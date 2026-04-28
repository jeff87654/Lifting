"""Test: How long does CCS take for the specific |P|=512 combo?"""
import subprocess, os, time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = os.path.join(LIFTING_DIR, "gap_output_ccs_512.log")

gap_commands = f'''
LogTo("{log_file.replace(chr(92), '/')}");

# Load the lifting code (which has the CCS fast path)
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LoadDatabaseIfExists();
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Construct the exact same group the stuck workers have:
# combo [[2,1],[2,1],[4,2],[4,2],[4,3]] for partition [4,4,4,2,2]
# This gives P = C2 x C2 x V4 x V4 x D4, |P|=512

G1 := TransitiveGroup(2, 1);
G2 := TransitiveGroup(2, 1);
G3 := TransitiveGroup(4, 2);
G4 := TransitiveGroup(4, 2);
G5 := TransitiveGroup(4, 3);

# Shift each factor to its own orbit
ShiftPerm := function(g, offset, deg)
    local imgs;
    imgs := List([1..offset+deg], function(x)
        if x <= offset then return x;
        elif x-offset <= deg then return (x-offset)^g + offset;
        else return x;
        fi;
    end);
    return PermList(imgs);
end;

factors := [G1, G2, G3, G4, G5];
degs := [2, 2, 4, 4, 4];
offset := 0;
shifted := [];
for i in [1..5] do
    gens := List(GeneratorsOfGroup(factors[i]), g -> ShiftPerm(g, offset, degs[i]));
    Add(shifted, Group(gens));
    offset := offset + degs[i];
od;

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P: |P| = ", Size(P), ", degree = ", NrMovedPoints(P), "\\n");
Print("IsAbelian(P) = ", IsAbelian(P), "\\n");

# Test 1: CCS timing
Print("\\nTest 1: ConjugacyClassesSubgroups(P)\\n");
t0 := Runtime();
ccs := ConjugacyClassesSubgroups(P);
t1 := Runtime();
Print("CCS: ", Length(ccs), " classes in ", t1-t0, "ms\\n");

# Count FPF
orbits := List(shifted, G -> MovedPoints(G));
fpfCount := 0;
for cc in ccs do
    H := Representative(cc);
    if ForAll(orbits, function(orb) return IsTransitive(H, orb); end) then
        fpfCount := fpfCount + 1;
    fi;
od;
Print("FPF classes: ", fpfCount, "\\n");

# Test 2: AllSubgroups timing
Print("\\nTest 2: AllSubgroups(P)\\n");
t0 := Runtime();
allsub := AllSubgroups(P);
t2 := Runtime();
Print("AllSubgroups: ", Length(allsub), " subgroups in ", t2-t0, "ms\\n");

LogTo();
QUIT;
'''

script_file = os.path.join(LIFTING_DIR, "temp_test_ccs_512.g")
with open(script_file, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_ccs_512.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting CCS test for |P|=512 at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=7200)
print(f"Finished at {time.strftime('%H:%M:%S')}, exit code: {process.returncode}")

with open(log_file, "r") as f:
    log = f.read()
for line in log.strip().split('\n'):
    print(line)
