"""Independent validation: run S_16 partition [6,5,5] with TF-database DISABLED.
Current run (TF on, new TF-top approach): 1276
Old ref (parallel_s16/gens/gens_6_5_5.txt): 1283
One of them is wrong. TF-off gives ground truth."""
import os, subprocess, time
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
GAP_RUNTIME = Path(r"C:\Program Files\GAP-4.15.1\runtime")
BASH_EXE = GAP_RUNTIME / "bin" / "bash.exe"

OUT_DIR = LIFTING / "parallel_sn_debug" / "16_tf_off" / "[6,5,5]"
if OUT_DIR.exists():
    for f in OUT_DIR.glob("*.g"):
        f.unlink()
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG = LIFTING / "debug_655_tf_off.log"
if LOG.exists():
    LOG.unlink()

tmp = LIFTING / "debug_655_tf_off.g"
tmp.write_text(f'''
USE_TF_DATABASE := false;;
LogTo("{LOG.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");
LIFT_CACHE.("15") := 159129;
COMBO_OUTPUT_DIR := "{OUT_DIR.as_posix()}";
t0 := Runtime();
fpf := FindFPFClassesForPartition(16, [6,5,5]);
elapsed := (Runtime() - t0) / 1000.0;
Print("\\n[6,5,5] FPF classes: ", Length(fpf), "\\n");
Print("Elapsed: ", elapsed, "s\\n");
LogTo();
QUIT;
''')

env = os.environ.copy()
env['PATH'] = str(GAP_RUNTIME / "bin") + os.pathsep + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running [6,5,5] with TF disabled...")
t0 = time.time()
proc = subprocess.Popen(
    [str(BASH_EXE), "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_655_tf_off.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=str(GAP_RUNTIME))
stdout, stderr = proc.communicate(timeout=3600)
elapsed = time.time() - t0
print(f"Completed in {elapsed:.1f}s")
total = sum(int(line[11:]) for f in OUT_DIR.glob("*.g") for line in f.read_text().splitlines() if line.startswith("# deduped: "))
print(f"Total: {total}")
print(f"New TF-top (current): 1276")
print(f"Old ref: 1283")
if total == 1276:
    print("TF-OFF = CURRENT. Old ref has a bug (overcount).")
elif total == 1283:
    print("TF-OFF = OLD REF. Current TF-top is WRONG.")
else:
    print(f"UNEXPECTED: {total}")
