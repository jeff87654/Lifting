"""Run check_combo_affected.g on the full affected_combos.txt list."""
import subprocess, os, time

code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/full_diagnostic.log");
Read("C:/Users/jeffr/Downloads/Lifting/check_combo_affected.g");
ProcessAffectedList(
    "C:/Users/jeffr/Downloads/Lifting/affected_combos.txt",
    "C:/Users/jeffr/Downloads/Lifting/affected_combos_confirmed.txt");
LogTo();
QUIT;
'''
with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_run_diag.g", "w") as f:
    f.write(code)
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
# Remove output if exists (to show fresh results)
out = r"C:\Users\jeffr\Downloads\Lifting\affected_combos_confirmed.txt"
if os.path.exists(out):
    os.remove(out)
t0 = time.time()
p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_run_diag.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
print(f"GAP diagnostic running at PID {p.pid}, logging to full_diagnostic.log")
print(f"Output file: {out}")
print(f"Started at {time.strftime('%H:%M:%S')}")
