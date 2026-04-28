"""Test whether AllHomomorphismClasses(C, A_5) is deterministic for the
(Q, M_bar) that GAH undercounts on. If the count varies across random
seeds, we've found the source of GAH's state-sensitivity bug.
"""
import subprocess, os

LOG = "C:/Users/jeffr/Downloads/Lifting/test_allhom_det.log"
DUMP = "C:/Users/jeffr/Downloads/Lifting/diag_combo6_diffs.g"

code = r'''
LogTo("__LOG__");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("__DUMP__");

r := DIAG_GAH_DIFFERS_LOADED[1];
Q := Group(r.Q_gens);
M_bar := Group(r.M_bar_gens);
SetSize(Q, r.Q_size);
SetSize(M_bar, r.M_bar_size);
C := Centralizer(Q, M_bar);

Print("[det] |Q|=", Size(Q), " |M_bar|=", Size(M_bar),
      " |C|=", Size(C), "\n");
Print("[det] gens(C) = ", GeneratorsOfGroup(C), "\n");
Print("[det] |gens(C)| = ", Length(GeneratorsOfGroup(C)), "\n\n");

# Call AllHomomorphismClasses 10 times with reset random seed, see if count varies.
counts := [];
for trial in [1..10] do
    Reset(GlobalMersenneTwister, trial * 17);
    h := AllHomomorphismClasses(C, M_bar);
    Add(counts, Length(h));
    Print("[det] trial ", trial, " (seed ", trial*17, "): ",
          Length(h), " hom classes\n");
od;
Print("[det] count summary: ", counts, "\n");
Print("[det] all same? ", Length(Set(counts)) = 1, "\n\n");

# Also try with different generating sets of C.
Print("[det] === testing with different gens of C ===\n");
sg := SmallGeneratingSet(C);
Print("[det] SmallGeneratingSet(C) = ", sg, " (len ", Length(sg), ")\n");
mg := MinimalGeneratingSet(C);
Print("[det] MinimalGeneratingSet(C) = ", mg, " (len ", Length(mg), ")\n");
C_sm := Group(sg);
SetSize(C_sm, Size(C));
C_mg := Group(mg);
SetSize(C_mg, Size(C));
Print("[det] AllHomClasses(C_sm, M_bar) = ", Length(AllHomomorphismClasses(C_sm, M_bar)), "\n");
Print("[det] AllHomClasses(C_mg, M_bar) = ", Length(AllHomomorphismClasses(C_mg, M_bar)), "\n");

LogTo();
QUIT;
'''.replace("__LOG__", LOG).replace("__DUMP__", DUMP)

tmp_path = r"C:\Users\jeffr\Downloads\Lifting\tmp_test_allhom_det.g"
with open(tmp_path, "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_test_allhom_det.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print(f"Log: {LOG}")
