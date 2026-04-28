"""Check whether AllHomomorphismClasses returns different rep SETS across
seeds (count=24 in all trials, but the actual representative homs might
differ in which Inn-class element they pick).
"""
import subprocess, os

LOG = "C:/Users/jeffr/Downloads/Lifting/test_allhom_reps.log"
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

Print("[reps] |C|=", Size(C), " gens(C)=", GeneratorsOfGroup(C), "\n\n");

# Compute hom-image sets for two seeds.
Reset(GlobalMersenneTwister, 17);
h17 := AllHomomorphismClasses(C, M_bar);
Print("[reps] seed 17: ", Length(h17), " hom classes\n");
imgs17 := Set(List(h17, h -> List(GeneratorsOfGroup(C), c -> Image(h, c))));
Print("[reps] seed 17 distinct image-tuples: ", Length(imgs17), "\n");

Reset(GlobalMersenneTwister, 34);
h34 := AllHomomorphismClasses(C, M_bar);
Print("[reps] seed 34: ", Length(h34), " hom classes\n");
imgs34 := Set(List(h34, h -> List(GeneratorsOfGroup(C), c -> Image(h, c))));
Print("[reps] seed 34 distinct image-tuples: ", Length(imgs34), "\n");

# Compare which image-tuples appear in seed 17 but not 34 (and vice versa).
only17 := Filtered(imgs17, t -> not t in imgs34);
only34 := Filtered(imgs34, t -> not t in imgs17);
Print("[reps] in seed-17 but not seed-34: ", Length(only17), "\n");
Print("[reps] in seed-34 but not seed-17: ", Length(only34), "\n");
both := Filtered(imgs17, t -> t in imgs34);
Print("[reps] in BOTH: ", Length(both), "\n");

# For the missing K's hom (gens map: (15,16),(13,14),(11,12) -> 1; (3,4,5)
# -> (8,10,9); (2,4,5) -> (7,10,9); (1,4,5) -> (6,10,9)), check if it's in
# either rep set.
target_imgs := [(), (), (), (8,10,9), (7,10,9), (6,10,9)];
Print("\n[reps] target image-tuple (missing K's hom):\n");
Print("  ", target_imgs, "\n");

# Need to check Inn(M_bar)-conjugacy: target ~ rep iff exists m in M_bar with
# Inn(m) o rep = target, ie target[i] = m * rep[i] * m^-1 for all i.
matches := function(target, rep)
    local m;
    for m in M_bar do
        if ForAll([1..Length(target)],
                  i -> target[i] = m * rep[i] * m^-1) then
            return true;
        fi;
    od;
    return false;
end;

t17 := Filtered([1..Length(imgs17)], i -> matches(target_imgs, imgs17[i]));
Print("[reps] target Inn-equivalent to imgs17[i] for i in: ", t17, "\n");
t34 := Filtered([1..Length(imgs34)], i -> matches(target_imgs, imgs34[i]));
Print("[reps] target Inn-equivalent to imgs34[i] for i in: ", t34, "\n");

LogTo();
QUIT;
'''.replace("__LOG__", LOG).replace("__DUMP__", DUMP)

tmp_path = r"C:\Users\jeffr\Downloads\Lifting\tmp_test_allhom_reps.g"
with open(tmp_path, "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_test_allhom_reps.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print(f"Log: {LOG}")
