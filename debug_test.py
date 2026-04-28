import subprocess
import sys
import os

# Debug test - just test specific partitions
gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_test_output.txt");
Print("Debug Test - [4,2,2] partition\\n");
Print("================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\nTesting partition [4,2,2] for S8:\\n");
Print("================================\\n\\n");

startTime := Runtime();

# Test just the [4,2,2] partition
result := FindFPFClassesForPartition(8, [4,2,2]);
elapsed := (Runtime() - startTime) / 1000.0;
Print("\\n[4,2,2] Result: ", Length(result), " classes\\n");
Print("Time: ", elapsed, " seconds\\n");

Print("\\n\\n================================\\n");
Print("Debug Test Complete\\n");
Print("================================\\n");
LogTo();
QUIT;
'''

def main():
    print("Launching GAP for debug test ([4,2,2] partition)...")
    print("Output will be logged to debug_test_output.txt")
    print()

    # Write GAP commands to a temporary file
    with open(r"C:\Users\jeffr\Downloads\Lifting\debug_test_commands.g", "w") as f:
        f.write(gap_commands)

    # GAP paths
    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

    # Convert Windows path to Cygwin path for the script
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_test_commands.g"

    # Set up environment for Cygwin
    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    try:
        print("Running GAP via Cygwin bash...")
        process = subprocess.Popen(
            [bash_exe, "--login", "-c", f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=gap_runtime
        )

        stdout, stderr = process.communicate(timeout=600)  # 10 min timeout

        if stdout:
            print("Output:")
            print(stdout)
        if stderr:
            print("Errors:")
            print(stderr)

        print(f"\nGAP exited with code: {process.returncode}")

        # Check if output file was created
        output_file = r"C:\Users\jeffr\Downloads\Lifting\debug_test_output.txt"
        if os.path.exists(output_file):
            print(f"\nOutput file created: {output_file}")
            print("\n" + "="*60)
            print("Test Output:")
            print("="*60)
            with open(output_file, 'r') as f:
                content = f.read()
                print(content)
        else:
            print("\nWarning: Output file was not created")

    except subprocess.TimeoutExpired:
        print("Process timed out after 10 minutes")
        process.kill()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
