"""Test all S12 FPF partitions against brute-force ground truth."""
import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_s12_test.log"

# S12 FPF ground truth from s12_partition_classes_output.txt
ground_truth = {
    "[12]": 301, "[10,2]": 116, "[9,3]": 143, "[8,4]": 1376,
    "[7,5]": 44, "[6,6]": 473, "[8,2,2]": 578, "[7,3,2]": 39,
    "[6,3,3]": 269, "[6,4,2]": 1126, "[5,4,3]": 205, "[5,5,2]": 62,
    "[4,4,4]": 894, "[6,2,2,2]": 285, "[5,3,2,2]": 86,
    "[4,4,2,2]": 932, "[4,3,3,2]": 277, "[3,3,3,3]": 50,
    "[4,2,2,2,2]": 263, "[3,3,2,2,2]": 74, "[2,2,2,2,2,2]": 36,
}

# Build GAP test commands
partitions_gap = []
expected_gap = []
for part_str, count in ground_truth.items():
    partitions_gap.append(part_str)
    expected_gap.append(str(count))

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear caches for clean test
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Load S1-S11 counts needed for S12 partition computation
LIFT_CACHE.("1") := 1;
LIFT_CACHE.("2") := 2;
LIFT_CACHE.("3") := 4;
LIFT_CACHE.("4") := 11;
LIFT_CACHE.("5") := 19;
LIFT_CACHE.("6") := 56;
LIFT_CACHE.("7") := 96;
LIFT_CACHE.("8") := 296;
LIFT_CACHE.("9") := 554;
LIFT_CACHE.("10") := 1593;
LIFT_CACHE.("11") := 3094;

partitions := [{", ".join(partitions_gap)}];
expected := [{", ".join(expected_gap)}];

Print("\\n=== S12 FPF Partition Verification ===\\n\\n");

totalComputed := 0;
totalExpected := 0;
failures := [];

for i in [1..Length(partitions)] do
    part := partitions[i];
    exp := expected[i];

    # Clear FPF cache for each partition to ensure fresh computation
    FPF_SUBDIRECT_CACHE := rec();
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

    t := Runtime();
    result := FindFPFClassesForPartition(12, part);
    elapsed := Runtime() - t;
    got := Length(result);

    totalComputed := totalComputed + got;
    totalExpected := totalExpected + exp;

    if got = exp then
        Print("  PASS ", part, ": ", got, " (", elapsed, "ms)\\n");
    else
        Print("  FAIL ", part, ": got ", got, " expected ", exp, " (diff ", got - exp, ") (", elapsed, "ms)\\n");
        Add(failures, [part, got, exp]);
    fi;
od;

Print("\\n=== Summary ===\\n");
Print("Total computed: ", totalComputed, "\\n");
Print("Total expected: ", totalExpected, "\\n");
Print("Difference: ", totalComputed - totalExpected, "\\n");
Print("Failures: ", Length(failures), "\\n");
for f in failures do
    Print("  ", f[1], ": got ", f[2], " expected ", f[3], " (diff ", f[2] - f[3], ")\\n");
od;

LogTo();
QUIT;
'''

# Write GAP commands
script_path = r"C:\Users\jeffr\Downloads\Lifting\temp_s12_test.g"
with open(script_path, "w") as f:
    f.write(gap_commands)

# Run GAP
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
cygwin_script = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s12_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S12 ground truth test at {time.strftime('%H:%M:%S')}...")
print(f"Testing {len(ground_truth)} FPF partitions")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{cygwin_script}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=600)

print(f"GAP exited with code {process.returncode} at {time.strftime('%H:%M:%S')}")

# Read log file
try:
    with open(log_file, "r") as f:
        log = f.read()
    print("\n" + log)
except FileNotFoundError:
    print("Log file not found, printing stdout:")
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
