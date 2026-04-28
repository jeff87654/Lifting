import subprocess
import os

gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_322_perf_output.txt");
Print("Performance Analysis: [3,2,2] partition\\n");
Print("=========================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Reset stats
ResetH1TimingStats();
if IsBound(ResetH1OrbitalStats) then
    ResetH1OrbitalStats();
fi;

Print("Testing [3,2,2] partition of S7...\\n\\n");

# Set up partition [3,2,2] - same as in lifting_method_fast_v2.g
S3 := SymmetricGroup(3);
S2a := SymmetricGroup(2);
S2b := ShiftGroup(S2a, 3);
S2c := ShiftGroup(S2a, 5);
S3shifted := S3;

shifted := [S3shifted, S2b, S2c];
offs := [0, 3, 5];

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("|P| = ", Size(P), "\\n");
Print("Factors: S3 x S2 x S2\\n\\n");

# Time the enumeration with orbital
Print("=== With USE_H1_ORBITAL := true ===\\n");
USE_H1_ORBITAL := true;
ResetH1TimingStats();
if IsBound(ResetH1OrbitalStats) then
    ResetH1OrbitalStats();
fi;

startTime := Runtime();
result := FindFPFClassesByLifting(P, shifted, offs);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\\n");
Print("Result: ", Length(result), " classes\\n");
Print("Time: ", elapsed, " seconds\\n\\n");

Print("H^1 Timing Stats:\\n");
PrintH1TimingStats();

if IsBound(PrintH1OrbitalStats) then
    Print("\\nH^1 Orbital Stats:\\n");
    PrintH1OrbitalStats();
fi;

Print("\\n\\n========================================\\n");
Print("=== With USE_H1_ORBITAL := false ===\\n");
Print("========================================\\n\\n");

USE_H1_ORBITAL := false;
ClearH1Cache();  # Clear cache to ensure fair comparison
ResetH1TimingStats();
if IsBound(ResetH1OrbitalStats) then
    ResetH1OrbitalStats();
fi;

startTime := Runtime();
result2 := FindFPFClassesByLifting(P, shifted, offs);
elapsed2 := (Runtime() - startTime) / 1000.0;

Print("\\n");
Print("Result: ", Length(result2), " classes\\n");
Print("Time: ", elapsed2, " seconds\\n\\n");

Print("H^1 Timing Stats (without orbital):\\n");
PrintH1TimingStats();

Print("\\n========================================\\n");
Print("Comparison:\\n");
Print("  With orbital:    ", elapsed, "s\\n");
Print("  Without orbital: ", elapsed2, "s\\n");
if elapsed < elapsed2 then
    Print("  Orbital speedup: ", Float(elapsed2/elapsed), "x\\n");
elif elapsed > elapsed2 then
    Print("  Orbital slowdown: ", Float(elapsed/elapsed2), "x\\n");
else
    Print("  No difference\\n");
fi;
Print("========================================\\n");

LogTo();
QUIT;
'''

def main():
    print("Performance Analysis: [3,2,2] partition")
    print("=" * 50)
    print()

    with open(r"C:\Users\jeffr\Downloads\Lifting\test_322_perf_commands.g", "w") as f:
        f.write(gap_commands)

    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_322_perf_commands.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    try:
        print("Running performance comparison...")
        print()
        process = subprocess.Popen(
            [bash_exe, "--login", "-c", f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=gap_runtime
        )

        stdout, stderr = process.communicate(timeout=600)

        if stdout:
            print(stdout)

        output_file = r"C:\Users\jeffr\Downloads\Lifting\test_322_perf_output.txt"
        if os.path.exists(output_file):
            print("\n" + "=" * 50)
            print("Summary from log file:")
            print("=" * 50)
            with open(output_file, 'r') as f:
                content = f.read()
                # Show comparison section
                if "Comparison:" in content:
                    idx = content.find("Comparison:")
                    print(content[idx:])

    except subprocess.TimeoutExpired:
        print("Process timed out")
        process.kill()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
