"""
Test if FindFPFClassesByLifting is deterministic.
Run 3 times with orbital ON, compare results.
"""

import subprocess
import os
import time

for trial in range(1, 4):
    log_file = f"C:/Users/jeffr/Downloads/Lifting/determinism_{trial}.log"

    gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

T66_5 := TransitiveGroup(6, 5);
T66_8 := TransitiveGroup(6, 8);
T63_2 := TransitiveGroup(3, 2);
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

USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
ResetH1TimingStats();

result := FindFPFClassesByLifting(P, shifted, offs);
Print("Result: ", Length(result), "\\n");
Print("Sizes: ", SortedList(List(result, Size)), "\\n");

LogTo();
QUIT;
'''

    with open(r"C:\Users\jeffr\Downloads\Lifting\temp_determinism.g", "w") as f:
        f.write(gap_commands)

    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_determinism.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=env, cwd=gap_runtime
    )

    stdout, stderr = process.communicate(timeout=600)

    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()

    for line in log.split('\n'):
        if 'Result:' in line or 'Sizes:' in line or 'orbital' in line.lower():
            print(f"Trial {trial}: {line.strip()}")
