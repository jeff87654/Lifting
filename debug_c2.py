import subprocess
import sys
import os

# Debug test - investigate C2 optimization
gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_c2_output.txt");
Print("Debug C2 optimization\\n");
Print("======================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Test the quotient map computation for S4
Print("Testing GetQuotientMapsToC2 for S4:\\n");
S4 := SymmetricGroup(4);
info := GetQuotientMapsToC2(S4);
Print("Dimension (r): ", info.dimension, "\\n");
Print("Number of index-2 subgroups: ", Length(info.kernels), "\\n\\n");

# For [4,2,2], we have T = S4, k = 2 C2 factors
# So we need to enumerate subdirects of C2^r x C2^2
r := info.dimension;
k := 2;
Print("For [4,2,2]: r = ", r, ", k = ", k, "\\n");
Print("Need to enumerate subdirects of C2^", r, " x C2^", k, " = C2^", r+k, "\\n");
Print("Total space size: ", 2^(r+k), "\\n");
Print("Number of non-zero vectors: ", 2^(r+k) - 1, "\\n\\n");

# The problem is that we're enumerating all Combinations of vectors
# For dim d subspaces, we check C(2^n-1, d) combinations
# For n=3 (r=1, k=2): C(7, 1) + C(7, 2) + C(7, 3) = 7 + 21 + 35 = 63 - manageable
# But we also need to check subdirect conditions

Print("Testing EnumerateSubdirectSubspacesRplusK(", r, ", ", k, "):\\n");
startTime := Runtime();
subspaces := EnumerateSubdirectSubspacesRplusK(r, k);
elapsed := (Runtime() - startTime) / 1000.0;
Print("Found ", Length(subspaces), " subdirect subspaces in ", elapsed, " seconds\\n\\n");

# Now test with D4 (dihedral group of order 8)
Print("Testing GetQuotientMapsToC2 for D8 (dihedral):\\n");
D8 := DihedralGroup(IsPermGroup, 8);
info := GetQuotientMapsToC2(D8);
Print("Dimension (r): ", info.dimension, "\\n\\n");

Print("======================\\n");
Print("Debug Complete\\n");
Print("======================\\n");
LogTo();
QUIT;
'''

def main():
    print("Launching GAP for C2 debug test...")
    print("Output will be logged to debug_c2_output.txt")
    print()

    # Write GAP commands to a temporary file
    with open(r"C:\Users\jeffr\Downloads\Lifting\debug_c2_commands.g", "w") as f:
        f.write(gap_commands)

    # GAP paths
    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

    # Convert Windows path to Cygwin path for the script
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_c2_commands.g"

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

        stdout, stderr = process.communicate(timeout=120)  # 2 min timeout

        if stdout:
            print("Output:")
            print(stdout)
        if stderr:
            print("Errors:")
            print(stderr)

        print(f"\nGAP exited with code: {process.returncode}")

        # Check if output file was created
        output_file = r"C:\Users\jeffr\Downloads\Lifting\debug_c2_output.txt"
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
        print("Process timed out after 2 minutes")
        process.kill()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
