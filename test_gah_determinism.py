"""Test whether GAH is deterministic across multiple runs in the same
process — establishes whether the bug is intrinsic randomness or external
state-sensitivity.  Also tries running GAH with various perturbations of
the (Q, M_bar) state (cached attributes, generator orderings).
"""
import subprocess, os

LOG = "C:/Users/jeffr/Downloads/Lifting/test_gah_det.log"
DUMP = "C:/Users/jeffr/Downloads/Lifting/diag_combo6_diffs.g"

code = r'''
LogTo("__LOG__");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("__DUMP__");

r := DIAG_GAH_DIFFERS_LOADED[1];
Print("[gd] divergent record: GAH=", r.gah_count, " NSCR=", r.nscr_count, "\n\n");

# Baseline trials with fresh objects.
Print("[gd] === fresh Q/M_bar each call ===\n");
for trial in [1..5] do
    Reset(GlobalMersenneTwister, trial * 17);
    Q := Group(r.Q_gens);
    M_bar := Group(r.M_bar_gens);
    SetSize(Q, r.Q_size);
    SetSize(M_bar, r.M_bar_size);
    C := Centralizer(Q, M_bar);
    g := GeneralAutHomComplements(Q, M_bar, C);
    Print("[gd] trial ", trial, " (seed ", trial*17, "): GAH = ",
          Length(g), " classes\n");
od;

Print("\n[gd] === pre-compute Pcgs(M_bar) ===\n");
Q := Group(r.Q_gens);
M_bar := Group(r.M_bar_gens);
SetSize(Q, r.Q_size);
SetSize(M_bar, r.M_bar_size);
# Force computation of various M_bar attributes.
Print("[gd] IsSolvable(M_bar) = ", IsSolvable(M_bar), "\n");
ConjugacyClasses(M_bar);;
g := GeneralAutHomComplements(Q, M_bar, Centralizer(Q, M_bar));
Print("[gd] after pre-compute: GAH = ", Length(g), " classes\n");

Print("\n[gd] === pre-compute Pcgs(C) ===\n");
Q := Group(r.Q_gens);
M_bar := Group(r.M_bar_gens);
SetSize(Q, r.Q_size);
SetSize(M_bar, r.M_bar_size);
C := Centralizer(Q, M_bar);
Print("[gd] IsSolvable(C) = ", IsSolvable(C), "\n");
ConjugacyClasses(C);;
g := GeneralAutHomComplements(Q, M_bar, C);
Print("[gd] after pre-compute Pcgs(C): GAH = ", Length(g), " classes\n");

Print("\n[gd] === reorder C generators ===\n");
Q := Group(r.Q_gens);
M_bar := Group(r.M_bar_gens);
SetSize(Q, r.Q_size);
SetSize(M_bar, r.M_bar_size);
C0 := Centralizer(Q, M_bar);
gC := GeneratorsOfGroup(C0);
Print("[gd] orig gens(C) = ", gC, "\n");
gC_rev := Reversed(gC);
C_rev := Group(gC_rev);
SetSize(C_rev, Size(C0));
g := GeneralAutHomComplements(Q, M_bar, C_rev);
Print("[gd] reversed gens(C): GAH = ", Length(g), " classes\n");

Print("\n[gd] === scrambled C generators (use SmallGeneratingSet) ===\n");
sg := SmallGeneratingSet(C0);
Print("[gd] SmallGeneratingSet(C) = ", sg, "\n");
C_sm := Group(sg);
SetSize(C_sm, Size(C0));
g := GeneralAutHomComplements(Q, M_bar, C_sm);
Print("[gd] SmallGen-built C: GAH = ", Length(g), " classes\n");

Print("\n[gd] === reorder Q generators (reversed) ===\n");
Q_rev := Group(Reversed(r.Q_gens));
SetSize(Q_rev, r.Q_size);
M_bar2 := Group(r.M_bar_gens);
SetSize(M_bar2, r.M_bar_size);
C_qrev := Centralizer(Q_rev, M_bar2);
Print("[gd] gens(C) with reversed-Q = ", GeneratorsOfGroup(C_qrev), "\n");
g := GeneralAutHomComplements(Q_rev, M_bar2, C_qrev);
Print("[gd] reversed-Q: GAH = ", Length(g), " classes\n");

LogTo();
QUIT;
'''.replace("__LOG__", LOG).replace("__DUMP__", DUMP)

tmp_path = r"C:\Users\jeffr\Downloads\Lifting\tmp_test_gah_det.g"
with open(tmp_path, "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_test_gah_det.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print(f"Log: {LOG}")
