"""Run S11 with TF cache loaded + DIAG_TF_VERIFY to find mismatching cases."""
import subprocess, os
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = LIFTING / "debug_find_mismatch.log"

gap_commands = f'''
DIAG_TF_VERIFY := true;;
USE_TF_DATABASE := true;;
LogTo("{LOG.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");
Read("{(LIFTING / "database" / "lift_cache.g").as_posix()}");
Unbind(LIFT_CACHE.("11"));

t0 := Runtime();
result := CountAllConjugacyClassesFast(11);
elapsed := (Runtime() - t0) / 1000.0;
Print("\\nS_11 = ", result, " expected=3094 elapsed=", elapsed, "s\\n");
Print("DIAG_TF_MISMATCHES count: ", Length(DIAG_TF_MISMATCHES), "\\n");

# Print first few mismatches
for i in [1..Minimum(5, Length(DIAG_TF_MISMATCHES))] do
    rec := DIAG_TF_MISMATCHES[i];
    Print("\\nMismatch ", i, ":\\n");
    Print("  was_hit: ", rec.was_hit, "\\n");
    Print("  |Q|=", rec.Q_size, " |M_bar|=", rec.M_bar_size, " idx=", rec.idx, "\\n");
    Print("  TFDB count: ", rec.tfdb_count, "\\n");
    Print("  Ground truth: ", rec.gt_count, "\\n");
    Print("  key: ", rec.key, "\\n");
od;
LogTo();
QUIT;
'''

TMP = LIFTING / "temp_find_mismatch.g"
TMP.write_text(gap_commands)
if LOG.exists():
    LOG.unlink()

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

proc = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_find_mismatch.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
stdout, stderr = proc.communicate(timeout=600)
print(stdout[-3500:])
