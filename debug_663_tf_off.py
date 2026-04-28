"""Diagnostic: run S_15 partition [6,6,3] with TF-database DISABLED.
Expected (per CLAUDE.md): 3248 FPF classes.
Buggy (TF on, current): 3000 FPF classes.
"""
import os
import subprocess
import time
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
GAP_RUNTIME = Path(r"C:\Program Files\GAP-4.15.1\runtime")
BASH_EXE = GAP_RUNTIME / "bin" / "bash.exe"

OUT_DIR = LIFTING / "parallel_sn_debug" / "15" / "[6,6,3]"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG = LIFTING / "debug_663_tf_off.log"
if LOG.exists():
    LOG.unlink()

tmp = LIFTING / "debug_663_tf_off.g"
tmp.write_text(f'''
USE_TF_DATABASE := false;;
LogTo("{LOG.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");
LIFT_CACHE.("14") := 75154;
COMBO_OUTPUT_DIR := "{OUT_DIR.as_posix()}";
Print("USE_TF_DATABASE = ", USE_TF_DATABASE, "\\n");
t0 := Runtime();
fpf := FindFPFClassesForPartition(15, [6,6,3]);
elapsed := (Runtime() - t0) / 1000.0;
Print("\\n[6,6,3] FPF classes: ", Length(fpf), "\\n");
Print("Expected (TF off, per CLAUDE.md): 3248\\n");
Print("Elapsed: ", elapsed, "s\\n");
LogTo();
QUIT;
''')

env = os.environ.copy()
env['PATH'] = str(GAP_RUNTIME / "bin") + os.pathsep + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running [6,6,3] with TF-database DISABLED...")
t0 = time.time()
proc = subprocess.Popen(
    [str(BASH_EXE), "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_663_tf_off.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=str(GAP_RUNTIME))
stdout, stderr = proc.communicate(timeout=14400)
elapsed = time.time() - t0

print(f"Completed in {elapsed:.1f}s")

# Sum # deduped from combo files
total_from_disk = 0
for f in OUT_DIR.glob("*.g"):
    for line in f.read_text().splitlines():
        if line.startswith("# deduped: "):
            total_from_disk += int(line[11:])
            break

print(f"Total from combo files: {total_from_disk}")
print(f"Expected: 3248")
print(f"Buggy run (TF on): 3000")
print(f"Match? {'YES - TF-database confirmed as bug' if total_from_disk == 3248 else 'NO'}")
print("\n=== STDOUT tail ===")
print(stdout[-1500:])
