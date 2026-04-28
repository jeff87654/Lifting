"""S13 correctness check: recompute from S10 cached, verify == 20832."""
import subprocess, os, time
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = LIFTING / "test_m3_s13.log"

gap_commands = f'''
LogTo("{LOG.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");

# Load S1-S10 cache (fast skip)
Read("{(LIFTING / "database" / "lift_cache.g").as_posix()}");

# Clear S11, S12, S13 entries to force recomputation
Unbind(LIFT_CACHE.("11"));
Unbind(LIFT_CACHE.("12"));
Unbind(LIFT_CACHE.("13"));

Print("\\n=== S11, S12, S13 with TF-database (new fingerprint) ===\\n");

for n in [11, 12, 13] do
    expected := function()
        if n = 11 then return 3094; fi;
        if n = 12 then return 10723; fi;
        if n = 13 then return 20832; fi;
        return fail;
    end();
    t0 := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - t0) / 1000.0;
    Print("\\n=== S_", n, " = ", result, " expected=", expected,
          " elapsed=", elapsed, "s ",
          function() if result = expected then return "PASS"; else return "FAIL"; fi; end(),
          " ===\\n");
od;

Print("\\nFINAL TF_LOOKUP_STATS: ", TF_LOOKUP_STATS, "\\n");
Print("TF_SUBGROUP_LATTICE entries: ", Length(RecNames(TF_SUBGROUP_LATTICE)), "\\n");
Print("DONE\\n");
LogTo();
QUIT;
'''

TMP = LIFTING / "temp_m3_s13.g"
TMP.write_text(gap_commands)
if LOG.exists():
    LOG.unlink()

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

start = time.time()
proc = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_m3_s13.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")

stdout, stderr = proc.communicate(timeout=10800)
elapsed = time.time() - start

print(f"Completed in {elapsed:.1f}s")
print(stdout[-2000:])
if stderr:
    print("\nstderr tail:")
    print(stderr[-500:])
