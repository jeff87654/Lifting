import subprocess
import sys
import os

# Debug test - investigate C2 optimization step by step
gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_c2_detailed_output.txt");
Print("Debug C2 optimization - detailed\\n");
Print("=================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Manually trace through the [4,2,2] case

Print("Setting up [4,2,2] partition:\\n");
partition := [4, 2, 2];
transFactors := [SymmetricGroup(4), SymmetricGroup(2), SymmetricGroup(2)];

# Build shifted groups
shifted := [];
offsets := [];
off := 0;
for i in [1..3] do
    Add(offsets, off);
    Add(shifted, ShiftGroup(transFactors[i], off));
    off := off + NrMovedPoints(transFactors[i]);
od;

Print("Offsets: ", offsets, "\\n");
Print("Shifted group sizes: ", List(shifted, Size), "\\n\\n");

# Count C2 factors
numC2 := 2;  # Last two factors
nonC2Start := 1;
k := numC2;

Print("numC2 = ", numC2, "\\n");
Print("nonC2Start = ", nonC2Start, "\\n\\n");

# The mixed factor is just S4
mixed := shifted[1];
Print("Mixed factor (S4) size: ", Size(mixed), "\\n");

# Get quotient maps
quotientInfo := GetQuotientMapsToC2(mixed);
r := quotientInfo.dimension;
kernels := quotientInfo.kernels;
Print("r (dimension of Hom(S4, C2)): ", r, "\\n");
Print("Number of kernels: ", Length(kernels), "\\n\\n");

# Enumerate subspaces
Print("Enumerating subdirect subspaces of C2^", r+k, "...\\n");
startTime := Runtime();
allSubspaces := EnumerateSubdirectSubspacesRplusK(r, k);
Print("Found ", Length(allSubspaces), " subspaces in ", (Runtime()-startTime)/1000.0, "s\\n\\n");

# Test building subdirects
Print("Building subdirects from each subspace...\\n");
count := 0;
fpfCount := 0;
for subspace in allSubspaces do
    count := count + 1;
    Print("Subspace ", count, "/", Length(allSubspaces), ": ");

    startTime := Runtime();
    S := BuildSubdirectFromSubspace(mixed, kernels, subspace, shifted, offsets, k, nonC2Start);
    buildTime := (Runtime()-startTime)/1000.0;

    Print("Built group of size ", Size(S), " in ", buildTime, "s, ");

    startTime := Runtime();
    isFPF := IsFPFSubdirect(S, shifted, offsets);
    fpfTime := (Runtime()-startTime)/1000.0;

    Print("FPF check: ", isFPF, " in ", fpfTime, "s\\n");

    if isFPF then
        fpfCount := fpfCount + 1;
    fi;
od;

Print("\\nTotal FPF subdirects found: ", fpfCount, "\\n");

Print("\\n=================================\\n");
Print("Debug Complete\\n");
Print("=================================\\n");
LogTo();
QUIT;
'''

def main():
    print("Launching GAP for detailed C2 debug test...")
    print("Output will be logged to debug_c2_detailed_output.txt")
    print()

    # Write GAP commands to a temporary file
    with open(r"C:\Users\jeffr\Downloads\Lifting\debug_c2_detailed_commands.g", "w") as f:
        f.write(gap_commands)

    # GAP paths
    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

    # Convert Windows path to Cygwin path for the script
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_c2_detailed_commands.g"

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

        stdout, stderr = process.communicate(timeout=300)  # 5 min timeout

        if stdout:
            print("Output:")
            print(stdout)
        if stderr:
            print("Errors:")
            print(stderr)

        print(f"\nGAP exited with code: {process.returncode}")

        # Check if output file was created
        output_file = r"C:\Users\jeffr\Downloads\Lifting\debug_c2_detailed_output.txt"
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
        print("Process timed out after 5 minutes")
        process.kill()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
