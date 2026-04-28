"""
Recompute the two affected partitions [5,4,4,2] and [6,6,3] with orbital OFF.
Writes generator files in same format as parallel_s15/gens/.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/recompute_affected.log"
gens_dir = "C:/Users/jeffr/Downloads/Lifting/parallel_s15/gens"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# DISABLE orbital to get correct counts
USE_H1_ORBITAL := false;

partitions := [ [5,4,4,2], [6,6,3] ];

for part in partitions do
    Print("\\n=== Computing ", part, " ===\\n");
    FPF_SUBDIRECT_CACHE := rec();
    ClearH1Cache();

    fpf_classes := FindFPFClassesForPartition(15, part);
    Print("Count: ", Length(fpf_classes), "\\n");

    # Save generators
    partStr := JoinStringsWithSeparator(List(part, String), "_");
    genFile := Concatenation("{gens_dir}", "/gens_", partStr, "_fixed.txt");
    PrintTo(genFile, "");
    for _h_idx in [1..Length(fpf_classes)] do
        _gens := List(GeneratorsOfGroup(fpf_classes[_h_idx]),
                      g -> ListPerm(g, 15));
        AppendTo(genFile, String(_gens), "\\n");
    od;
    Print("Saved to ", genFile, "\\n");
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_recompute_affected.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_recompute_affected.g"

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

stdout, stderr = process.communicate(timeout=36000)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['===', 'Count', 'Saved', 'Final count',
                                      'Time:', 'Error']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
