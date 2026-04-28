"""
Test script to verify the H^1 cache fix.
The fix adds preimageGens to the cache fingerprint to prevent incorrect cache hits.
Expected result: S8 should return exactly 296 conjugacy classes of subgroups.
"""

import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Run S8 test - must return exactly 296 conjugacy classes
Print("\\n=== Testing S8 with H^1 cache enabled ===\\n");

# Verify cache is enabled (H1_CACHE_ENABLED is from cohomology.g, loaded via modules.g)
if IsBound(H1_CACHE_ENABLED) then
    Print("H1_CACHE_ENABLED = ", H1_CACHE_ENABLED, "\\n");
else
    Print("Note: H1_CACHE_ENABLED not yet bound (modules load on demand)\\n");
fi;

startTime := Runtime();
result := CountAllConjugacyClassesFast(8);
endTime := Runtime();

Print("\\nS8 result: ", result, " conjugacy classes\\n");
Print("Time: ", Float(endTime - startTime)/1000.0, " seconds\\n");

# Check expected value
if result = 296 then
    Print("\\n*** TEST PASSED: S8 returns 296 (correct) ***\\n");
else
    Print("\\n*** TEST FAILED: S8 returns ", result, " (expected 296) ***\\n");
fi;

# Show cache stats (now modules should be loaded)
if IsBound(H1_CACHE_ENABLED) then
    Print("\\nH1_CACHE_ENABLED = ", H1_CACHE_ENABLED, "\\n");
fi;
if IsBound(GetH1CacheStats) then
    Print("H^1 Cache Statistics:\\n");
    cacheStats := GetH1CacheStats();
    Print("  Cache entries: ", cacheStats.entries, "\\n");
fi;

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test_h1_cache.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_h1_cache.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S8 test with H^1 cache fix...")
print("=" * 60)

# Run GAP via Cygwin bash
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

try:
    stdout, stderr = process.communicate(timeout=600)  # 10 minute timeout for S8
    print(stdout)
    if stderr:
        print("STDERR:", stderr)

    # Check for success
    if "TEST PASSED" in stdout:
        print("\n" + "=" * 60)
        print("H^1 cache fix VERIFIED - S8 returns correct result!")
        sys.exit(0)
    elif "TEST FAILED" in stdout:
        print("\n" + "=" * 60)
        print("H^1 cache fix FAILED - S8 returns incorrect result!")
        sys.exit(1)
    else:
        print("\n" + "=" * 60)
        print("Test result unclear - check output above")
        sys.exit(2)

except subprocess.TimeoutExpired:
    process.kill()
    print("ERROR: Test timed out after 10 minutes")
    sys.exit(3)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(4)
