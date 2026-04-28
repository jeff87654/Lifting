"""A/B test: Compare orbital ON vs OFF for affected partitions with current code (post cross-combo dedup fix)."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"

def run_gap_partition(partition_str, orbital_on, log_suffix):
    """Run a single partition with orbital ON or OFF."""
    log_file = f"C:/Users/jeffr/Downloads/Lifting/orbital_ab_{log_suffix}.log"
    orbital_val = "true" if orbital_on else "false"

    gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

USE_H1_ORBITAL := {orbital_val};
Print("Config: USE_H1_ORBITAL (", USE_H1_ORBITAL, ")\\n");

# Clear caches for clean run
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("Running {partition_str} with orbital={orbital_val}...\\n");
t0 := Runtime();
result := FindFPFClassesForPartition(15, {partition_str});
elapsed := Runtime() - t0;
Print("Result: ", Length(result), " classes\\n");
Print("Time: ", elapsed, "ms\\n");
LogTo();
QUIT;
'''

    temp_gap = os.path.join(LIFTING_DIR, f"temp_ab_{log_suffix}.g")
    with open(temp_gap, "w") as f:
        f.write(gap_commands)

    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_ab_{log_suffix}.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    print(f"  Starting {log_suffix} at {time.strftime('%H:%M:%S')}")
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
    )
    stdout, stderr = process.communicate(timeout=7200)
    print(f"  Finished {log_suffix} at {time.strftime('%H:%M:%S')}")

    if stderr.strip():
        err_lines = [l for l in stderr.split('\n') if 'Error' in l]
        if err_lines:
            print(f"  ERRORS: {err_lines[:5]}")

    log_path = log_file.replace("/", os.sep)
    count = None
    elapsed_ms = None
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            log = f.read()
        for line in log.split('\n'):
            if line.startswith('Result: '):
                count = int(line.split()[1])
            if line.startswith('Time: '):
                elapsed_ms = int(line.split()[1].replace('ms', ''))

    return count, elapsed_ms

# Test both affected partitions
partitions = [
    ("[6,6,3]", "663"),
    ("[5,4,4,2]", "5442"),
]

print("=" * 60)
print("Orbital ON vs OFF A/B Test (post cross-combo dedup fix)")
print("=" * 60)

results = {}
for partition_str, tag in partitions:
    print(f"\n--- Testing {partition_str} ---")

    # Run orbital OFF first (baseline)
    count_off, time_off = run_gap_partition(partition_str, False, f"{tag}_off")
    print(f"  Orbital OFF: {count_off} classes in {time_off}ms")

    # Run orbital ON
    count_on, time_on = run_gap_partition(partition_str, True, f"{tag}_on")
    print(f"  Orbital ON:  {count_on} classes in {time_on}ms")

    results[tag] = (count_off, count_on, time_off, time_on)

    if count_off == count_on:
        print(f"  >>> MATCH: Both give {count_off}")
    else:
        print(f"  >>> MISMATCH: OFF={count_off}, ON={count_on}, delta={count_off - count_on}")

print("\n" + "=" * 60)
print("Summary:")
for tag, (off, on, t_off, t_on) in results.items():
    status = "MATCH" if off == on else f"MISMATCH (delta={off-on})"
    speedup = f"{t_off/t_on:.2f}x" if t_on and t_off else "N/A"
    print(f"  {tag}: OFF={off} ON={on} [{status}] speedup={speedup}")
print("=" * 60)
