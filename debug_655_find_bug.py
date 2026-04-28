"""Find the specific (Q, M_bar) where TF-top reduction undercounts."""
import os, subprocess
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
GAP_RUNTIME = Path(r"C:\Program Files\GAP-4.15.1\runtime")
BASH_EXE = GAP_RUNTIME / "bin" / "bash.exe"

OUT_DIR = LIFTING / "parallel_sn_debug" / "16_find_bug" / "[6,5,5]"
if OUT_DIR.exists():
    for f in OUT_DIR.glob("*.g"):
        f.unlink()
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG = LIFTING / "debug_655_find_bug.log"
if LOG.exists():
    LOG.unlink()

tmp = LIFTING / "debug_655_find_bug.g"
tmp.write_text(f'''
USE_TF_DATABASE := true;;
DIAG_TF_VERIFY := true;;
LogTo("{LOG.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");
LIFT_CACHE.("15") := 159129;
COMBO_OUTPUT_DIR := "{OUT_DIR.as_posix()}";
fpf := FindFPFClassesForPartition(16, [6,5,5]);
Print("\\n[6,5,5] FPF classes: ", Length(fpf), "\\n");
if IsBound(DIAG_TF_MISMATCHES) then
    Print("Mismatches: ", Length(DIAG_TF_MISMATCHES), "\\n");
    for i in [1..Minimum(10, Length(DIAG_TF_MISMATCHES))] do
        rec := DIAG_TF_MISMATCHES[i];
        Print("  #", i, ": |Q|=", rec.Q_size, " |M_bar|=", rec.M_bar_size,
              " |R|=", rec.R_size, " |TF|=", rec.TF_size,
              " TFtop=", rec.tftop_count, " NSCR=", rec.nscr_count, "\\n");
    od;
fi;
LogTo();
QUIT;
''')

env = os.environ.copy()
env['PATH'] = str(GAP_RUNTIME / "bin") + os.pathsep + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

import time
t0 = time.time()
proc = subprocess.Popen(
    [str(BASH_EXE), "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_655_find_bug.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=str(GAP_RUNTIME))
stdout, stderr = proc.communicate(timeout=14400)
print(f"Elapsed {time.time()-t0:.1f}s")
print(stdout[-1500:])
