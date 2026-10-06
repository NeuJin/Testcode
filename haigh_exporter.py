#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FEMFAT Haigh Exporter
=====================
App nho (Tkinter, chi dung thu vien chuan) de xuat anh "Local Haigh Diagram" goc cua FEMFAT
cho mot danh sach node, bang script Tcl chay ben trong FEMFAT (BLT snap / blt::winop snap).

Cach hoat dong:
  1. App sinh 2 file trong <thu muc output>/_job : run_haigh.ffj va hx_export.tcl
  2. Che do "batch": app chay  femfat.bat -job=run_haigh.ffj
     Che do "append": ban mo FEMFAT, nap ket qua, roi File -> Append -> run_haigh.ffj
  3. Script mo hop thoai Haigh, doi tung node, bat/tat diem do, chup anh, ghi log.
  4. App doc log va hien ket qua tung node.

Chay:  python haigh_exporter.py        (build exe: pyinstaller --onefile --noconsole haigh_exporter.py)
"""
from __future__ import annotations

import glob
import json
import ntpath
import os
import posixpath
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
except Exception:  # cho phep test phan logic khi khong co tkinter
    tk = None

APP_NAME = "FEMFAT Haigh Exporter"
CONFIG_PATH = Path.home() / ".femfat_haigh_exporter.json"
TOOL_DIR = Path.home() / "femfat_haigh_tool"
HIDE_WHEN_OFF = True  # tat diem do = an han ky hieu "Critical Point" (False: chi bo highlight)

DEFAULT_CFG = {
    "femfat_bat": "",
    "ffj": "",
    "fps": "",
    "out_auto": True,
    "out_dir": "",
    "nodes": "",
    "crit": True,
    "mode": "both",       # graph | full | both
    "run_mode": "append",  # batch | append
    "load_template": "",
}

# --------------------------------------------------------------------------------------
# Script Tcl chay ben trong FEMFAT (ASCII thuan). Doc cac bien ::hx_* do job dat truoc.
# --------------------------------------------------------------------------------------
TCL_EXPORT = r'''# hx_export.tcl -- sinh boi haigh_exporter.py
# Dung cac bien ::hx_* do job dat truoc:
#   ::hx_work ::hx_dir ::hx_prefix ::hx_nodes ::hx_crit_on ::hx_hide_when_off ::hx_do_graph ::hx_do_full
set ::hx_tries 0
set ::hx_fh [::open [::file join $::hx_work hx_log.txt] w]
proc ::hx_log {s} { ::catch {::puts $::hx_fh $s; ::flush $::hx_fh} }

# ---------- chup anh ----------
proc ::hx_snap_graph {file} {
    ::catch {::image delete hx_img1}
    ::image create photo hx_img1
    .resultHaighDiagramDialog.childsite.lf1.graph.graph snap hx_img1
    hx_img1 write $file -format png
    ::image delete hx_img1
}
proc ::hx_snap_full {file} {
    if {[::info commands ::blt::winop] eq ""} { error "khong co ::blt::winop" }
    ::catch {::image delete hx_img3}
    ::image create photo hx_img3
    ::blt::winop snap .resultHaighDiagramDialog.childsite hx_img3
    hx_img3 write $file -format png
    ::image delete hx_img3
}

# ---------- legend / Critical Point ----------
proc ::hx_legend_text {} {
    set cv .resultHaighDiagramDialog.childsite.lf1.legend.cv
    set txt ""
    foreach lb {lb1 lb2 lb3 lb4} { ::catch {append txt " | [$cv.$lb cget -text]"} }
    return $txt
}
proc ::hx_wait_legend {pat {maxms 5000}} {
    set t 0
    while {$t <= $maxms} {
        ::update
        if {[::string first $pat [::hx_legend_text]] >= 0} { return 1 }
        ::after 100
        incr t 100
    }
    return 0
}
proc ::hx_crit_row {} {
    set cv .resultHaighDiagramDialog.childsite.lf1.legend.cv
    foreach i {1 2 3 4} {
        if {[::catch {$cv.lb$i cget -text} t]} continue
        if {[::string match -nocase "*critical*" $t]} { return $i }
    }
    return 0
}
proc ::hx_crit_on {k} {
    set cv .resultHaighDiagramDialog.childsite.lf1.legend.cv
    if {[::catch {
        set a [$cv.lb$k cget -background]
        set b [$cv cget -background]
    }]} { return 0 }
    return [expr {$a ne $b}]
}
proc ::hx_click {w} {
    ::catch {::event generate $w <Enter>}
    ::event generate $w <ButtonPress-1> -x 3 -y 3
    ::event generate $w <ButtonRelease-1> -x 3 -y 3
    ::update
}
proc ::hx_set_crit {want} {
    set d .resultHaighDiagramDialog.childsite.lf1.legend
    set k [::hx_crit_row]
    if {$k == 0} { ::hx_log "crit: khong thay hang Critical trong legend"; return 0 }
    set cur [::hx_crit_on $k]
    if {$cur == $want} { return 1 }
    foreach w [list $d.cv.lb$k $d.cv.leg$k] {
        ::catch {::hx_click $w} msg
        if {[::hx_crit_on $k] == $want} { return 1 }
    }
    foreach arg [list {} $k] {
        set rc [::catch {$d toggleHighlightGraph {*}$arg} msg]
        ::update
        if {$rc == 0 && [::hx_crit_on $k] == $want} { return 1 }
    }
    return 0
}
proc ::hx_crit_elements {} {
    set g .resultHaighDiagramDialog.childsite.lf1.graph.graph
    set res {}
    foreach el [$g element names] {
        if {[::catch {$g element cget $el -label} lab]} continue
        if {[::string match -nocase "*critical*" $lab]} { lappend res $el }
    }
    return $res
}
proc ::hx_force_big {} {
    set g .resultHaighDiagramDialog.childsite.lf1.graph.graph
    foreach el [::hx_crit_elements] {
        ::catch {
            set px [$g element cget $el -pixels]
            $g element configure $el -pixels [expr {$px < 14 ? 14 : $px}]
        }
    }
}
proc ::hx_apply_crit {} {
    set g .resultHaighDiagramDialog.childsite.lf1.graph.graph
    if {$::hx_crit_on} {
        set ok [::hx_set_crit 1]
        foreach el [::hx_crit_elements] { ::catch {$g element configure $el -hide no} }
        if {!$ok} {
            ::hx_log "crit: khong bat duoc bang GUI -> phong to ky hieu truc tiep"
            ::hx_force_big
        }
    } else {
        ::hx_set_crit 0
        if {$::hx_hide_when_off} {
            foreach el [::hx_crit_elements] { ::catch {$g element configure $el -hide yes} }
        }
    }
    ::update
}

# ---------- tung node ----------
proc ::hx_one {node} {
    set d .resultHaighDiagramDialog
    set si $d.childsite.nodeSelector.si01
    ::hx_log "---- node $node ----"
    ::catch {$si.entry delete 0 end}
    ::catch {$si.entry insert 0 $node}
    set rc [::catch {$si apply} msg]
    ::hx_log "spinbox apply rc=$rc msg=$msg"
    if {![::hx_wait_legend "N$node" 6000]} {
        ::hx_log "RESULT\t$node\tFAIL\t-\t-\tnode khong co trong DETAILED RESULTS hoac do thi khong doi"
        return
    }
    ::hx_apply_crit
    ::update
    ::catch {::raise $d}
    ::update
    set gfile "-"
    set ffile "-"
    set err ""
    if {$::hx_do_graph} {
        set f [::file join $::hx_dir "${::hx_prefix}_N${node}_graph.png"]
        if {[::catch {::hx_snap_graph $f} msg]} { append err " graph:$msg" } else { set gfile $f }
    }
    if {$::hx_do_full} {
        set f [::file join $::hx_dir "${::hx_prefix}_N${node}_full.png"]
        if {[::catch {::hx_snap_full $f} msg]} { append err " full:$msg" } else { set ffile $f }
    }
    if {$err eq ""} {
        ::hx_log "RESULT\t$node\tOK\t$gfile\t$ffile\t"
    } else {
        ::hx_log "RESULT\t$node\tFAIL\t$gfile\t$ffile\t[::string trim $err]"
    }
}

# ---------- ket thuc / chay ----------
proc ::hx_finish {} {
    set rc [::catch {.resultHaighDiagramDialog.frButtons.close invoke} msg]
    ::hx_log "close invoke rc=$rc msg=$msg"
    if {$rc} { ::catch {.resultHaighDiagramDialog.frButtons.ok invoke} }
    ::hx_log "done"
    ::catch {::close $::hx_fh}
    set ::hx_done 1
}

proc ::hx_run {} {
    set d .resultHaighDiagramDialog
    set g $d.childsite.lf1.graph.graph
    set ns $d.childsite.nodeSelector
    if {![::winfo exists $g] || ![::winfo ismapped $g]} {
        incr ::hx_tries
        ::hx_log "graph chua hien (lan $::hx_tries)"
        if {$::hx_tries < 20} { ::after 500 ::hx_run; return }
        ::hx_log "FATAL\thop thoai Haigh khong mo duoc (da nap ket qua chua?)"
        ::hx_finish
        return
    }
    ::hx_log "dialog is up"
    ::catch {$ns.rbs2.rb2 invoke}
    ::update
    foreach node $::hx_nodes {
        if {[::catch {::hx_one $node} err]} {
            ::hx_log "RESULT\t$node\tFAIL\t-\t-\t$err"
        }
    }
    ::hx_finish
}

# ---- chay ----
set ::hx_btn ".femfat.hpane.rpane.main_sw.cv.dialogFr.bas-vi.inf.lf1.btHaigh.button"
set ::hx_wait 0
proc ::hx_start {} {
    if {![::winfo exists $::hx_btn]} {
        incr ::hx_wait
        if {$::hx_wait == 1 || $::hx_wait % 10 == 0} {
            ::hx_log "cho GUI/nut Haigh (lan $::hx_wait) children=[::catch {::winfo children .} ch; set ch]"
        }
        if {$::hx_wait < 240} { ::after 500 ::hx_start; return }
        ::hx_log "FATAL\tkhong thay nut Haigh sau 120 s (GUI chua dung hoac chua nap ket qua)"
        ::hx_finish
        return
    }
    ::hx_log "nut Haigh da co sau [expr {$::hx_wait * 500}] ms"
    ::after 1500 ::hx_run
    set rc [::catch {$::hx_btn invoke} msg]
    ::hx_log "btHaigh invoke returned rc=$rc msg=$msg"
}
::hx_start
'''

# --------------------------------------------------------------------------------------
# Logic (khong phu thuoc GUI)
# --------------------------------------------------------------------------------------


def norm_path(p) -> str:
    """Chuan hoa duong dan: bo dau nhay/khoang trang thua, thong nhat dau / va \\ theo he dieu hanh."""
    p = str(p or "").strip().strip('"').strip("'").strip()
    if not p:
        return ""
    if os.name == "nt":
        return ntpath.normpath(p.replace("/", "\\"))
    return posixpath.normpath(p.replace("\\", "/"))


def tcl_str(s) -> str:
    """Chuoi Tcl trong ngoac kep, dung dau / cho duong dan."""
    s = str(s).replace("\\", "/")
    for ch, rep in (('"', '\\"'), ("$", "\\$"), ("[", "\\["), ("]", "\\]")):
        s = s.replace(ch, rep)
    return f'"{s}"'


def parse_nodes(text: str) -> list[str]:
    seen: list[str] = []
    for n in re.findall(r"\d+", text or ""):
        if n not in seen:
            seen.append(n)
    return seen


def default_outdir(fps: str, ffj: str) -> str:
    base = norm_path(fps) or norm_path(ffj)
    if not base:
        return ""
    p = Path(base)
    return str(p.parent / (p.stem + "_haigh"))


def safe_prefix(fps: str, ffj: str) -> str:
    base = Path(fps).stem if fps else (Path(ffj).stem if ffj else "haigh")
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", base) or "haigh"


def effective_outdir(cfg: dict) -> str:
    if (not cfg["out_auto"]) and cfg["out_dir"].strip():
        return norm_path(cfg["out_dir"])
    return default_outdir(cfg["fps"], cfg["ffj"])


def find_femfat() -> str:
    pats = [
        r"C:\Program Files\ECS\FEMFAT*\bin\femfat.bat",
        r"C:\Program Files\*\FEMFAT*\bin\femfat.bat",
        r"D:\ECS\FEMFAT*\bin\femfat.bat",
    ]
    for p in pats:
        m = sorted(glob.glob(p), reverse=True)
        if m:
            return m[0]
    return ""


def validate(cfg: dict) -> list[str]:
    errs: list[str] = []
    if not parse_nodes(cfg["nodes"]):
        errs.append("Chưa nhập node ID.")
    if not effective_outdir(cfg):
        errs.append("Chưa có thư mục output (nhập fps/ffj để tự đặt, hoặc bỏ tick 'Tự động' và chọn thư mục).")
    if cfg["run_mode"] == "batch":
        if not cfg["femfat_bat"] or not Path(cfg["femfat_bat"]).exists():
            errs.append("Chưa chọn đúng file femfat.bat.")
        if not cfg["ffj"] and not cfg["fps"]:
            errs.append("Chế độ batch cần ffj hoặc fps.")
        if cfg["ffj"] and not Path(cfg["ffj"]).exists():
            errs.append("File ffj không tồn tại.")
        if cfg["fps"] and not Path(cfg["fps"]).exists():
            errs.append("File fps không tồn tại.")
        if cfg["fps"] and not any("@FPS@" in x for x in clean_template(cfg["load_template"])):
            errs.append("Chưa có 'Lệnh nạp fps' (mục Nâng cao). Dùng nút 'Ghi lệnh nạp fps' để lấy lệnh một lần, "
                        "hoặc dùng chế độ 'append'.")
    return errs


def clean_template(text: str) -> list[str]:
    """Chi giu cac lenh GHI (setValue...), bo getValue (chi doc) va dong trung lien tiep."""
    out: list[str] = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or re.match(r"^(::)?(doc0\s+)?getValue\b", ln):
            continue
        if not out or out[-1] != ln:
            out.append(ln)
    return out


def build_job(cfg: dict, work: Path, outdir: Path, tcl_path: Path) -> str:
    nodes = parse_nodes(cfg["nodes"])
    prefix = safe_prefix(cfg["fps"], cfg["ffj"])
    do_graph = 1 if cfg["mode"] in ("graph", "both") else 0
    do_full = 1 if cfg["mode"] in ("full", "both") else 0
    L = [
        "# FEMFAT Haigh Exporter - job tu dong sinh (khong sua tay)",
        "set ::hx_done 0",
        f"set ::hx_work {tcl_str(work)}",
        f"set ::hx_dir {tcl_str(outdir)}",
        f"set ::hx_prefix {tcl_str(prefix)}",
        "set ::hx_nodes {" + " ".join(nodes) + "}",
        f"set ::hx_crit_on {1 if cfg['crit'] else 0}",
        f"set ::hx_hide_when_off {1 if HIDE_WHEN_OFF else 0}",
        f"set ::hx_do_graph {do_graph}",
        f"set ::hx_do_full {do_full}",
    ]
    L.append(f"set ::hx_trace {tcl_str(work / 'hx_jobtrace.txt')}")
    L.append('proc ::hx_jt {s} { ::catch { set f [::open $::hx_trace a]; ::puts $f $s; ::close $f } }')
    L.append('::hx_jt "job bat dau"')
    if cfg["run_mode"] == "batch":
        if cfg["ffj"]:
            L.append(f'if {{[::catch {{::source {tcl_str(cfg["ffj"])}}} ::hx_e]}} {{ ::hx_jt "LOI ffj: $::hx_e" }} else {{ ::hx_jt "ffj OK" }}')
        if cfg["fps"] and cfg["load_template"].strip():
            fps = str(cfg["fps"]).replace("\\", "/")
            for ln in clean_template(cfg["load_template"]):
                if "{@FPS@}" in ln:
                    ln = ln.replace("@FPS@", fps)
                else:
                    ln = ln.replace("@FPS@", "{" + fps + "}")
                L.append(f'if {{[::catch {{{ln}}} ::hx_e]}} {{ ::hx_jt "LOI lenh nap: $::hx_e" }} else {{ ::hx_jt "nap OK" }}')
    L.append('::hx_jt "chuan bi chay script xuat anh"')
    L += [
        f"set ::hx_tcl {tcl_str(tcl_path)}",
        f"set ::hx_errfile {tcl_str(work / 'hx_error.txt')}",
        "::uplevel #0 {",
        "    ::after 1000 {",
        "        if {[::catch {::source $::hx_tcl} ::hx_err]} {",
        "            ::catch {",
        "                set ::ef [::open $::hx_errfile w]",
        "                ::puts $::ef $::hx_err",
        "                ::puts $::ef $::errorInfo",
        "                ::close $::ef",
        "            }",
        "            set ::hx_done 1",
        "        }",
        "    }",
        "}",
        "::vwait ::hx_done",
        "",
    ]
    return "\n".join(L)


def prepare(cfg: dict) -> dict:
    outdir = Path(effective_outdir(cfg))
    work = outdir / "_job"
    work.mkdir(parents=True, exist_ok=True)
    tcl_path = work / "hx_export.tcl"
    job_path = work / "run_haigh.ffj"
    tcl_path.write_text(TCL_EXPORT, encoding="utf-8")
    job_path.write_text(build_job(cfg, work, outdir, tcl_path), encoding="utf-8")
    return {"outdir": outdir, "work": work, "tcl": tcl_path, "job": job_path,
            "log": work / "hx_log.txt", "err": work / "hx_error.txt",
            "nodes": parse_nodes(cfg["nodes"])}


def kill_tree(proc) -> None:
    try:
        if proc and proc.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                proc.kill()
    except Exception:
        pass


def worker(cfg: dict, info: dict, q: "queue.Queue", stop: threading.Event, holder: dict) -> None:
    work: Path = info["work"]
    log_path: Path = info["log"]
    err_path: Path = info["err"]
    for p in (log_path, err_path, work / "hx_jobtrace.txt"):
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    proc = None
    try:
        if cfg["run_mode"] == "batch":
            cwd = str(Path(cfg["ffj"]).parent) if cfg["ffj"] else str(work)
            cmd = f'"{cfg["femfat_bat"]}" -job="{str(info["job"]).replace(chr(92), "/")}" -gui'
            out = open(work / "femfat_stdout.txt", "wb")
            proc = subprocess.Popen(cmd, shell=True, cwd=cwd, stdout=out, stderr=subprocess.STDOUT)
            holder["proc"] = proc
            q.put(("log", f"Đã chạy FEMFAT (PID {proc.pid}). Đợi script xuất ảnh..."))
        else:
            q.put(("log", "Đã tạo job: " + str(info["job"])))
            q.put(("log", "Trong FEMFAT (đã nạp kết quả, đang ở trang Visualization, hộp thoại Haigh ĐÓNG): "
                          "File → Append... → chọn file job ở trên. Đừng chạm chuột/bàn phím và đừng để cửa sổ khác "
                          "che FEMFAT cho tới khi hộp thoại tự đóng."))
        pos = 0
        buf = ""
        done = False
        done_t = None
        t0 = time.time()
        warned = False
        while True:
            if stop.is_set():
                q.put(("log", "Đã dừng theo yêu cầu."))
                break
            if log_path.exists():
                with open(log_path, "rb") as f:
                    f.seek(pos)
                    data = f.read()
                pos += len(data)
                buf += data.decode("utf-8", "replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.rstrip("\r")
                    if line.startswith("RESULT\t"):
                        parts = line.split("\t")
                        parts += [""] * (6 - len(parts))
                        q.put(("result", parts[1:6]))
                    elif line.startswith("FATAL\t"):
                        q.put(("log", "LỖI: " + line.split("\t", 1)[1]))
                    elif line == "done":
                        done = True
                        done_t = time.time()
                    elif line.startswith("---- node"):
                        q.put(("log", line.strip("- ")))
            if err_path.exists():
                q.put(("log", "LỖI script Tcl:\n" + err_path.read_text(encoding="utf-8", errors="replace")))
                break
            if proc is not None and proc.poll() is not None:
                q.put(("log", f"FEMFAT đã thoát (mã {proc.returncode})."))
                if not done and not log_path.exists():
                    q.put(("log", "Không có log: FEMFAT thoát trước khi chạy script."))
                    for nm in ("hx_jobtrace.txt", "femfat_stdout.txt"):
                        fp = work / nm
                        try:
                            txt = fp.read_text(encoding="utf-8", errors="replace").strip()
                        except Exception:
                            txt = "(không có file)"
                        q.put(("log", f"--- {nm} (cuối) ---\n" + "\n".join(txt.splitlines()[-25:])))
                # doc not phan log con lai roi thoat
                if log_path.exists():
                    with open(log_path, "rb") as f:
                        f.seek(pos)
                        tail = f.read().decode("utf-8", "replace")
                    for line in tail.splitlines():
                        if line.startswith("RESULT\t"):
                            parts = line.split("\t")
                            parts += [""] * (6 - len(parts))
                            q.put(("result", parts[1:6]))
                break
            if done:
                if proc is None or proc.poll() is not None:
                    break
                if time.time() - done_t > 5:
                    q.put(("log", "Xong. Đóng FEMFAT."))
                    kill_tree(proc)
                    break
            if not warned and time.time() - t0 > 180 and not log_path.exists():
                warned = True
                q.put(("log", "Sau 3 phút chưa thấy log: FEMFAT có thể đang chờ license hoặc hộp thoại lỗi. "
                              "Kiểm tra cửa sổ FEMFAT."))
            time.sleep(0.4)
    except Exception as e:  # noqa: BLE001
        q.put(("log", f"Lỗi app: {e!r}"))
    finally:
        if proc is not None:
            kill_tree(proc)
        q.put(("finished", None))


# --------------------------------------------------------------------------------------
# Ghi lenh nap fps (de lay lenh ffj that su do GUI goi)
# --------------------------------------------------------------------------------------
def make_record_ffj() -> tuple[Path, Path]:
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    log = TOOL_DIR / "fps_load_record.txt"
    ffj = TOOL_DIR / "record_fps_load.ffj"
    text = "\n".join([
        "::uplevel #0 {",
        f"    set ::rec_fh [::open {tcl_str(log)} w]",
        "    proc ::rec_cb {cmd op} {",
        "        ::catch {::puts $::rec_fh [::string range $cmd 0 800]; ::flush $::rec_fh}",
        "    }",
        "    ::trace add execution ::doc0 enter ::rec_cb",
        "}",
        "",
    ])
    ffj.write_text(text, encoding="utf-8")
    return ffj, log


def recorded_candidates(log: Path) -> tuple[list[str], int]:
    if not log.exists():
        return [], 0
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    cands = [ln for ln in lines if re.search(r"fps", ln, re.I)]
    return cands, len(lines)


def to_template(lines: list[str]) -> str:
    out = []
    for ln in lines:
        if re.match(r"^\s*(::)?(doc0\s+)?getValue\b", ln):
            continue
        ln = re.sub(r"^\s*(::)?doc0\s+", "", ln)
        ln = re.sub(r"\{[^{}]*\.fps\}", "{@FPS@}", ln, flags=re.I)
        ln = re.sub(r"[^\s{}\"]+\.fps", "@FPS@", ln, flags=re.I)
        out.append(ln)
    return "\n".join(out)


# --------------------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------------------
def load_cfg() -> dict:
    cfg = dict(DEFAULT_CFG)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception:
        pass
    if not cfg["femfat_bat"]:
        cfg["femfat_bat"] = find_femfat()
    return cfg


def save_cfg(cfg: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = load_cfg()
        self.q: queue.Queue = queue.Queue()
        self.stop = threading.Event()
        self.holder: dict = {}
        self.thread = None
        self.info = None
        root.title(APP_NAME)
        root.minsize(760, 640)
        self.build_ui()
        self.refresh_out()
        root.after(200, self.poll)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---- UI ----
    def build_ui(self):
        r = self.root
        r.columnconfigure(0, weight=1)
        r.rowconfigure(0, weight=1)
        main = ttk.Frame(r, padding=10)
        main.grid(sticky="nsew")
        main.columnconfigure(1, weight=1)
        main.rowconfigure(8, weight=1)
        c = self.cfg

        self.v_femfat = tk.StringVar(value=c["femfat_bat"])
        self.v_ffj = tk.StringVar(value=c["ffj"])
        self.v_fps = tk.StringVar(value=c["fps"])
        self.v_out_auto = tk.BooleanVar(value=c["out_auto"])
        self.v_out = tk.StringVar(value=c["out_dir"])
        self.v_crit = tk.BooleanVar(value=c["crit"])
        self.v_mode = tk.StringVar(value=c["mode"])
        self.v_run = tk.StringVar(value=c["run_mode"])

        def path_row(row, label, var, cmd, hint=None):
            ttk.Label(main, text=label).grid(row=row, column=0, sticky="w", pady=2)
            e = ttk.Entry(main, textvariable=var)
            e.grid(row=row, column=1, sticky="ew", padx=6, pady=2)
            e.bind("<FocusOut>", lambda ev, v=var: v.set(norm_path(v.get())))
            ttk.Button(main, text="Chọn…", command=cmd, width=8).grid(row=row, column=2, pady=2)
            if hint:
                ttk.Label(main, text=hint, foreground="#666").grid(row=row + 1, column=1, sticky="w", padx=6)
            return e

        path_row(0, "FEMFAT (femfat.bat)", self.v_femfat, lambda: self.pick(self.v_femfat, [("femfat.bat", "*.bat"), ("Tất cả", "*.*")]))
        path_row(1, "File ffj (tuỳ chọn)", self.v_ffj, lambda: self.pick(self.v_ffj, [("FEMFAT job", "*.ffj"), ("Tất cả", "*.*")]))
        path_row(2, "File fps (kết quả)", self.v_fps, lambda: self.pick(self.v_fps, [("FEMFAT fps", "*.fps"), ("Tất cả", "*.*")]))

        ttk.Label(main, text="Thư mục ảnh output").grid(row=3, column=0, sticky="w", pady=2)
        self.e_out = ttk.Entry(main, textvariable=self.v_out)
        self.e_out.grid(row=3, column=1, sticky="ew", padx=6, pady=2)
        self.e_out.bind("<FocusOut>", lambda ev: self.v_out.set(norm_path(self.v_out.get())))
        self.b_out = ttk.Button(main, text="Chọn…", width=8, command=self.pick_out)
        self.b_out.grid(row=3, column=2, pady=2)
        ttk.Checkbutton(main, text="Tự động (cạnh file fps/ffj: <tên>_haigh)", variable=self.v_out_auto,
                        command=self.refresh_out).grid(row=4, column=1, sticky="w", padx=6)
        self.v_fps.trace_add("write", lambda *a: self.refresh_out())
        self.v_ffj.trace_add("write", lambda *a: self.refresh_out())

        ttk.Label(main, text="Node ID").grid(row=5, column=0, sticky="nw", pady=4)
        nf = ttk.Frame(main)
        nf.grid(row=5, column=1, columnspan=2, sticky="ew", padx=6, pady=4)
        nf.columnconfigure(0, weight=1)
        self.t_nodes = tk.Text(nf, height=3, width=50)
        self.t_nodes.grid(row=0, column=0, sticky="ew")
        self.t_nodes.insert("1.0", c["nodes"])
        ttk.Label(nf, text="Cách nhau bằng dấu phẩy, khoảng trắng hoặc xuống dòng. Node phải nằm trong DETAILED RESULTS group.",
                  foreground="#666").grid(row=1, column=0, sticky="w")

        opt = ttk.LabelFrame(main, text="Tuỳ chọn", padding=8)
        opt.grid(row=6, column=0, columnspan=3, sticky="ew", pady=6)
        ttk.Checkbutton(opt, text="Hiện điểm đỏ Critical Point (mặc định bật)", variable=self.v_crit).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(opt, text="Xuất ảnh:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Radiobutton(opt, text="Chỉ đồ thị (graph)", variable=self.v_mode, value="graph").grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Radiobutton(opt, text="Đầy đủ (full, winop)", variable=self.v_mode, value="full").grid(row=1, column=2, sticky="w", pady=(6, 0))
        ttk.Radiobutton(opt, text="Cả hai", variable=self.v_mode, value="both").grid(row=1, column=3, sticky="w", pady=(6, 0))
        ttk.Label(opt, text="Cách chạy:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Radiobutton(opt, text="Append (FEMFAT đã mở, đã nạp kết quả) — đã kiểm chứng", variable=self.v_run, value="append").grid(row=2, column=1, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Radiobutton(opt, text="Batch (app tự chạy femfat.bat, cần ffj/lệnh nạp fps) — chưa kiểm chứng", variable=self.v_run, value="batch").grid(row=3, column=1, columnspan=3, sticky="w")

        adv = ttk.LabelFrame(main, text="Nâng cao: lệnh nạp fps vào FEMFAT (chỉ cần cho chế độ batch; dùng @FPS@ thay cho đường dẫn)", padding=8)
        adv.grid(row=7, column=0, columnspan=3, sticky="ew", pady=4)
        adv.columnconfigure(0, weight=1)
        self.t_tpl = tk.Text(adv, height=3, width=60)
        self.t_tpl.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.t_tpl.insert("1.0", c["load_template"])
        ttk.Button(adv, text="Ghi lệnh nạp fps…", command=self.record_start).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(adv, text="Xem lệnh đã ghi…", command=self.record_view).grid(row=1, column=1, sticky="w", pady=(6, 0), padx=6)

        lf = ttk.LabelFrame(main, text="Tiến trình / kết quả", padding=6)
        lf.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=6)
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(1, weight=1)
        cols = ("node", "status", "graph", "full", "note")
        self.tree = ttk.Treeview(lf, columns=cols, show="headings", height=5)
        for k, w in zip(cols, (90, 60, 220, 220, 200)):
            self.tree.heading(k, text=k)
            self.tree.column(k, width=w, anchor="w")
        self.tree.grid(row=0, column=0, sticky="ew")
        self.tree.bind("<Double-1>", self.open_selected)
        self.log = scrolledtext.ScrolledText(lf, height=8, state="disabled", wrap="word")
        self.log.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        bf = ttk.Frame(main)
        bf.grid(row=9, column=0, columnspan=3, sticky="ew")
        self.b_run = ttk.Button(bf, text="Chạy", command=self.run)
        self.b_run.pack(side="left")
        self.b_stop = ttk.Button(bf, text="Dừng", command=self.stop_run, state="disabled")
        self.b_stop.pack(side="left", padx=6)
        ttk.Button(bf, text="Mở thư mục output", command=self.open_out).pack(side="left")
        self.v_status = tk.StringVar(value="Sẵn sàng.")
        ttk.Label(bf, textvariable=self.v_status).pack(side="right")

    # ---- helpers ----
    def pick(self, var, types):
        p = filedialog.askopenfilename(filetypes=types)
        if p:
            var.set(norm_path(p))

    def pick_out(self):
        p = filedialog.askdirectory()
        if p:
            self.v_out.set(norm_path(p))

    def refresh_out(self):
        if self.v_out_auto.get():
            self.v_out.set(default_outdir(self.v_fps.get(), self.v_ffj.get()))
            self.e_out.state(["disabled"])
            self.b_out.state(["disabled"])
        else:
            self.e_out.state(["!disabled"])
            self.b_out.state(["!disabled"])

    def collect(self) -> dict:
        return {
            "femfat_bat": norm_path(self.v_femfat.get()),
            "ffj": norm_path(self.v_ffj.get()),
            "fps": norm_path(self.v_fps.get()),
            "out_auto": bool(self.v_out_auto.get()),
            "out_dir": norm_path(self.v_out.get()),
            "nodes": self.t_nodes.get("1.0", "end").strip(),
            "crit": bool(self.v_crit.get()),
            "mode": self.v_mode.get(),
            "run_mode": self.v_run.get(),
            "load_template": self.t_tpl.get("1.0", "end").strip(),
        }

    def add_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ---- run ----
    def run(self):
        cfg = self.collect()
        errs = validate(cfg)
        if errs:
            messagebox.showerror(APP_NAME, "\n".join("• " + e for e in errs))
            return
        save_cfg(cfg)
        try:
            self.info = prepare(cfg)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(APP_NAME, f"Không tạo được job: {e}")
            return
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.stop.clear()
        self.holder = {}
        self.b_run.state(["disabled"])
        self.b_stop.state(["!disabled"])
        self.v_status.set("Đang chạy…")
        self.add_log(f"--- Bắt đầu: {len(self.info['nodes'])} node, output: {self.info['outdir']}")
        self.thread = threading.Thread(target=worker, args=(cfg, self.info, self.q, self.stop, self.holder), daemon=True)
        self.thread.start()

    def stop_run(self):
        self.stop.set()
        kill_tree(self.holder.get("proc"))

    def poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "log":
                    self.add_log(data)
                elif kind == "result":
                    node, status, g, f, note = data
                    self.tree.insert("", "end", values=(node, status, g, f, note))
                elif kind == "finished":
                    self.b_run.state(["!disabled"])
                    self.b_stop.state(["disabled"])
                    rows = [self.tree.item(i)["values"] for i in self.tree.get_children()]
                    ok = sum(1 for r in rows if str(r[1]) == "OK")
                    self.v_status.set(f"Xong: {ok}/{len(rows)} node OK.")
                    self.add_log(f"--- Kết thúc: {ok}/{len(rows)} node OK.")
        except queue.Empty:
            pass
        self.root.after(300, self.poll)

    def open_out(self):
        d = effective_outdir(self.collect())
        if d and Path(d).exists() and hasattr(os, "startfile"):
            os.startfile(d)  # type: ignore[attr-defined]
        elif d:
            messagebox.showinfo(APP_NAME, d)

    def open_selected(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])["values"]
        for p in (vals[3], vals[2]):
            if p and str(p) != "-" and Path(str(p)).exists() and hasattr(os, "startfile"):
                os.startfile(str(p))  # type: ignore[attr-defined]
                return

    # ---- ghi lenh nap fps ----
    def record_start(self):
        ffj, log = make_record_ffj()
        messagebox.showinfo(
            APP_NAME,
            "Làm một lần để lấy lệnh nạp fps:\n\n"
            "1) Mở FEMFAT (nạp ffj nếu cần).\n"
            f"2) File → Append... → chọn:\n   {ffj}\n"
            "3) Nạp file fps bằng GUI như bạn vẫn làm.\n"
            "4) Quay lại app, bấm 'Xem lệnh đã ghi…'.\n\n"
            f"Log ghi tại: {log}")

    def record_view(self):
        log = TOOL_DIR / "fps_load_record.txt"
        cands, total = recorded_candidates(log)
        win = tk.Toplevel(self.root)
        win.title("Lệnh đã ghi")
        win.geometry("760x420")
        ttk.Label(win, text=f"Tổng {total} lệnh đã ghi; {len(cands)} dòng có chữ 'fps'. "
                            "Giữ lại các dòng đúng là nạp fps, xoá dòng thừa, rồi bấm 'Dùng làm mẫu'.").pack(anchor="w", padx=8, pady=6)
        txt = scrolledtext.ScrolledText(win, wrap="none")
        txt.pack(fill="both", expand=True, padx=8)
        txt.insert("1.0", "\n".join(cands) if cands else "(chưa có dòng nào — hãy chạy bước ghi lệnh trước)")

        def use():
            lines = [ln for ln in txt.get("1.0", "end").splitlines() if ln.strip()]
            self.t_tpl.delete("1.0", "end")
            self.t_tpl.insert("1.0", to_template(lines))
            win.destroy()

        ttk.Button(win, text="Dùng làm mẫu", command=use).pack(pady=6)

    def on_close(self):
        save_cfg(self.collect())
        self.stop_run()
        self.root.destroy()


def main():
    if tk is None:
        print("Python của bạn thiếu tkinter.")
        sys.exit(1)
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
