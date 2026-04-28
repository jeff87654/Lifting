import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_phase_c1_s12.log"

gap_commands = f'''
LogTo("{log_file}");
Print("=== Phase C1 S12 Per-Partition Test ===\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear caches
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Compute S2-S11 first (needed for lifting)
Print("Computing S2-S11 (warmup)...\\n");
t0 := Runtime();
CountAllConjugacyClassesFast(11);
Print("Warmup done in ", (Runtime()-t0)/1000.0, "s\\n\\n");

# Now compute each S12 FPF partition individually
partitions_12 := [
    [12], [10,2], [8,4], [8,2,2], [6,6], [6,4,2], [6,2,2,2],
    [4,4,4], [4,4,2,2], [4,2,2,2,2], [2,2,2,2,2,2]
];

# Reference values from brute-force (s12_partition_classes_output.txt)
# Format: partition -> FPF count
ref := rec();
ref.("12") := 301;
ref.("10_2") := 77;
ref.("8_4") := 1119;
ref.("8_2_2") := 624;
ref.("6_6") := 473;
ref.("6_4_2") := 1665;
ref.("6_2_2_2") := 481;
ref.("4_4_4") := 1408;
ref.("4_4_2_2") := 1538;
ref.("4_2_2_2_2") := 450;
ref.("2_2_2_2_2_2") := 113;

total_fpf := 0;
all_pass := true;

for part in partitions_12 do
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
    FPF_SUBDIRECT_CACHE := rec();

    partStr := JoinStringsWithSeparator(List(part, String), "_");
    t0 := Runtime();
    fpf := FindFPFClassesForPartition(12, part);
    dt := (Runtime() - t0) / 1000.0;
    count := Length(fpf);
    total_fpf := total_fpf + count;

    expected := 0;
    if IsBound(ref.(partStr)) then
        expected := ref.(partStr);
    fi;

    if expected > 0 and count = expected then
        Print("  ", part, ": ", count, " PASS (", dt, "s)\\n");
    elif expected > 0 then
        Print("  ", part, ": ", count, " FAIL (expected ", expected, ", diff=",
              count - expected, ") (", dt, "s)\\n");
        all_pass := false;
    else
        Print("  ", part, ": ", count, " (no ref) (", dt, "s)\\n");
    fi;
od;

Print("\\nTotal FPF: ", total_fpf, " (expected 8249)\\n");
if total_fpf = 8249 then
    Print("TOTAL PASS\\n");
else
    Print("TOTAL FAIL (diff=", total_fpf - 8249, ")\\n");
fi;
if all_pass then
    Print("ALL PARTITIONS PASS\\n");
fi;

Print("\\n=== Test Complete ===\\n");
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_phase_c1_s12.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_phase_c1_s12.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S12 per-partition test at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=1800)
print(f"GAP exited with code {process.returncode} at {time.strftime('%H:%M:%S')}")

if os.path.exists(r"C:\Users\jeffr\Downloads\Lifting\test_phase_c1_s12.log"):
    with open(r"C:\Users\jeffr\Downloads\Lifting\test_phase_c1_s12.log", "r") as f:
        log = f.read()
    # Print just the summary
    for line in log.split('\n'):
        if 'PASS' in line or 'FAIL' in line or 'Total' in line or 'Test' in line or line.strip().startswith('['):
            print(line)
else:
    print("No log file!")
    print("STDERR:", stderr[:2000])
