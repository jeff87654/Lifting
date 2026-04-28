"""Per-layer diagnostic v5 for orbital bug.
Tests the [6,5] x [6,8] x [3,2] combo with orbital ON vs OFF
to verify the affine H^1 fix resolves the mismatch."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = "C:/Users/jeffr/Downloads/Lifting/orbital_layer_diag5.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Build combo: [6,5] x [6,8] x [3,2]
f1 := TransitiveGroup(6, 5);
f2 := TransitiveGroup(6, 8);
f3 := TransitiveGroup(3, 2);

shifted := [];
offs := [];
off := 0;
for factor in [f1, f2, f3] do
    Add(offs, off);
    degree := NrMovedPoints(factor);
    shift_perm := MappingPermListList([1..degree], [off+1..off+degree]);
    Add(shifted, Group(List(GeneratorsOfGroup(factor), g -> g^shift_perm)));
    off := off + degree;
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P = ", StructureDescription(P), ", |P| = ", Size(P), "\\n");

# ========== RUN 1: Orbital OFF ==========
Print("\\n========== ORBITAL OFF ==========\\n");
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
results_off := FindFPFClassesByLifting(P, shifted, offs);
Print("Orbital OFF: ", Length(results_off), " FPF subdirects\\n");

# ========== RUN 2: Orbital ON ==========
Print("\\n========== ORBITAL ON (with affine fix) ==========\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
results_on := FindFPFClassesByLifting(P, shifted, offs);
Print("Orbital ON: ", Length(results_on), " FPF subdirects\\n");

# ========== COMPARISON ==========
Print("\\n========== COMPARISON ==========\\n");
Print("OFF: ", Length(results_off), ", ON: ", Length(results_on), "\\n");
if Length(results_off) <> Length(results_on) then
    Print("DELTA: ", Length(results_off) - Length(results_on), "\\n");
else
    Print("MATCH! Both give ", Length(results_off), " FPF subdirects\\n");
fi;

LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_layer_diag5.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_layer_diag5.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting diagnostic v5 at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=7200)
print(f"Finished at {time.strftime('%H:%M:%S')}")

if stderr.strip():
    err_lines = [l for l in stderr.split('\n') if 'Error' in l or 'error' in l.lower()]
    if err_lines:
        print(f"ERRORS:\n" + "\n".join(err_lines[:10]))

log_path = log_file.replace("/", os.sep)
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    lines = log.split('\n')
    for line in lines:
        if any(x in line for x in ['==========', 'DELTA', 'MATCH', 'Orbital',
                                     'P = ', 'orbital', 'H^1']):
            print(line)
else:
    print("No log file found")
    print("STDOUT:", stdout[-2000:])
