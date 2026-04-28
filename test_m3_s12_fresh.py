"""Fresh S12 computation: clears LIFT_CACHE for 11 and 12, runs S11 + S12 from scratch.
Exercises the non-abelian branch where TF-database kicks in."""
import subprocess, os, time
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = LIFTING / "test_m3_s12_fresh.log"

gap_commands = f'''
LogTo("{LOG.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");

# Load S1-S10 cache (to skip those fast)
Read("{(LIFTING / "database" / "lift_cache.g").as_posix()}");

# Clear S11 and S12 entries to force recomputation
Unbind(LIFT_CACHE.("11"));
Unbind(LIFT_CACHE.("12"));

Print("\\n=== Computing S_11 from S_10 cache ===\\n");
t0 := Runtime();
result := CountAllConjugacyClassesFast(11);
elapsed := (Runtime() - t0) / 1000.0;
Print("S_11 = ", result, " expected=3094 elapsed=", elapsed, "s ",
      function() if result = 3094 then return "PASS"; else return "FAIL"; fi; end(), "\\n");

Print("\\n=== Computing S_12 from S_11 cache ===\\n");
t0 := Runtime();
result := CountAllConjugacyClassesFast(12);
elapsed := (Runtime() - t0) / 1000.0;
Print("S_12 = ", result, " expected=10723 elapsed=", elapsed, "s ",
      function() if result = 10723 then return "PASS"; else return "FAIL"; fi; end(), "\\n");

Print("\\nFINAL TF_LOOKUP_STATS: ", TF_LOOKUP_STATS, "\\n");

# Show cache state
Print("\\nTF_SUBGROUP_LATTICE entries: ", Length(RecNames(TF_SUBGROUP_LATTICE)), "\\n");
Print("TF_SUBGROUP_LATTICE_DIRTY_KEYS: ", Length(RecNames(TF_SUBGROUP_LATTICE_DIRTY_KEYS)), "\\n");
Print("Keys (first 20): ", RecNames(TF_SUBGROUP_LATTICE){{[1..Minimum(20, Length(RecNames(TF_SUBGROUP_LATTICE)))]}}, "\\n");

Print("DONE\\n");
LogTo();
QUIT;
'''

TMP = LIFTING / "temp_m3_s12_fresh.g"
TMP.write_text(gap_commands)
if LOG.exists():
    LOG.unlink()

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S11+S12 fresh (this takes ~10-15 minutes)...")
proc = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_m3_s12_fresh.g"'],
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
    print(stderr[-1500:])
