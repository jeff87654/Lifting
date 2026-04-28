import os, subprocess
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
GAP_RUNTIME = Path(r"C:\Program Files\GAP-4.15.1\runtime")

OUT_DIR = LIFTING / "parallel_sn" / "16" / "[6,5,5]"
for f in OUT_DIR.glob("*.g"): f.unlink()
tmp = LIFTING / "debug_655_v3.g"
tmp.write_text(f'''
USE_TF_DATABASE := true;;
LogTo("{(LIFTING / "debug_655_v3.log").as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");
LIFT_CACHE.("15") := 159129;
COMBO_OUTPUT_DIR := "{OUT_DIR.as_posix()}";
fpf := FindFPFClassesForPartition(16, [6,5,5]);
Print("RESULT [6,5,5] = ", Length(fpf), " (expected 1283)\n");
Print("TF stats: ", TF_LOOKUP_STATS, "\n");
LogTo();
QUIT;
''')

env = os.environ.copy()
env['PATH'] = str(GAP_RUNTIME / 'bin') + os.pathsep + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
proc = subprocess.Popen(
    [str(GAP_RUNTIME / 'bin' / 'bash.exe'), '--login', '-c',
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_655_v3.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=str(GAP_RUNTIME))
out, err = proc.communicate(timeout=7200)
print(out[-800:])
