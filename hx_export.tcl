# hx_export.tcl -- THI NGHIEM: tu mo hop thoai Haigh, doi node, chup anh (BLT snap + Img window)
# Chay boi run_hx.ffj. Ket qua nam trong D:/femfat_probe/out
set ::hx_dir "D:/femfat_probe/out"
set ::hx_nodes {1397615 1205731 1402796 1155964 1058635 3046564 1327621}
set ::hx_tries 0
set ::hx_ntrace 0
::file mkdir $::hx_dir
set ::hx_fh [::open [::file join $::hx_dir hx_log.txt] w]

proc ::hx_log {s} { ::catch {::puts $::hx_fh $s; ::flush $::hx_fh} }

# ghi lai moi lenh goi vao doc0 (de hoc cach FEMFAT doi node khi ban thao tac tay)
proc ::hx_trace {cmd op} {
    incr ::hx_ntrace
    if {$::hx_ntrace <= 400} { ::hx_log "doc0> [::string range $cmd 0 300]" }
}

# chup rieng vung do thi (BLT snap) -> PNG (Img)
proc ::hx_snap_graph {file} {
    ::catch {::image delete hx_img1}
    ::image create photo hx_img1
    .resultHaighDiagramDialog.childsite.lf1.graph.graph snap hx_img1
    hx_img1 write $file -format png
    ::image delete hx_img1
}

# chup ca khung (tieu de + do thi + legend + o chon node) bang Img 'window'
proc ::hx_snap_window {w file} {
    ::catch {::image delete hx_img2}
    ::image create photo hx_img2 -format window -data $w
    hx_img2 write $file -format png
    ::image delete hx_img2
}

proc ::hx_one {node} {
    set d .resultHaighDiagramDialog
    set si $d.childsite.nodeSelector.si01
    ::hx_log ""
    ::hx_log "---- node $node ----"
    # 1) nhap node vao o spinbox qua entry cua Tk
    set e $si.entry
    ::catch {$e delete 0 end}
    ::catch {$e insert 0 $node}
    ::catch {::hx_log "entry=[$e get]  Value=[$si info variable ::Femfat::SpinBox::Value -value]"}
    # 2) goi apply cua spinbox
    set rc [::catch {$si apply} msg]
    ::hx_log "spinbox apply rc=$rc msg=$msg"
    # 3) cho do thi cap nhat: legend phai co 'N<node>'
    set ok 0
    set txt ""
    for {set i 0} {$i < 50} {incr i} {
        ::update
        set txt ""
        foreach lb {lb1 lb2 lb3 lb4} {
            ::catch {append txt " | [$d.childsite.lf1.legend.cv.$lb cget -text]"}
        }
        if {[::string first "N$node" $txt] >= 0} { set ok 1; break }
        ::after 100
    }
    ::hx_log "legend:$txt   matched=$ok  waited=[expr {$i * 100}]ms"
    ::catch {::hx_log "oldNodeLabel=[$d info variable ::Femfat::ResultHaighDiagram::oldNodeLabel -value]"}
    # 4) chup anh
    ::update
    ::catch {::raise $d}
    ::update
    set base [::file join $::hx_dir "haigh_$node"]
    set rc [::catch {::hx_snap_graph "${base}_graph.png"} msg]
    ::hx_log "snap graph  rc=$rc $msg"
    set rc [::catch {::hx_snap_window $d.childsite "${base}_window.png"} msg]
    ::hx_log "snap window rc=$rc $msg"
}

proc ::hx_finish {} {
    ::catch {::trace remove execution ::doc0 enter ::hx_trace}
    set rc [::catch {.resultHaighDiagramDialog.frButtons.close invoke} msg]
    ::hx_log "close invoke rc=$rc msg=$msg"
    if {$rc} { ::catch {.resultHaighDiagramDialog.frButtons.ok invoke} }
    ::hx_log "done"
    ::catch {::close $::hx_fh}
}

proc ::hx_run {} {
    set d .resultHaighDiagramDialog
    set g $d.childsite.lf1.graph.graph
    if {![::winfo exists $g] || ![::winfo ismapped $g]} {
        incr ::hx_tries
        ::hx_log "graph chua hien (lan $::hx_tries)"
        if {$::hx_tries < 20} { ::after 500 ::hx_run; return }
        ::hx_log "bo cuoc: hop thoai Haigh khong mo duoc"
        ::hx_finish
        return
    }
    ::hx_log "dialog is up: state=[::wm state $d] grab=[::grab current] graph=[::winfo width $g]x[::winfo height $g]"
    ::catch {::hx_log "radio rbs1 Value=[$d.childsite.nodeSelector.rbs1 info variable ::Femfat::RadioButtons::Value -value]  rbs2 Value=[$d.childsite.nodeSelector.rbs2 info variable ::Femfat::RadioButtons::Value -value]"}
    ::catch {::hx_log "spinbox Value=[$d.childsite.nodeSelector.si01 info variable ::Femfat::SpinBox::Value -value]"}
    foreach node $::hx_nodes { ::hx_one $node }
    ::hx_finish
}

# ---- chay ----
::catch {::trace add execution ::doc0 enter ::hx_trace} te
::hx_log "trace: $te"
::after 1500 ::hx_run
set rc [::catch {.femfat.hpane.rpane.main_sw.cv.dialogFr.bas-vi.inf.lf1.btHaigh.button invoke} msg]
::hx_log "btHaigh invoke returned rc=$rc msg=$msg"
