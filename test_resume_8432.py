"""Resume [8,4,3,2] from checkpoint with per-combo normalizer optimization."""
import subprocess, os, time, shutil

LOG = "C:/Users/jeffr/Downloads/Lifting/test_resume_8432.log"
CKPT_SRC = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17\checkpoints\worker_174\ckpt_17_8_4_3_2.log"
CKPT_DIR = r"C:\Users\jeffr\Downloads\Lifting\test_ckpt_8432"

gap_commands = f'''
LogTo("{LOG}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("=== Resuming [8,4,3,2] of S17 from checkpoint ===\\n");
Print("275/500 combos already done, 73814 FPF so far\\n\\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/test_ckpt_8432/";

t0 := Runtime();
result := FindFPFClassesForPartition(17, [8,4,3,2]);
t1 := Runtime();
Print("\\n[8,4,3,2] result: ", Length(result), " FPF classes\\n");
Print("Time (resume portion): ", StringTime(t1-t0), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_resume_8432.g", "w") as f:
    f.write(gap_commands)

# Copy checkpoint
os.makedirs(CKPT_DIR, exist_ok=True)
shutil.copy2(CKPT_SRC, os.path.join(CKPT_DIR, "ckpt_17_8_4_3_2.log"))

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_resume_8432.g"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Resuming [8,4,3,2] from checkpoint (275/500 combos done)...")
print("Per-combo normalizer should show big gains for degree-8 groups")
t0 = time.time()
p = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
p.communicate(timeout=7200)
elapsed = time.time() - t0
print(f"Done in {elapsed:.1f}s")

with open(LOG.replace("/","\\"), "r") as f:
    log = f.read()
for line in log.split('\n'):
    if any(k in line for k in ['Resum', 'combo #', 'result', 'Time', 'per-combo', 'fpf total', 'checkpoint', 'Loading', '8,4,3,2']):
        print(line)
