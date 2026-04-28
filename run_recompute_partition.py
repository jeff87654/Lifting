"""Recompute a single S15 FPF partition and compare to old count."""
import subprocess
import os
import sys
import time

def count_entries(gens_file):
    """Count logical entries (groups) in a gens file."""
    if not os.path.exists(gens_file):
        return 0
    with open(gens_file, "r") as f:
        content = f.read()
    lines = content.split('\n')
    count = 0
    for line in lines:
        if line.strip().startswith('['):
            count += 1
    return count

def run_partition(partition_list):
    part_str = ",".join(str(x) for x in partition_list)
    part_underscore = "_".join(str(x) for x in partition_list)
    gens_file = f"C:/Users/jeffr/Downloads/Lifting/parallel_s15/gens/gens_{part_underscore}.txt"
    log_file = f"C:/Users/jeffr/Downloads/Lifting/gap_recompute_{part_underscore}.log"

    old_count = count_entries(gens_file.replace("/", os.sep))
    print(f"[{part_str}] Old count: {old_count}")

    gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("=== Recomputing [{part_str}] for S15 ===\\n");
t0 := Runtime();
result := FindFPFClassesForPartition(15, [{part_str}]);
t1 := Runtime();
Print("[{part_str}] count: ", Length(result), "\\n");
Print("[{part_str}] time: ", StringTime(t1 - t0), "\\n");

# Save generators
fname := "{gens_file}";
PrintTo(fname, "");
for H in result do
    AppendTo(fname, GeneratorsOfGroup(H), "\\n");
od;
Print("Saved ", Length(result), " groups to ", fname, "\\n");
LogTo();
QUIT;
'''

    temp_file = f"C:\\Users\\jeffr\\Downloads\\Lifting\\temp_cmd_{part_underscore}.g"
    with open(temp_file, "w") as f:
        f.write(gap_commands)

    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_cmd_{part_underscore}.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    print(f"[{part_str}] Starting at {time.strftime('%H:%M:%S')}")
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=gap_runtime
    )

    stdout, stderr = process.communicate(timeout=14400)

    print(f"[{part_str}] Finished at {time.strftime('%H:%M:%S')}")

    # Read the count from log
    new_count = None
    with open(log_file.replace("/", os.sep), "r") as f:
        for line in f:
            if f"[{part_str}] count:" in line:
                new_count = int(line.split(":")[1].strip())
            if f"[{part_str}] time:" in line:
                print(f"[{part_str}] {line.strip()}")

    if new_count is not None:
        delta = new_count - old_count
        sign = "+" if delta >= 0 else ""
        print(f"[{part_str}] Old: {old_count}, New: {new_count}, Delta: {sign}{delta}")
        if delta != 0:
            print(f"  *** CHANGED by {sign}{delta} ***")
    else:
        print(f"[{part_str}] ERROR: Could not find count in log")
        if stderr.strip():
            err_lines = [l for l in stderr.split('\n') if 'Error' in l]
            if err_lines:
                print(f"  {chr(10).join(err_lines[:5])}")

if __name__ == "__main__":
    partition = [int(x) for x in sys.argv[1].split(",")]
    run_partition(partition)
