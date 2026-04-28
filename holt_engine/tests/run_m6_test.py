"""Run the M6 block-factored normalizer test on the slow combo."""
import os, subprocess

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
SCRIPT = r"C:\Users\jeffr\Downloads\Lifting\holt_engine\tests\test_m6_blocknorm.g"
LOG = r"C:\Users\jeffr\Downloads\Lifting\holt_engine\tests\test_m6_blocknorm.log"

bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = SCRIPT.replace("C:\\", "/cygdrive/c/").replace("\\", "/")
gap_dir = '/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1'

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

if os.path.exists(LOG):
    os.remove(LOG)

proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "{gap_dir}" && ./gap.exe -q -o 0 "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, timeout=7200,
)
print(f"Exit code: {proc.returncode}")
if proc.stderr:
    print(f"stderr tail: {proc.stderr[-1000:]}")
print("Log tail:")
if os.path.exists(LOG):
    with open(LOG) as f:
        lines = f.readlines()
    for line in lines[-30:]:
        print(line.rstrip())
