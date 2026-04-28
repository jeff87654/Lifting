"""TF enabled with EMPTY tf_subgroup_lattice (all cache misses → compute fresh).
If this gives 3248, iso-translation of cache HITS is the bug.
If this gives 3000 (still wrong), the filter itself or compute path is the bug.
"""
import os
import subprocess
import time
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
GAP_RUNTIME = Path(r"C:\Program Files\GAP-4.15.1\runtime")
BASH_EXE = GAP_RUNTIME / "bin" / "bash.exe"

# Back up and empty the TF cache first
TF_CACHE = LIFTING / "database" / "tf_groups" / "tf_subgroup_lattice.g"
BACKUP = LIFTING / "database" / "tf_groups" / "tf_subgroup_lattice.g.backup_before_diag"
if TF_CACHE.exists() and not BACKUP.exists():
    BACKUP.write_text(TF_CACHE.read_text())
TF_CACHE.write_text(
    "###############################################################################\n"
    "# tf_subgroup_lattice.g - Temporarily empty for diagnostic\n"
    "###############################################################################\n"
    "TF_SUBGROUP_LATTICE_DATA := rec();\n"
)

OUT_DIR = LIFTING / "parallel_sn_debug" / "15_tf_fresh" / "[6,6,3]"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG = LIFTING / "debug_663_tf_fresh.log"
if LOG.exists():
    LOG.unlink()

tmp = LIFTING / "debug_663_tf_fresh.g"
tmp.write_text(f'''
USE_TF_DATABASE := true;;
LogTo("{LOG.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");
LIFT_CACHE.("14") := 75154;
# Ensure TF cache starts empty
TF_SUBGROUP_LATTICE := rec();
TF_SUBGROUP_LATTICE_DIRTY_KEYS := rec();
COMBO_OUTPUT_DIR := "{OUT_DIR.as_posix()}";
Print("USE_TF_DATABASE = ", USE_TF_DATABASE, "\\n");
Print("TF_SUBGROUP_LATTICE initial entries: ", Length(RecNames(TF_SUBGROUP_LATTICE)), "\\n");
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

print("Running [6,6,3] with TF ENABLED (fresh cache)...")
t0 = time.time()
proc = subprocess.Popen(
    [str(BASH_EXE), "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_663_tf_fresh.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=str(GAP_RUNTIME))
stdout, stderr = proc.communicate(timeout=14400)
elapsed = time.time() - t0

print(f"Completed in {elapsed:.1f}s")

total = 0
for f in OUT_DIR.glob("*.g"):
    for line in f.read_text().splitlines():
        if line.startswith("# deduped: "):
            total += int(line[11:])
            break

print(f"Total from combo files: {total}")
print(f"Expected: 3248")
print(f"Buggy (TF on, M2 cache): 3000")
print(f"Match? {'YES' if total == 3248 else 'NO'}")
if total == 3248:
    print("CONCLUSION: iso-translation in LookupTFSubgroups is the bug.")
elif total == 3000:
    print("CONCLUSION: bug is in filter or compute path, not iso.")
else:
    print(f"UNEXPECTED: {total} (maybe third mode?)")

# Restore TF cache
TF_CACHE.write_text(BACKUP.read_text())
print("TF cache restored from backup.")
