import subprocess
import os

gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_s10_speed_output.txt");
Print("S10 Speed Test with H^1 Orbital Optimization\\n");
Print("=============================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("Configuration:\\n");
Print("  USE_H1_COMPLEMENTS: ", USE_H1_COMPLEMENTS, "\\n");
Print("  USE_H1_ORBITAL: ", USE_H1_ORBITAL, "\\n\\n");

# Reset statistics
ResetH1TimingStats();
if IsBound(ResetH1OrbitalStats) then
    ResetH1OrbitalStats();
fi;

Print("Running S10 enumeration...\\n\\n");
startTime := Runtime();
result := CountAllConjugacyClassesFast(10);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\\n");
Print("============================================\\n");
Print("S10 Result: ", result, " (expected: 1593)\\n");
Print("Total Time: ", elapsed, " seconds\\n");
Print("============================================\\n");

if result = 1593 then
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

LogTo();
QUIT;
'''

def main():
    print("S10 Speed Test with H^1 Orbital Optimization")
    print("=" * 50)
    print()

    with open(r"C:\Users\jeffr\Downloads\Lifting\test_s10_speed_commands.g", "w") as f:
        f.write(gap_commands)

    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_s10_speed_commands.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    try:
        print("Running GAP... (this may take several minutes)")
        print()
        process = subprocess.Popen(
            [bash_exe, "--login", "-c", f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=gap_runtime
        )

        stdout, stderr = process.communicate(timeout=7200)  # 2 hour timeout

        if stdout:
            print(stdout)

        output_file = r"C:\Users\jeffr\Downloads\Lifting\test_s10_speed_output.txt"
        if os.path.exists(output_file):
            print("\n" + "=" * 50)
            print("Full output from log file:")
            print("=" * 50)
            with open(output_file, 'r') as f:
                print(f.read())

    except subprocess.TimeoutExpired:
        print("Process timed out after 2 hours")
        process.kill()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
