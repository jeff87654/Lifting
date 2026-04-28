import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_goursat_88_test.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed S1-S15 data
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear FPF cache for fresh computation
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("=== Heavy [8,8] combos via Goursat ===\\n\\n");

# Test individual heavy combos
# TransitiveGroup(8,49) = A_8, TransitiveGroup(8,50) = S_8
heavyCombos := [
    [8, 49, 8, 49],  # A_8 x A_8
    [8, 49, 8, 50],  # A_8 x S_8
    [8, 50, 8, 50],  # S_8 x S_8
    [8, 48, 8, 48],  # PGL(2,7) x PGL(2,7), |T|=1344
    [8, 47, 8, 47],  # PSL(2,7) x PSL(2,7), |T|=168
    [8, 45, 8, 45],  # AGL(1,8) x AGL(1,8), |T|=56
    [8, 3, 8, 3],    # D_4 x D_4 (the slow dedup case from before)
];

for combo in heavyCombos do
    T1 := TransitiveGroup(combo[1], combo[2]);
    T2 := TransitiveGroup(combo[3], combo[4]);
    T2_shifted := ShiftGroup(T2, combo[1]);
    pts1 := MovedPoints(T1);
    pts2 := MovedPoints(T2_shifted);

    Print("--- [8,", combo[2], "] x [8,", combo[4], "] ---\\n");
    Print("  |T1|=", Size(T1), " |T2|=", Size(T2), "\\n");

    t0 := Runtime();
    result := GoursatFPFSubdirects(T1, T2_shifted, pts1, pts2);
    t1 := Runtime();

    Print("  Result: ", Length(result), " FPF subdirects (", t1-t0, "ms)\\n");
    for i in [1..Length(result)] do
        Print("    H", i, ": |H|=", Size(result[i]), "\\n");
    od;
    Print("\\n");
od;

Print("\\n=== Full [8,8] partition test ===\\n");
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
result := FindFPFClassesForPartition(16, [8,8]);
t1 := Runtime();
Print("[8,8] FPF classes: ", Length(result), " (", t1-t0, "ms = ",
      Int((t1-t0)/1000), "s)\\n");

Print("\\nAll tests complete.\\n");
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting GAP test at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=7200)  # 2 hour timeout
print(f"GAP finished at {time.strftime('%H:%M:%S')}")

with open(log_file, "r") as f:
    log = f.read()
print(log[-5000:])
