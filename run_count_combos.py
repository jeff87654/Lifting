"""Count combos for [6,6,3] and check cross-combo dedup."""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/count_combos.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Count combos for [6,6,3]
Print("Transitive groups of degree 6: ", NrTransitiveGroups(6), "\\n");
Print("Transitive groups of degree 3: ", NrTransitiveGroups(3), "\\n");

# List all valid combos (non-decreasing for equal-degree parts)
combos := [];
for i in [1..NrTransitiveGroups(6)] do
    for j in [i..NrTransitiveGroups(6)] do
        for k in [1..NrTransitiveGroups(3)] do
            Add(combos, [i, j, k]);
        od;
    od;
od;
Print("Total combos: ", Length(combos), "\\n");

# For each combo, run lifting with ON and OFF, report raw counts
N := BuildConjugacyTestGroup(15, [6, 6, 3]);

for combo in combos do
    factors := [TransitiveGroup(6, combo[1]),
                TransitiveGroup(6, combo[2]),
                TransitiveGroup(3, combo[3])];
    shifted := [];
    offs := [];
    off := 0;
    for m in [1..3] do
        Add(offs, off);
        Add(shifted, ShiftGroup(factors[m], off));
        off := off + NrMovedPoints(factors[m]);
    od;
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));

    # OFF
    USE_H1_ORBITAL := false;
    FPF_SUBDIRECT_CACHE := rec();
    ClearH1Cache();
    off_result := FindFPFClassesByLifting(P, shifted, offs, N);

    # ON
    USE_H1_ORBITAL := true;
    FPF_SUBDIRECT_CACHE := rec();
    ClearH1Cache();
    on_result := FindFPFClassesByLifting(P, shifted, offs, N);

    if Length(off_result) <> Length(on_result) then
        Print("DIFF combo T(6,", combo[1], ")xT(6,", combo[2], ")xT(3,", combo[3],
              "): OFF=", Length(off_result), " ON=", Length(on_result), "\\n");
    fi;
od;

Print("\\nDone.\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_count_combos.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_count_combos.g"

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

stdout, stderr = process.communicate(timeout=7200)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['DIFF', 'Total combos', 'Transitive',
                                      'Done']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
