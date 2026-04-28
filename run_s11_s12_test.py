import subprocess
import os

gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_s11_s12_output.txt");
Print("S11-S12 Test Run\\n");
Print("=================\\n\\n");

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
        Print("Status: FAIL\\n");
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
    print("Launching GAP to test S11-S12...")
    print("Output will be logged to test_s11_s12_output.txt")
    print()

    with open(r"C:\Users\jeffr\Downloads\Lifting\test_commands_s11_s12.g", "w") as f:
        f.write(gap_commands)

    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_commands_s11_s12.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    try:
        print("Running GAP via Cygwin bash...")
        process = subprocess.Popen(
            [bash_exe, "--login", "-c",
             f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=gap_runtime
        )

        stdout, stderr = process.communicate(timeout=14400)  # 4 hour timeout

        if stdout:
            print("Output:")
            print(stdout)
        if stderr:
            print("Errors:")
            print(stderr)

        print(f"\nGAP exited with code: {process.returncode}")

        output_file = r"C:\Users\jeffr\Downloads\Lifting\test_s11_s12_output.txt"
        if os.path.exists(output_file):
            print(f"\nOutput file created: {output_file}")
            print("Reading output file...")
            with open(output_file, 'r') as f:
                content = f.read()
                print(content)
        else:
            print("\nWarning: Output file was not created")

    except subprocess.TimeoutExpired:
        print("Process timed out after 4 hours")
        process.kill()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
