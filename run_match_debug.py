"""
Match exactly what run_debug_combo2.py does, but also print result sizes
and check N-classes.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/match_debug.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Build the combo
T63_2 := TransitiveGroup(3, 2);
T66_5 := TransitiveGroup(6, 5);
T66_8 := TransitiveGroup(6, 8);

factors := [T66_5, T66_8, T63_2];
shifted := [];
offs := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
N := BuildConjugacyTestGroup(15, [6, 6, 3]);

# Run 1: orbital ON, with cache clearing (like debug_combo2)
Print("=== Run 1: orbital ON (with cache clear) ===\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
result_orb := FindFPFClassesByLifting(P, shifted, offs, N);
Print("Result: ", Length(result_orb), " sizes: ", List(result_orb, Size), "\\n\\n");

# Run 2: orbital ON, without cache clearing
Print("=== Run 2: orbital ON (no cache clear) ===\\n");
USE_H1_ORBITAL := true;
ClearH1Cache();
result_orb2 := FindFPFClassesByLifting(P, shifted, offs);
Print("Result: ", Length(result_orb2), " sizes: ", List(result_orb2, Size), "\\n\\n");

# Run 3: orbital OFF
Print("=== Run 3: orbital OFF ===\\n");
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
result_no := FindFPFClassesByLifting(P, shifted, offs, N);
Print("Result: ", Length(result_no), "\\n\\n");

# N-dedup
DedupUnderN := function(results, N_group)
    local reps, H, found, i;
    reps := [];
    for H in results do
        found := false;
        for i in [1..Length(reps)] do
            if Size(H) = Size(reps[i]) then
                if RepresentativeAction(N_group, H, reps[i]) <> fail then
                    found := true;
                    break;
                fi;
            fi;
        od;
        if not found then
            Add(reps, H);
        fi;
    od;
    return reps;
end;

Print("Dedup run 1: ", Length(result_orb), " -> ", Length(DedupUnderN(result_orb, N)), "\\n");
Print("Dedup run 2: ", Length(result_orb2), " -> ", Length(DedupUnderN(result_orb2, N)), "\\n");
Print("Dedup run 3: ", Length(result_no), " -> ", Length(DedupUnderN(result_no, N)), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_match_debug.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_match_debug.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting at {time.strftime('%H:%M:%S')}")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    env=env, cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=600)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['Run', 'Result', 'Dedup', 'orbital', 'sizes']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
