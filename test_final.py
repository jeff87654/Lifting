"""
Final verification that S7 and S8 work correctly.
"""
import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n========== Final Verification ==========\\n\\n");

# Test S7
Print("Testing S7...\\n");
start := Runtime();
result7 := CountAllConjugacyClassesFast(7);
time7 := Runtime() - start;
Print("S7: ", result7, " (expected 96), time: ", time7/1000.0, "s\\n");

# Test S8
Print("\\nTesting S8...\\n");
start := Runtime();
result8 := CountAllConjugacyClassesFast(8);
time8 := Runtime() - start;
Print("S8: ", result8, " (expected 296), time: ", time8/1000.0, "s\\n");

Print("\\n========== Summary ==========\\n");
if result7 = 96 and result8 = 296 then
    Print("ALL TESTS PASSED\\n");
else
    Print("TESTS FAILED\\n");
    if result7 <> 96 then Print("  S7: got ", result7, " expected 96\\n"); fi;
    if result8 <> 296 then Print("  S8: got ", result8, " expected 296\\n"); fi;
fi;

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_final_test.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_final_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running final verification...")
print("=" * 60)

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
    stdout, stderr = process.communicate(timeout=1800)
    print(stdout)
except subprocess.TimeoutExpired:
    process.kill()
    print("ERROR: Test timed out")
    sys.exit(1)
