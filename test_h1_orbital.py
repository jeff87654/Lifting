import subprocess
import sys
import os

# GAP commands to test the H^1 orbital optimization
gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_h1_orbital_output.txt");
Print("H^1 Orbital Complement Enumeration Test\\n");
Print("========================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\\nPhase 2 Optimization: H^1 Orbital Method\\n");
Print("=========================================\\n\\n");

# First, test that h1_action.g loads correctly
Print("1. Testing module loading...\\n");
if IsBound(GetH1OrbitRepresentatives) then
    Print("   GetH1OrbitRepresentatives: LOADED\\n");
else
    Print("   GetH1OrbitRepresentatives: NOT FOUND\\n");
fi;
if IsBound(USE_H1_ORBITAL) then
    Print("   USE_H1_ORBITAL: ", USE_H1_ORBITAL, "\\n");
else
    Print("   USE_H1_ORBITAL: NOT DEFINED\\n");
fi;
Print("\\n");

# Test on a simple case: S3 x S3
Print("2. Testing S3 x S3 complement enumeration...\\n");
S3 := SymmetricGroup(3);
P := DirectProduct(S3, S3);
M_bar := Group((4,5,6), (4,5));  # Second S3 factor
Print("   |P| = ", Size(P), "\\n");
Print("   |M_bar| = ", Size(M_bar), "\\n");

# Compare orbital method vs standard
if IsBound(GetH1OrbitRepresentatives) then
    startTime := Runtime();
    orbitComps := GetH1OrbitRepresentatives(P, M_bar, P);
    orbitTime := Runtime() - startTime;
    Print("   Orbital method: ", Length(orbitComps), " complements in ", orbitTime/1000.0, "s\\n");
fi;

startTime := Runtime();
standardComps := ComplementClassesRepresentatives(P, M_bar);
standardTime := Runtime() - startTime;
Print("   Standard method: ", Length(standardComps), " complements in ", standardTime/1000.0, "s\\n");
Print("\\n");

# Test known values for S6, S7, S8
Print("3. Testing known values (S6, S7, S8)...\\n");
known := rec(
    s6 := 56,
    s7 := 96,
    s8 := 296
);

for n in [6, 7, 8] do
    Print("\\n   Testing S_", n, "...\\n");
    ResetH1OrbitalStats();
    startTime := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - startTime) / 1000.0;

    expected := known.(Concatenation("s", String(n)));
    Print("   Result: ", result, " (expected: ", expected, ")\\n");
    Print("   Time: ", elapsed, " seconds\\n");

    if result = expected then
        Print("   Status: PASS\\n");
    else
        Print("   Status: FAIL\\n");
    fi;

    # Print orbital stats
    if IsBound(PrintH1OrbitalStats) then
        PrintH1OrbitalStats();
    fi;
od;

Print("\\n\\n4. Testing S10 with orbital optimization...\\n");
Print("   This tests the [8,2] partition which is the main bottleneck.\\n\\n");
ResetH1OrbitalStats();
ResetH1TimingStats();
startTime := Runtime();
result := CountAllConjugacyClassesFast(10);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\\nS10 Result: ", result, " (expected: 1593)\\n");
Print("Total time: ", elapsed, " seconds\\n");
if result = 1593 then
    Print("Status: PASS\\n");
else
    Print("Status: FAIL\\n");
fi;

Print("\\nTiming Statistics:\\n");
PrintH1TimingStats();
if IsBound(PrintH1OrbitalStats) then
    PrintH1OrbitalStats();
fi;

Print("\\n\\n========================================\\n");
Print("Test Complete\\n");
Print("========================================\\n");
LogTo();
QUIT;
'''

def main():
    print("Testing H^1 Orbital Complement Enumeration (Phase 2)")
    print("=" * 50)
    print()
    print("Output will be logged to test_h1_orbital_output.txt")
    print()

    # Write GAP commands to a temporary file
    with open(r"C:\Users\jeffr\Downloads\Lifting\test_h1_orbital_commands.g", "w") as f:
        f.write(gap_commands)

    # GAP paths
    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

    # Convert Windows path to Cygwin path for the script
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_h1_orbital_commands.g"

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

        stdout, stderr = process.communicate(timeout=7200)  # 2 hour timeout for S10

        if stdout:
            print("Output:")
            print(stdout)
        if stderr:
            print("Errors:")
            print(stderr)

        print(f"\nGAP exited with code: {process.returncode}")

        # Check if output file was created
        output_file = r"C:\Users\jeffr\Downloads\Lifting\test_h1_orbital_output.txt"
        if os.path.exists(output_file):
            print(f"\nOutput file created: {output_file}")
            print("\n" + "=" * 50)
            print("Full output:")
            print("=" * 50)
            with open(output_file, 'r') as f:
                content = f.read()
                print(content)
        else:
            print("\nWarning: Output file was not created")

    except subprocess.TimeoutExpired:
        print("Process timed out after 2 hours")
        process.kill()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
