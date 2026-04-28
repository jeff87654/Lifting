import subprocess
import os
import time
import shutil

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
source_file = r"C:\Users\jeffr\Downloads\Lifting\lifting_method_fast_v2.g"
log_file_a = "C:/Users/jeffr/Downloads/Lifting/gap_output_a.log"
log_file_b = "C:/Users/jeffr/Downloads/Lifting/gap_output_b.log"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

def make_gap_commands(log_file):
    return f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Fast warmup: load precomputed S1-S11 counts + FPF subdirect cache
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
# FPF subdirect cache is loaded automatically by load_database.g

# Clear FPF cache so [4,4,4] is computed fresh (not from cache)
# But keep LIFT_CACHE so recursive calls return immediately
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("\\n=== Running [4,4,4] partition ===\\n");
FindFPFClassesForPartition(12, [4,4,4]);
Print("\\n=== Done ===\\n");

LogTo();
QUIT;
'''

def run_gap(label, log_file, cmd_file):
    gap_commands = make_gap_commands(log_file)

    with open(cmd_file, "w") as f:
        f.write(gap_commands)

    script_path = cmd_file.replace("C:\\Users\\jeffr\\Downloads\\Lifting\\",
                                    "/cygdrive/c/Users/jeffr/Downloads/Lifting/")
    script_path = script_path.replace("\\", "/")

    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"{'='*60}")
    start = time.time()

    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
    )

    stdout, stderr = process.communicate(timeout=7200)
    elapsed = time.time() - start
    print(f"GAP finished in {elapsed:.1f}s")

    log_path = log_file.replace("/", "\\").replace("C:", "C:")
    try:
        with open(log_path, "r") as f:
            log = f.read()

        # Print all lines from "Running [4,4,4]" onwards
        in_section = False
        for line in log.split('\n'):
            if 'Running [4,4,4]' in line:
                in_section = True
            if in_section:
                line_s = line.strip()
                if line_s:
                    print(line_s)
                if 'Done' in line:
                    break

    except FileNotFoundError:
        print("Log file not found!")
        print(f"STDOUT: {stdout[:3000]}")

    return elapsed

# --- Local version strings for swapping ---
local_version = """    incrementalDedup := function(newResults)
        local H, localByInvariant, before;
        localByInvariant := rec();
        before := Length(all_fpf);
        totalCandidates := totalCandidates + Length(newResults);
        for H in newResults do
            if AddIfNotConjugate(N, H, all_fpf, localByInvariant, invFunc) then
                addedCount := addedCount + 1;
            fi;
        od;
        Print("    combo: ", Length(newResults), " candidates -> ",
              Length(all_fpf) - before, " new (", Length(all_fpf), " total)\\n");
    end;"""

shared_version = """    incrementalDedup := function(newResults)
        local H, before;
        before := Length(all_fpf);
        totalCandidates := totalCandidates + Length(newResults);
        for H in newResults do
            if AddIfNotConjugate(N, H, all_fpf, byInvariant, invFunc) then
                addedCount := addedCount + 1;
            fi;
        od;
        Print("    combo: ", Length(newResults), " candidates -> ",
              Length(all_fpf) - before, " new (", Length(all_fpf), " total)\\n");
    end;"""

# --- RUN A: Local byInvariant (current code) ---
time_a = run_gap("A: Local byInvariant (independent per-combination dedup)",
                 log_file_a,
                 r"C:\Users\jeffr\Downloads\Lifting\temp_commands_a.g")

# --- Swap to shared byInvariant ---
print("\n--- Swapping to shared byInvariant for run B ---")
with open(source_file, "r") as f:
    code = f.read()

assert local_version in code, "Could not find local byInvariant version in source!"
code_b = code.replace(local_version, shared_version)
with open(source_file, "w") as f:
    f.write(code_b)

# --- RUN B: Shared byInvariant (baseline) ---
time_b = run_gap("B: Shared byInvariant (baseline dedup)",
                 log_file_b,
                 r"C:\Users\jeffr\Downloads\Lifting\temp_commands_b.g")

# --- Restore local byInvariant ---
print("\n--- Restoring local byInvariant ---")
with open(source_file, "r") as f:
    code = f.read()
assert shared_version in code, "Could not find shared version to restore!"
code_restored = code.replace(shared_version, local_version)
with open(source_file, "w") as f:
    f.write(code_restored)

print(f"\n{'='*60}")
print("A/B SUMMARY — [4,4,4] partition")
print(f"{'='*60}")
print(f"  A (local byInvariant):  {time_a:.1f}s")
print(f"  B (shared byInvariant): {time_b:.1f}s")
print(f"  Difference: {time_b - time_a:+.1f}s ({'+' if time_b > time_a else ''}{(time_b - time_a) / time_b * 100:.1f}%)")
print("(Times include GAP startup + cache loading; partition time is in the log output above)")
