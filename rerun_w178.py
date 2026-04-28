"""Rerun W178: S17 partition [8,4,3,2] with per-combo dedup."""
import subprocess, os

log_file = "C:/Users/jeffr/Downloads/Lifting/parallel_s17/rerun/w178.log"

gap_commands = f'''
LogTo("{log_file}");
Print("W178 rerun: S17 [8,4,3,2]\\n");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/rerun/ckpt_178";
_HEARTBEAT_FILE := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/rerun/w178_heartbeat.txt";

startT := Runtime();
result := FindFPFClassesForPartition(17, [8,4,3,2]);
elapsed := (Runtime() - startT) / 1000.0;
Print("\\n[8,4,3,2] = ", Length(result), " (expected 116100) in ", elapsed, "s\\n");
if Length(result) = 116100 then Print("PASS\\n"); else Print("FAIL\\n"); fi;
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\parallel_s17\rerun\w178.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s17/rerun/w178.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=36000)
with open(log_file.replace("/", "\\"), "r") as f:
    log = f.read()
for line in log.split('\n'):
    if any(k in line for k in ['PASS', 'FAIL', '8,4,3,2', 'expected']):
        print(line)
