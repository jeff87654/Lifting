"""
Test [6,6,3]: orbital ON with cache ON vs orbital ON with cache OFF.
If the cache is causing wrong results, disabling it should fix the count.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/cache_disabled_test.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Run 1: orbital ON, cache ON (the default)
Print("=== Run 1: orbital ON, cache ON ===\\n");
USE_H1_ORBITAL := true;
H1_CACHE_ENABLED := true;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();
t0 := Runtime();
result1 := FindFPFClassesForPartition(15, [6, 6, 3]);
Print("Result 1 (cache ON): ", Length(result1), " classes (",
      (Runtime()-t0)/1000.0, "s)\\n\\n");

# Run 2: orbital ON, cache OFF
Print("=== Run 2: orbital ON, cache OFF ===\\n");
USE_H1_ORBITAL := true;
H1_CACHE_ENABLED := false;
FPF_SUBDIRECT_CACHE := rec();
ClearH1Cache();
t0 := Runtime();
result2 := FindFPFClassesForPartition(15, [6, 6, 3]);
Print("Result 2 (cache OFF): ", Length(result2), " classes (",
      (Runtime()-t0)/1000.0, "s)\\n\\n");

Print("Difference: ", Length(result1) - Length(result2), "\\n");

if Length(result1) <> Length(result2) then
    Print("\\n*** COUNT DIFFERS! Cache is the likely culprit! ***\\n");

    # Find which classes differ
    N := BuildConjugacyTestGroup(15, [6, 6, 3]);

    # Check result2 classes against result1
    missing_from_1 := [];
    for i in [1..Length(result2)] do
        H2 := result2[i];
        found := false;
        for j in [1..Length(result1)] do
            H1 := result1[j];
            if Size(H2) = Size(H1) then
                if RepresentativeAction(N, H2, H1) <> fail then
                    found := true;
                    break;
                fi;
            fi;
        od;
        if not found then
            Add(missing_from_1, i);
            Print("  Class ", i, " in result2 not in result1: |H|=", Size(H2), "\\n");
        fi;
    od;
    Print("Total missing from result1: ", Length(missing_from_1), "\\n");
else
    Print("Counts match! Cache is NOT the culprit.\\n");
fi;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_cache_disabled.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_cache_disabled.g"

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

stdout, stderr = process.communicate(timeout=14400)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['===', 'Result', 'Difference', 'DIFFERS',
                                      'Counts match', 'missing', 'Class', 'Total',
                                      'culprit']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
