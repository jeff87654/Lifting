"""Resume [6,4,3,2,2] from checkpoint with per-combo normalizer optimization."""
import subprocess, os, time

LOG = "C:/Users/jeffr/Downloads/Lifting/test_resume_64322.log"
CKPT = "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_172/ckpt_17_6_4_3_2_2.log"

gap_commands = f'''
LogTo("{LOG}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Need S1-S16 cached for S17 partition work
# lift_cache.g has S1-S16

Print("=== Resuming [6,4,3,2,2] of S17 from checkpoint ===\\n");
Print("Loading checkpoint...\\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/test_ckpt_64322/";

# Time the resume
t0 := Runtime();
result := FindFPFClassesForPartition(17, [6,4,3,2,2]);
t1 := Runtime();
Print("\\n[6,4,3,2,2] result: ", Length(result), " FPF classes\\n");
Print("Time: ", StringTime(t1-t0), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_resume_64322.g", "w") as f:
    f.write(gap_commands)

# Make checkpoint dir and copy checkpoint
os.makedirs(r"C:\Users\jeffr\Downloads\Lifting\test_ckpt_64322", exist_ok=True)
import shutil
shutil.copy2(
    r"C:\Users\jeffr\Downloads\Lifting\parallel_s17\checkpoints\worker_172\ckpt_17_6_4_3_2_2.log",
    r"C:\Users\jeffr\Downloads\Lifting\test_ckpt_64322\ckpt_17_6_4_3_2_2.log"
)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_resume_64322.g"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Resuming [6,4,3,2,2] from checkpoint (153/160 combos done)...")
t0 = time.time()
p = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
p.communicate(timeout=3600)
elapsed = time.time() - t0
print(f"Done in {elapsed:.1f}s")

with open(LOG.replace("/","\\"), "r") as f:
    log = f.read()
for line in log.split('\n'):
    if any(k in line for k in ['Resum', 'combo', 'result', 'Time', 'per-combo', 'PASS', 'FAIL', 'fpf total', 'checkpoint', 'Loading']):
        print(line)
