"""Verify the cache-mutation bug is fully fixed: run S_4 twice in same session,
confirm both runs return correct result and cache stays valid."""
import subprocess, os
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = LIFTING / "debug_verify_fix.log"

gap_commands = f'''
LogTo("{LOG.as_posix()}");
USE_TF_DATABASE := false;;
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");

Print("\\n=== Run 1 of S_4 ===\\n");
r1 := CountAllConjugacyClassesFast(4);
Print("S_4 (run 1) = ", r1, " expected=11\\n");

# Verify cache integrity after run 1
key := "[ [ 2, 1 ], [ 2, 1 ] ]";
Print("\\nCache for ", key, ":\\n");
for G in FPF_SUBDIRECT_CACHE.(key) do
    Print("  ", G, " IsGroup=", IsGroup(G), "\\n");
od;

# Reset only the lift_cache, keep FPF cache
Unbind(LIFT_CACHE.("4"));
Print("\\n=== Run 2 of S_4 (FPF cache populated) ===\\n");
r2 := CountAllConjugacyClassesFast(4);
Print("S_4 (run 2) = ", r2, " expected=11\\n");

# Verify cache integrity after run 2
Print("\\nCache for ", key, " after run 2:\\n");
for G in FPF_SUBDIRECT_CACHE.(key) do
    Print("  ", G, " IsGroup=", IsGroup(G), "\\n");
od;

# Reset and run a third time to be sure
Unbind(LIFT_CACHE.("4"));
Print("\\n=== Run 3 of S_4 ===\\n");
r3 := CountAllConjugacyClassesFast(4);
Print("S_4 (run 3) = ", r3, " expected=11\\n");

LogTo();
QUIT;
'''

TMP = LIFTING / "temp_verify_fix.g"
TMP.write_text(gap_commands)
if LOG.exists():
    LOG.unlink()

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

proc = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_verify_fix.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
stdout, stderr = proc.communicate(timeout=300)
print(stdout[-2500:])
