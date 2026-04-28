import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_recompute_suspect.log"
gens_dir = "C:/Users/jeffr/Downloads/Lifting/parallel_s15/gens"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed S1-S14 caches
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear H1 cache for clean computation
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("=== Recomputing [5,4,4,2] for S15 ===\\n");
t0 := Runtime();
result1 := FindFPFClassesForPartition(15, [5,4,4,2]);
t1 := Runtime();
Print("[5,4,4,2] count: ", Length(result1), "\\n");
Print("[5,4,4,2] time: ", StringTime(t1 - t0), "\\n");

# Save generators
fname := "{gens_dir}/gens_5_4_4_2.txt";
PrintTo(fname, "");
for H in result1 do
    AppendTo(fname, GeneratorsOfGroup(H), "\\n");
od;
Print("Saved ", Length(result1), " groups to ", fname, "\\n");

Print("\\n=== Recomputing [6,6,3] for S15 ===\\n");
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
result2 := FindFPFClassesForPartition(15, [6,6,3]);
t1 := Runtime();
Print("[6,6,3] count: ", Length(result2), "\\n");
Print("[6,6,3] time: ", StringTime(t1 - t0), "\\n");

# Save generators
fname2 := "{gens_dir}/gens_6_6_3.txt";
PrintTo(fname2, "");
for H in result2 do
    AppendTo(fname2, GeneratorsOfGroup(H), "\\n");
od;
Print("Saved ", Length(result2), " groups to ", fname2, "\\n");

Print("\\nDone. Expected: [5,4,4,2]=4753 (was 4742), [6,6,3]=3248 (was 3246)\\n");
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

print(f"Starting recomputation at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=14400)  # 4 hour timeout

print(f"GAP finished at {time.strftime('%H:%M:%S')}")
with open(r"C:\Users\jeffr\Downloads\Lifting\gap_recompute_suspect.log", "r") as f:
    log = f.read()
# Print last 5000 chars to see results
print(log[-5000:] if len(log) > 5000 else log)
