"""run_prodcopy.py — run the verbatim production batch_run.g on the same
LEFT cache, in isolation, with no other GAPs. If this is also slow, the
bottleneck IS in the production GAP code (some path the bench skips).
If this is fast, the bottleneck is the multi-process environment.
"""
import os, subprocess, time
from pathlib import Path

ROOT = Path(__file__).parent
SCRIPT = ROOT / "bench_prodcopy_tmp/run.g"
LIFTING_WS_CYG = "/cygdrive/c/Users/jeffr/Downloads/Lifting/lifting.ws"

bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/bench_prodcopy_tmp/run.g"
env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"
cmd = (f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
       f'./gap.exe -q -o 0 -L "{LIFTING_WS_CYG}" "{script_cyg}"')

print(f"running production batch_run.g verbatim, isolated...")
t0 = time.time()
proc = subprocess.run([bash_exe, "--login", "-c", cmd], env=env,
                      capture_output=True, text=True, timeout=4*3600)
print(f"done in {time.time()-t0:.0f}s")
log = ROOT / "bench_prodcopy_tmp/prodcopy.log"
if log.exists():
    print("--- last 30 lines of log ---")
    print("\n".join(log.read_text().splitlines()[-30:]))
