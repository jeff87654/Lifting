"""
Check if within-combo N-dedup gives different counts for ON vs OFF.

The combo T(6,5)xT(6,8)xT(3,2) produces:
- 26 raw results with orbital OFF
- 14 raw results with orbital ON

After N-dedup within the combo, do we get different N-class counts?
If yes, that's the bug. If no, the bug is in cross-combo interaction.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/combo_ndedup.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Set up combo
factors := [TransitiveGroup(6, 5), TransitiveGroup(6, 8), TransitiveGroup(3, 2)];
shifted := [];
offs := [];
off := 0;
for k in [1..3] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
N := BuildConjugacyTestGroup(15, [6, 6, 3]);

# Get raw results with OFF
Print("\\n=== OFF raw results ===\\n");
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();
off_raw := FindFPFClassesByLifting(P, shifted, offs, N);
Print("OFF raw: ", Length(off_raw), "\\n");

# N-dedup the OFF results
off_deduped := [];
for i in [1..Length(off_raw)] do
    found := false;
    for j in [1..Length(off_deduped)] do
        if Size(off_raw[i]) = Size(off_deduped[j]) then
            if RepresentativeAction(N, off_raw[i], off_deduped[j]) <> fail then
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        Add(off_deduped, off_raw[i]);
    fi;
od;
Print("OFF after N-dedup: ", Length(off_deduped), "\\n");

# Get raw results with ON
Print("\\n=== ON raw results ===\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();
on_raw := FindFPFClassesByLifting(P, shifted, offs, N);
Print("ON raw: ", Length(on_raw), "\\n");

# N-dedup the ON results
on_deduped := [];
for i in [1..Length(on_raw)] do
    found := false;
    for j in [1..Length(on_deduped)] do
        if Size(on_raw[i]) = Size(on_deduped[j]) then
            if RepresentativeAction(N, on_raw[i], on_deduped[j]) <> fail then
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        Add(on_deduped, on_raw[i]);
    fi;
od;
Print("ON after N-dedup: ", Length(on_deduped), "\\n");

# Compare: are all ON N-classes present in OFF N-classes?
Print("\\n=== Cross-comparison ===\\n");
for i in [1..Length(on_deduped)] do
    found := false;
    for j in [1..Length(off_deduped)] do
        if Size(on_deduped[i]) = Size(off_deduped[j]) then
            if RepresentativeAction(N, on_deduped[i], off_deduped[j]) <> fail then
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        Print("ON class ", i, " (|H|=", Size(on_deduped[i]),
              ") NOT in OFF classes!\\n");
    fi;
od;

for i in [1..Length(off_deduped)] do
    found := false;
    for j in [1..Length(on_deduped)] do
        if Size(off_deduped[i]) = Size(on_deduped[j]) then
            if RepresentativeAction(N, off_deduped[i], on_deduped[j]) <> fail then
                found := true;
                break;
            fi;
        fi;
    od;
    if not found then
        Print("OFF class ", i, " (|H|=", Size(off_deduped[i]),
              ") NOT in ON classes!\\n");
    fi;
od;

Print("\\nDone.\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_combo_ndedup.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_combo_ndedup.g"

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
        if any(kw in line for kw in ['===', 'raw', 'N-dedup', 'NOT in',
                                      'Done', 'class']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
