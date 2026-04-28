import subprocess
import sys
import os

# Test S8 with H^1 orbital optimization
gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_s8_orbital_output.txt");
Print("S8 Test with H^1 Orbital Optimization\\n");
Print("======================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("Configuration:\\n");
Print("  USE_H1_COMPLEMENTS: ", USE_H1_COMPLEMENTS, "\\n");
if IsBound(USE_H1_ORBITAL) then
    Print("  USE_H1_ORBITAL: ", USE_H1_ORBITAL, "\\n");
else
    Print("  USE_H1_ORBITAL: not defined\\n");
fi;
Print("\\n");

# Reset statistics
ResetH1TimingStats();
if IsBound(ResetH1OrbitalStats) then
    ResetH1OrbitalStats();
fi;

Print("Running S8 enumeration...\\n");
startTime := Runtime();
result := CountAllConjugacyClassesFast(8);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\\nS8 Result: ", result, " (expected: 296)\\n");
Print("Time: ", elapsed, " seconds\\n");

if result = 296 then
    Print("Status: PASS\\n");
else
    Print("Status: FAIL\\n");
fi;

Print("\\nH^1 Timing Statistics:\\n");
PrintH1TimingStats();

if IsBound(PrintH1OrbitalStats) then
    Print("\\nH^1 Orbital Statistics:\\n");
    PrintH1OrbitalStats();
fi;

Print("\\n========================================\\n");
Print("Test Complete\\n");
Print("========================================\\n");
LogTo();
QUIT;
'''

def main():
    print("Testing S8 with H^1 Orbital Optimization")
    print("=" * 45)
    print()

    # Write GAP commands to a temporary file
    with open(r"C:\Users\jeffr\Downloads\Lifting\test_s8_orbital_commands.g", "w") as f:
        f.write(gap_commands)

    # GAP paths
    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

    # Convert Windows path to Cygwin path for the script
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_s8_orbital_commands.g"

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

        stdout, stderr = process.communicate(timeout=1800)  # 30 minute timeout

        if stdout:
            print("Output:")
            print(stdout)
        if stderr:
            print("Errors (warnings are normal):")
            print(stderr[-2000:] if len(stderr) > 2000 else stderr)

        print(f"\nGAP exited with code: {process.returncode}")

        # Check if output file was created
        output_file = r"C:\Users\jeffr\Downloads\Lifting\test_s8_orbital_output.txt"
        if os.path.exists(output_file):
            print(f"\n{'='*45}")
            print("Full output from log file:")
            print('='*45)
            with open(output_file, 'r') as f:
                content = f.read()
                print(content)
        else:
            print("\nWarning: Output file was not created")

    except subprocess.TimeoutExpired:
        print("Process timed out after 30 minutes")
        process.kill()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
