import subprocess
import sys
import os

# GAP commands to run
gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_output.txt");
Print("S14 Optimization Test Run\\n");
Print("==========================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\n\\nTesting S2 through S10:\\n");
Print("========================\\n\\n");

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];

for n in [2..10] do
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
    print("Launching GAP to test S2-S10...")
    print("Output will be logged to test_output.txt")
    print()

    # Write GAP commands to a temporary file
    with open(r"C:\Users\jeffr\Downloads\Lifting\test_commands.g", "w") as f:
        f.write(gap_commands)

    # GAP paths
    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    gap_exe = r"C:\Program Files\GAP-4.15.1\runtime\opt\gap-4.15.1\gap.exe"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

    # Convert Windows path to Cygwin path for the script
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_commands.g"

    # Set up environment for Cygwin
    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    # Create a shell script to run GAP
    bash_script = f'''#!/bin/bash
cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"
./gap.exe -q "{script_path}"
'''

    bash_script_path = r"C:\Users\jeffr\Downloads\Lifting\run_gap.sh"
    with open(bash_script_path, "w", newline='\n') as f:
        f.write(bash_script)

    try:
        print("Running GAP via Cygwin bash...")
        process = subprocess.Popen(
            [bash_exe, "--login", "-c", f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_path}"'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=gap_runtime
        )

        stdout, stderr = process.communicate(timeout=3600)  # 1 hour timeout

        if stdout:
            print("Output:")
            print(stdout)
        if stderr:
            print("Errors:")
            print(stderr)

        print(f"\nGAP exited with code: {process.returncode}")

        # Check if output file was created
        output_file = r"C:\Users\jeffr\Downloads\Lifting\test_output.txt"
        if os.path.exists(output_file):
            print(f"\nOutput file created: {output_file}")
            print("Reading output file...")
            with open(output_file, 'r') as f:
                content = f.read()
                print(content)
        else:
            print("\nWarning: Output file was not created")

    except subprocess.TimeoutExpired:
        print("Process timed out after 1 hour")
        process.kill()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
