# hx_export2.tcl -- tu mo hop thoai Haigh, doi node, bat/tat "Critical Point", chup anh
# Chay boi run_hx2.ffj. Ket qua: D:/femfat_probe/out2

# ================= TUY CHON =================
set ::hx_dir "D:/femfat_probe/out2"
set ::hx_nodes {1397615 1205731 1402796 1155964 1058635 3046564 1327621}
set ::hx_crit_highlight 1    ;# 1 = bat diem do "Critical Point" noi bat, 0 = tat, -1 = giu nguyen
set ::hx_do_most_critical 1  ;# 1 = xuat them anh cua "Most Critical Node", 0 = khong
# ============================================

set ::hx_tries 0
::file mkdir $::hx_dir
set ::hx_fh [::open [::file join $::hx_dir hx2_log.txt] w]
proc ::hx_log {s} { ::catch {::puts $::hx_fh $s; ::flush $::hx_fh} }

# ---------- chup anh ----------
proc ::hx_snap_graph {file} {
    ::catch {::image delete hx_img1}
    ::image create photo hx_img1
    .resultHaighDiagramDialog.childsite.lf1.graph.graph snap hx_img1
    hx_img1 write $file -format png
    ::image delete hx_img1
}
proc ::hx_snap_window {w file} {
    ::catch {::image delete hx_img2}
    ::image create photo hx_img2 -format window -data $w
    hx_img2 write $file -format png
    ::image delete hx_img2
}
proc ::hx_capture {tag} {
    set d .resultHaighDiagramDialog
    ::update
    ::catch {::raise $d}
    ::update
    set base [::file join $::hx_dir "haigh_$tag"]
    set rc [::catch {::hx_snap_graph "${base}_graph.png"} msg]
    ::hx_log "snap graph  rc=$rc $msg"
    set rc [::catch {::hx_snap_window $d.childsite "${base}_window.png"} msg]
    ::hx_log "snap window rc=$rc $msg"
}

# ---------- legend ----------
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
# hang nao trong legend la "Critical Point"
proc ::hx_crit_row {} {
    set cv .resultHaighDiagramDialog.childsite.lf1.legend.cv
    foreach i {1 2 3 4} {
        if {[::catch {$cv.lb$i cget -text} t]} continue
        if {[::string match -nocase "*critical*" $t]} { return $i }
    }
    return 0
}
# hang do dang duoc highlight? (mau nen khac nen cua legend)
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
# dat trang thai highlight; tra ve 1 neu dat duoc
proc ::hx_set_crit {want} {
    set d .resultHaighDiagramDialog.childsite.lf1.legend
    set k [::hx_crit_row]
    if {$k == 0} { ::hx_log "crit: khong thay hang 'Critical' trong legend"; return 0 }
    set cur [::hx_crit_on $k]
    ::hx_log "crit: row=$k highlighted=$cur want=$want"
    if {$cur == $want} { return 1 }
    # cach 1: gui su kien click vao hang legend
    foreach w [list $d.cv.lb$k $d.cv.leg$k] {
        ::catch {::hx_click $w} msg
        if {[::hx_crit_on $k] == $want} { ::hx_log "crit: doi trang thai bang click vao $w"; return 1 }
    }
    # cach 2: goi method cua legend
    foreach arg [list {} $k] {
        set rc [::catch {$d toggleHighlightGraph {*}$arg} msg]
        ::update
        ::hx_log "crit: toggleHighlightGraph {$arg} rc=$rc msg=$msg now=[::hx_crit_on $k]"
        if {$rc == 0 && [::hx_crit_on $k] == $want} { return 1 }
    }
    return 0
}
# cach 3 (du phong): phong to ky hieu diem do truc tiep tren do thi BLT
proc ::hx_force_big {} {
    set g .resultHaighDiagramDialog.childsite.lf1.graph.graph
    foreach el [$g element names] {
        if {[::catch {$g element cget $el -label} lab]} continue
        if {![::string match -nocase "*critical*" $lab]} continue
        set rc [::catch {
            set px [$g element cget $el -pixels]
            $g element configure $el -pixels [expr {$px < 14 ? 14 : $px}]
        } msg]
        ::hx_log "force big: element $el label=$lab rc=$rc msg=$msg"
    }
}
proc ::hx_apply_crit {} {
    if {$::hx_crit_highlight < 0} { return }
    set ok [::hx_set_crit $::hx_crit_highlight]
    if {!$ok && $::hx_crit_highlight == 1} {
        ::hx_log "crit: khong bat duoc bang GUI -> dung cach du phong (phong to ky hieu)"
        ::hx_force_big
    }
    ::update
}

# ---------- thong tin chan doan ----------
proc ::hx_dump_fn {o} {
    ::catch {
        foreach f [$o info function] {
            set sig ""
            ::catch {set sig [$o info function $f -protection -args]}
            ::hx_log "   fn $f | $sig"
        }
    }
}
proc ::hx_dump_binds {w} {
    set seqs [::bind $w]
    ::hx_log "   binds $w: $seqs"
    foreach s $seqs { ::catch {::hx_log "      $s => [::string range [::bind $w $s] 0 300]"} }
}
proc ::hx_dump_elements {} {
    set g .resultHaighDiagramDialog.childsite.lf1.graph.graph
    foreach el [$g element names] {
        set line "element $el:"
        foreach opt {-label -pixels -symbol -fill -color -linewidth -hide} {
            ::catch {append line " $opt=[$g element cget $el $opt]"}
        }
        ::hx_log $line
    }
}
proc ::hx_dump_legend {} {
    set cv .resultHaighDiagramDialog.childsite.lf1.legend.cv
    ::catch {::hx_log "legend cv bg=[$cv cget -background]"}
    foreach i {1 2 3 4} {
        set line "legend row $i:"
        ::catch {append line " text='[$cv.lb$i cget -text]' lb_bg=[$cv.lb$i cget -background]"}
        ::catch {append line " leg_bg=[$cv.leg$i cget -background]"}
        ::hx_log $line
    }
}

