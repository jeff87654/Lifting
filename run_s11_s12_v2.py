import subprocess
import os
import time

gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_s11_s12_v2_output.txt");
Print("S11-S12 Test Run v2 (with fail handling fix)\\n");
Print("===============================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n\\nTesting S11 and S12:\\n");
Print("========================\\n\\n");

# Known values from OEIS A005432
known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593, 3094, 10723];

for n in [11, 12] do
    Print("\\n========================================\\n");
    Print("Testing S_", n, " (expected: ", known[n], ")\\n");
    Print("========================================\\n");
    startTime := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - startTime) / 1000.0;
    Print("\\nS_", n, " Result: ", result, "\\n");
    Print("Expected: ", known[n], "\\n");
    if result = known[n] then
        Print("Status: PASS\\n");
    else
        Print("Status: FAIL (off by ", known[n] - result, ")\\n");
    fi;
    Print("Time: ", elapsed, " seconds\\n");
od;

Print("\\n\\n========================================\\n");
Print("Test Complete\\n");
Print("========================================\\n");
LogTo();
QUIT;
'''

def main():
    print("Launching GAP to test S11-S12 (v2 with fail handling fix)...")
    print()

    with open(r"C:\Users\jeffr\Downloads\Lifting\test_commands_s11_s12_v2.g", "w") as f:
        f.write(gap_commands)

    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_commands_s11_s12_v2.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    start = time.time()
    try:
        process = subprocess.Popen(
            [bash_exe, "--login", "-c",
             f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=gap_runtime
        )

        stdout, stderr = process.communicate(timeout=14400)
        wall = time.time() - start

        if stdout:
            print("Output:")
            print(stdout[-3000:])
        if stderr:
            # Only print relevant warnings
            for line in stderr.split('\n'):
                if 'rror' in line or 'FAIL' in line:
                    print("STDERR:", line)

        print(f"\nWall clock: {wall:.1f}s")
        print(f"GAP exited with code: {process.returncode}")

    except subprocess.TimeoutExpired:
        print("Process timed out after 4 hours")
        process.kill()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
