# femfat_probe2.tcl -- CHI DOC thong tin. Chay o pham vi global (xem run_probe2.ffj)
if {![info exists ::probe_out]} { set ::probe_out femfat_probe2.txt }
set ::probe_fh [::open $::probe_out w]
proc ::probe_p {s} { ::puts $::probe_fh $s }

catch {::probe_p "tcl=[::info patchlevel]  tk=$::tk_patchLevel"}
catch {::probe_p "packages: [::lsort [::package names]]"}

# 1) [incr Tcl]: danh sach class va object, method cua object lien quan
::probe_p "---- itcl classes ----"
if {![catch {::itcl::find classes} classes]} {
    ::probe_p "count=[::llength $classes]"
    ::probe_p $classes
} else { ::probe_p "itcl::find classes error: $classes" }

::probe_p "---- itcl objects ----"
if {![catch {::itcl::find objects} objs]} {
    ::probe_p "count=[::llength $objs]"
    foreach o $objs {
        set cls ""
        catch {set cls [$o info class]}
        ::probe_p "obj $o  class=$cls"
        if {[::regexp -nocase {doc0|aigh|histor|chart|plot|graph|diagram|snap|export|result|visual} "$o $cls"]} {
            catch {foreach f [$o info function] { ::probe_p "      fn $f" }}
        }
    }
} else { ::probe_p "itcl::find objects error: $objs" }

# 2) Ten lenh gan voi Haigh/History/Export
::probe_p "---- commands ----"
foreach pat {*aigh* *istory* *ostscript* *xport* *napshot* *icture* *rint* *mage* *hart* *lot*} {
    catch {::probe_p "cmd ::$pat : [::info commands ::$pat]"}
}

# 3) Cay widget + menu
proc ::probe_walk {w} {
    set cls [::winfo class $w]
    set line "$w  class=$cls  mapped=[::winfo ismapped $w]"
    foreach opt {-textvariable -variable -command} {
        if {![::catch {$w cget $opt} v] && $v ne ""} { append line "  $opt=$v" }
    }
    ::probe_p $line
    if {$cls eq "Canvas"} {
        ::probe_p "    canvas items=[::llength [$w find all]]"
    }
    if {$cls eq "Menu"} {
        set last [$w index end]
        if {$last ne "none"} {
            for {set i 0} {$i <= $last} {incr i} {
                set t [$w type $i]
                if {$t in {command cascade checkbutton radiobutton}} {
                    set lab ""; set cmd ""
                    catch {set lab [$w entrycget $i -label]}
                    catch {set cmd [$w entrycget $i -command]}
                    ::probe_p "    entry#$i $t \"$lab\" -> $cmd"
                }
            }
        }
    }
    foreach c [::winfo children $w] { ::probe_walk $c }
}
::probe_p "---- widget tree ----"
if {[::catch {::probe_walk .} err]} { ::probe_p "walk error: $err" }
::close $::probe_fh