# ---------- tung node ----------
proc ::hx_one {node} {
    set d .resultHaighDiagramDialog
    set si $d.childsite.nodeSelector.si01
    ::hx_log ""
    ::hx_log "---- node $node ----"
    set e $si.entry
    ::catch {$e delete 0 end}
    ::catch {$e insert 0 $node}
    set rc [::catch {$si apply} msg]
    ::hx_log "spinbox apply rc=$rc msg=$msg"
    set ok [::hx_wait_legend "N$node" 5000]
    ::hx_log "legend:[::hx_legend_text]   matched=$ok"
    ::hx_apply_crit
    ::hx_capture $node
}

# ---------- Most Critical Node ----------
proc ::hx_most_critical {} {
    set d .resultHaighDiagramDialog
    set ns $d.childsite.nodeSelector
    ::hx_log ""
    ::hx_log "---- MOST CRITICAL NODE ----"
    set r1 $ns.rbs1.rb1
    set r2 $ns.rbs2.rb2
    set t1 ""; set t2 ""
    ::catch {set t1 [$r1 cget -text]}
    ::catch {set t2 [$r2 cget -text]}
    if {[::string match -nocase "*critical*" $t2] && ![::string match -nocase "*critical*" $t1]} {
        set pick $r2; set back $r1
    } else {
        set pick $r1; set back $r2
    }
    ::hx_log "radio texts: '$t1' / '$t2'  -> pick $pick"
    set before [::hx_legend_text]
    set rc [::catch {$pick invoke} msg]
    ::hx_log "radio invoke rc=$rc msg=$msg"
    for {set i 0} {$i < 50} {incr i} {
        ::update
        if {[::hx_legend_text] ne $before} break
        ::after 100
    }
    ::after 500
    ::update
    set txt [::hx_legend_text]
    ::hx_log "legend:$txt"
    ::catch {::hx_log "flb1.label='[$ns.flb1.label cget -text]'  flb1.unit='[$ns.flb1.unit cget -text]'"}
    set id ""
    ::regexp {N([0-9]+)} $txt -> id
    ::hx_apply_crit
    ::hx_capture "MOSTCRIT_$id"
    # tra lai che do DETAILED
    ::catch {$back invoke}
    ::update
}

# ---------- ket thuc / chay ----------
proc ::hx_finish {} {
    set rc [::catch {.resultHaighDiagramDialog.frButtons.close invoke} msg]
    ::hx_log "close invoke rc=$rc msg=$msg"
    if {$rc} { ::catch {.resultHaighDiagramDialog.frButtons.ok invoke} }
    ::hx_log "done"
    ::catch {::close $::hx_fh}
}

proc ::hx_run {} {
    set d .resultHaighDiagramDialog
    set g $d.childsite.lf1.graph.graph
    set ns $d.childsite.nodeSelector
    if {![::winfo exists $g] || ![::winfo ismapped $g]} {
        incr ::hx_tries
        ::hx_log "graph chua hien (lan $::hx_tries)"
        if {$::hx_tries < 20} { ::after 500 ::hx_run; return }
        ::hx_log "bo cuoc: hop thoai Haigh khong mo duoc"
        ::hx_finish
        return
    }
    ::hx_log "dialog is up: state=[::wm state $d] grab=[::grab current]"
    ::hx_log "== legend functions =="
    ::hx_dump_fn $d.childsite.lf1.legend
    ::hx_log "== legend binds =="
    set cv $d.childsite.lf1.legend.cv
    foreach w [list $cv $cv.lb1 $cv.lb2 $cv.lb3 $cv.lb4 $cv.leg1 $cv.leg2 $cv.leg3 $cv.leg4] {
        ::catch {::hx_dump_binds $w}
    }
    ::catch {::hx_dump_legend}
    ::catch {::hx_dump_elements}
    # dam bao dang o che do DETAILED RESULTS
    ::catch {::hx_log "radio texts: '[$ns.rbs1.rb1 cget -text]' / '[$ns.rbs2.rb2 cget -text]'"}
    ::catch {$ns.rbs2.rb2 invoke}
    ::update
    foreach node $::hx_nodes {
        if {[::catch {::hx_one $node} err]} { ::hx_log "node $node ERROR: $err" }
    }
    if {$::hx_do_most_critical} {
        if {[::catch {::hx_most_critical} err]} { ::hx_log "most critical ERROR: $err" }
    }
    ::hx_finish
}

# ---- chay ----
::after 1500 ::hx_run
set rc [::catch {.femfat.hpane.rpane.main_sw.cv.dialogFr.bas-vi.inf.lf1.btHaigh.button invoke} msg]
::hx_log "btHaigh invoke returned rc=$rc msg=$msg"
