"""Run S11 and S12 to exercise the non-abelian branch and verify TF-database
integration doesn't regress correctness. S11 = 3094, S12 = 10723.

This test confirms M3's integration is correct on real workloads where the
non-abelian complement path actually fires.
"""
import subprocess, os, time
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = LIFTING / "test_m3_s11_s12.log"

gap_commands = f'''
LogTo("{LOG.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");

# Use precomputed S1-S10 to avoid burning cycles recomputing those.
Read("{(LIFTING / "database" / "lift_cache.g").as_posix()}");

expected := rec(("11") := 3094, ("12") := 10723);

for n in [11, 12] do
    Print("\\n=== S_", n, " (expected: ", expected.(String(n)), ") ===\\n");
    t0 := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - t0) / 1000.0;
    Print("S_", n, " = ", result, " expected=", expected.(String(n)),
          " elapsed=", elapsed, "s ",
          function() if result = expected.(String(n)) then return "PASS"; else return "FAIL"; fi; end(), "\\n");
    # Clear LIFT_CACHE between runs to force recompute at next iteration
    # Actually, keep it - S12 needs S11 cached.
od;

Print("\\nFINAL TF_LOOKUP_STATS: ", TF_LOOKUP_STATS, "\\n");
Print("DONE\\n");
LogTo();
QUIT;
'''

TMP = LIFTING / "temp_m3_s11_s12.g"
TMP.write_text(gap_commands)
if LOG.exists():
    LOG.unlink()

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

proc = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_m3_s11_s12.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")

start = time.time()
stdout, stderr = proc.communicate(timeout=3600)
elapsed = time.time() - start

print(f"=== Completed in {elapsed:.1f}s ===")
print("\nSTDOUT tail:")
print(stdout[-3000:])
if stderr:
    print("\nSTDERR tail:")
    print(stderr[-1000:])
