import subprocess
import sys
import os

# Test just the [8,2] partition to measure impact of maximal descent threshold
gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_82_output.txt");
Print("Testing [8,2] partition with lowered maximal descent threshold\\n");
Print("=============================================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("Testing partition [8,2] for S10:\\n");
Print("================================\\n\\n");

startTime := Runtime();
result := FindFPFClassesForPartition(10, [8,2]);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\\n[8,2] Result: ", Length(result), " classes\\n");
Print("Time: ", elapsed, " seconds\\n");
Print("(Previous time was 242 seconds)\\n");

Print("\\n=============================================================\\n");
Print("Test Complete\\n");
Print("=============================================================\\n");
LogTo();
QUIT;
'''

def main():
    print("Testing [8,2] partition with lowered maximal descent threshold...")
    print("Output will be logged to test_82_output.txt")
    print()

    # Write GAP commands to a temporary file
    with open(r"C:\Users\jeffr\Downloads\Lifting\test_82_commands.g", "w") as f:
        f.write(gap_commands)

    # GAP paths
    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

    # Convert Windows path to Cygwin path for the script
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_82_commands.g"

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
        if stderr and "Syntax warning" not in stderr:
            print("Errors:")
            print(stderr)

        print(f"\nGAP exited with code: {process.returncode}")

        # Check if output file was created
        output_file = r"C:\Users\jeffr\Downloads\Lifting\test_82_output.txt"
        if os.path.exists(output_file):
            print(f"\n{'='*60}")
            print("Test Output:")
            print("="*60)
            with open(output_file, 'r') as f:
                content = f.read()
                # Filter out syntax warnings
                lines = [l for l in content.split('\n') if 'Syntax warning' not in l and 'complements :=' not in l]
                print('\n'.join(lines))
        else:
            print("\nWarning: Output file was not created")

    except subprocess.TimeoutExpired:
        print("Process timed out after 10 minutes")
        process.kill()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
