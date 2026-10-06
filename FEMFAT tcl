# femfat_probe.tcl  -- CHI DOC thong tin, khong thay doi gi trong FEMFAT
# Cach dung: them dong sau vao CUOI file .ffj (sau StartAnalysisLoop):
#     source /duong/dan/femfat_probe.tcl
# Ket qua: file femfat_probe.txt trong thu muc lam viec cua FEMFAT.

if {![info exists ::probe_out]} { set ::probe_out femfat_probe.txt }
set ::probe_fh [open $::probe_out w]

catch {puts $::probe_fh "tcl=[info patchlevel]  tk=$::tk_patchLevel"}
catch {puts $::probe_fh "packages: [lsort [package names]]"}

# 1) Tim ten lenh/namespace lien quan (ten van thay duoc du code bi bien dich)
foreach pat {*aigh* *istory* *ostscript* *xport* *napshot* *icture* *rint* *mage* *hart* *lot*} {
    catch {puts $::probe_fh "cmd ::$pat : [info commands ::$pat]"}
}
foreach ns [namespace children ::] {
    puts $::probe_fh "namespace $ns"
    foreach pat {*aigh* *istory* *xport* *icture* *hart*} {
        catch {puts $::probe_fh "cmd ${ns}::$pat : [info commands ${ns}::$pat]"}
    }
}

# 2) Duyet cay widget + menu (menu -> lenh dung de mo hop thoai History/Result)
proc probe_walk {w} {
    set cls [winfo class $w]
    set line "$w  class=$cls  mapped=[winfo ismapped $w]"
    foreach opt {-textvariable -variable -command} {
        if {![catch {$w cget $opt} v] && $v ne ""} { append line "  $opt=$v" }
    }
    puts $::probe_fh $line
    if {$cls eq "Canvas"} {
        puts $::probe_fh "    canvas items=[llength [$w find all]]"
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
                    puts $::probe_fh "    entry#$i $t \"$lab\" -> $cmd"
                }
            }
        }
    }
    foreach c [winfo children $w] { probe_walk $c }
}

puts $::probe_fh "---- widget tree ----"
if {[catch {probe_walk .} err]} { puts $::probe_fh "walk error: $err" }
close $::probe_fh
