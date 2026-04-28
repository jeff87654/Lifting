"""Test the fix: run [6,6,3] with TF enabled + M2 cache loaded (bug scenario).
Using Image(iso, H) instead of Subgroup(G, [Image(iso, g) for g in gens(H)]).
Expected: 3248 (if fix works) or 3000 (if same bug).
"""
import os, subprocess, time
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
GAP_RUNTIME = Path(r"C:\Program Files\GAP-4.15.1\runtime")
BASH_EXE = GAP_RUNTIME / "bin" / "bash.exe"

OUT_DIR = LIFTING / "parallel_sn_debug" / "15_tf_fix" / "[6,6,3]"
if OUT_DIR.exists():
    for f in OUT_DIR.glob("*.g"):
        f.unlink()
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG = LIFTING / "debug_663_tf_fix.log"
if LOG.exists():
    LOG.unlink()

tmp = LIFTING / "debug_663_tf_fix.g"
tmp.write_text(f'''
USE_TF_DATABASE := true;;
LogTo("{LOG.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");
LIFT_CACHE.("14") := 75154;
COMBO_OUTPUT_DIR := "{OUT_DIR.as_posix()}";
Print("USE_TF_DATABASE = ", USE_TF_DATABASE, "\\n");
Print("TF_SUBGROUP_LATTICE entries loaded: ", Length(RecNames(TF_SUBGROUP_LATTICE)), "\\n");
t0 := Runtime();
fpf := FindFPFClassesForPartition(15, [6,6,3]);
elapsed := (Runtime() - t0) / 1000.0;
Print("\\n[6,6,3] FPF classes: ", Length(fpf), "\\n");
Print("TF_LOOKUP_STATS: ", TF_LOOKUP_STATS, "\\n");
Print("Elapsed: ", elapsed, "s\\n");
LogTo();
QUIT;
''')

env = os.environ.copy()
env['PATH'] = str(GAP_RUNTIME / "bin") + os.pathsep + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running [6,6,3] with TF ENABLED + M2 cache + Image(iso, H) fix...")
t0 = time.time()
proc = subprocess.Popen(
    [str(BASH_EXE), "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_663_tf_fix.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=str(GAP_RUNTIME))
stdout, stderr = proc.communicate(timeout=14400)
elapsed = time.time() - t0
print(f"Completed in {elapsed:.1f}s")
total = sum(int(line[11:]) for f in OUT_DIR.glob("*.g") for line in f.read_text().splitlines() if line.startswith("# deduped: "))
print(f"Total: {total}")
print(f"Expected: 3248")
print(f"Buggy: 3000")
print(f"Fix {'WORKED' if total == 3248 else 'DID NOT WORK (got ' + str(total) + ')'}")
