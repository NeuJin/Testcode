# femfat_probe3.tcl -- thu chu ky method + thu chup anh do thi Haigh (BLT snap / postscript)
# Chay o pham vi global (xem run_probe3.ffj). Chi tao file trong thu muc D:/femfat_probe.
if {![info exists ::probe_out]} { set ::probe_out femfat_probe3.txt }
set ::probe_dir [::file dirname $::probe_out]
set ::probe_fh [::open $::probe_out w]
proc ::probe_p {s} { ::puts $::probe_fh $s; ::flush $::probe_fh }
proc ::probe_trunc {s n} {
    if {[::string length $s] > $n} { return "[::string range $s 0 $n]...(truncated)" }
    return $s
}
proc ::probe_obj {o} {
    ::probe_p ""
    ::probe_p "=== OBJECT $o ==="
    if {![::catch {$o info class} c]} { ::probe_p "class: $c" }
    if {![::catch {$o info heritage} h]} { ::probe_p "heritage: $h" }
    if {![::catch {$o info function} fl]} {
        foreach f $fl {
            set sig ""
            ::catch {set sig [$o info function $f -protection -type -args]}
            set body ""
            if {[::regexp {apply|print|update|dialog|invoke|Pressed|Apply|setValue|getValue|snap|camera|setNode|node} $f]} {
                ::catch {set body [$o info function $f -body]}
            }
            ::probe_p "fn $f | $sig | [::probe_trunc $body 300]"
        }
    }
    if {![::catch {$o info variable} vl]} {
        foreach v $vl {
            set val ""
            ::catch {set val [$o info variable $v -value]}
            ::probe_p "var $v = [::probe_trunc $val 150]"
        }
    }
}

set ::probe_objs {
    .resultHaighDiagramDialog
    .resultHaighDiagramDialog.childsite.lf1.graph
    .resultHaighDiagramDialog.childsite.nodeSelector
    .resultHaighDiagramDialog.childsite.nodeSelector.si01
    .resultHaighDiagramDialog.childsite.nodeSelector.rbs1
    .resultHaighDiagramDialog.childsite.nodeSelector.rbs2
    .resultHaighDiagramDialog.childsite.lf1.legend
    .femfat.hpane.rpane.main_sw.cv.dialogFr.bas-vi.inf.lf1.btHaigh
    ::printDialog ::printer ::specimenHaighDiagram ::doc0
}
foreach o $::probe_objs {
    if {[::catch {::probe_obj $o} e]} { ::probe_p "obj $o error: $e" }
}
foreach cls {::Femfat::Visualization ::Femfat::MainResultDialog ::Femfat::PrintDialog ::Femfat::ResultSNCurve} {
    if {![::catch {::itcl::find objects -class $cls} found]} {
        ::probe_p ""
        ::probe_p "#### objects of class $cls: $found"
        foreach o $found {
            if {[::catch {::probe_obj $o} e]} { ::probe_p "obj $o error: $e" }
        }
    }
}

# ---- BLT / Tk ----
set g .resultHaighDiagramDialog.childsite.lf1.graph.graph
::probe_p ""
::probe_p "==== BLT / Tk ===="
::catch {::probe_p "BLT=[::package provide BLT]  Img=[::package provide Img]"}
::catch {::probe_p "image types: [::image types]"}
::catch {::probe_p "dialog state: [::wm state .resultHaighDiagramDialog]  grab: [::grab current]"}
::catch {::probe_p "graph exists=[::winfo exists $g] mapped=[::winfo ismapped $g] size=[::winfo width $g]x[::winfo height $g]"}
foreach op {snap postscript} {
    ::catch {$g $op} msg
    ::probe_p "usage $op: $msg"
}
::catch {::probe_p "postscript options: [$g postscript configure]"}
::catch {::probe_p "elements: [$g element names]"}
::catch {::probe_p "markers: [$g marker names]"}
foreach w {ok cancel apply camera close stop yes no continue} {
    set p .resultHaighDiagramDialog.frButtons.$w
    set line "button $w:"
    foreach opt {-text -image -command -state} {
        ::catch {append line " $opt=[$p cget $opt]"}
    }
    ::catch {append line " binds=[::bind $p]"}
    ::probe_p $line
}

# ---- Thu chup anh neu do thi dang hien thi ----
if {[::catch {::winfo ismapped $g} m] == 0 && $m} {
    ::probe_p ""
    ::probe_p "==== snapshot test (graph is mapped) ===="
    set rc [::catch {
        ::image create photo probe_img
        $g snap probe_img
        probe_img write [::file join $::probe_dir test_haigh.png] -format png
    } msg]
    ::probe_p "snap->png rc=$rc msg=$msg"
    ::catch {::image delete probe_img}
    set rc [::catch {$g postscript output [::file join $::probe_dir test_haigh.ps]} msg]
    ::probe_p "postscript rc=$rc msg=$msg"
} else {
    ::probe_p "graph not mapped -> bo qua snapshot test (hay mo hop thoai Haigh truoc khi probe chay)"
}
::close $::probe_fh
