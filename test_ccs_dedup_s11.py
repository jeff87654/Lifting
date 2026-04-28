"""Quick test: S11=3094 with CCS Union-Find dedup. Uses cached S1-S10."""
import subprocess, os, time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = os.path.join(LIFTING_DIR, "gap_output_ccs_s11.log")

gap_commands = f'''
LogTo("{log_file.replace(chr(92), '/')}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
LoadDatabaseIfExists();
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("Testing S11 with CCS Union-Find dedup (cached S1-S10)...\\n");
t0 := Runtime();
c := CountAllConjugacyClassesFast(11);
Print("S11 = ", c, " (", Runtime()-t0, "ms)\\n");
if c = 3094 then Print("S11 PASS\\n"); else Print("S11 FAIL\\n"); fi;
LogTo();
QUIT;
'''

script_file = os.path.join(LIFTING_DIR, "temp_test_ccs_s11.g")
with open(script_file, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_ccs_s11.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting S11 test at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=300)
print(f"Finished at {time.strftime('%H:%M:%S')}, exit code: {process.returncode}")

with open(log_file, "r") as f:
    log = f.read()
lines = log.strip().split('\n')
for line in lines[-15:]:
    print(line)
