import subprocess
import sys
import os

# Debug test - test full C2 optimization function
gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_c2_full_output.txt");
Print("Debug C2 optimization - Full function\\n");
Print("=====================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Test the full C2 opt function for various factor combinations in [4,2,2]

partition := [4, 2, 2];
numC2 := 2;

# Get all transitive groups for degree 4
transGroups4 := List([1..NrTransitiveGroups(4)], j -> TransitiveGroup(4, j));
Print("Number of transitive groups for degree 4: ", Length(transGroups4), "\\n");
for i in [1..Length(transGroups4)] do
    Print("  T4_", i, ": ", StructureDescription(transGroups4[i]), ", size ", Size(transGroups4[i]), "\\n");
od;
Print("\\n");

totalCount := 0;
testCount := 0;

# Test with each transitive group
for T4 in transGroups4 do
    testCount := testCount + 1;
    C2 := SymmetricGroup(2);

    transFactors := [T4, C2, C2];

    # Build shifted groups
    shifted := [];
    offsets := [];
    off := 0;
    for i in [1..3] do
        Add(offsets, off);
        Add(shifted, ShiftGroup(transFactors[i], off));
        off := off + NrMovedPoints(transFactors[i]);
    od;

    Print("Test ", testCount, ": [", StructureDescription(T4), " x C2 x C2]\\n");

    # Check if all trailing factors are C2
    allC2 := ForAll([2..3], i -> Size(transFactors[i]) = 2);
    Print("  All trailing factors are C2: ", allC2, "\\n");

    if allC2 then
        startTime := Runtime();
        result := FindSubdirectsForPartitionWith2s(partition, transFactors, shifted, offsets);
        elapsed := (Runtime() - startTime) / 1000.0;

        if result <> fail then
            Print("  C2 opt found ", Length(result), " subdirects in ", elapsed, "s\\n");
            totalCount := totalCount + Length(result);
        else
            Print("  C2 opt returned fail\\n");
        fi;
    fi;
    Print("\\n");
od;

Print("Total subdirects from C2 opt: ", totalCount, "\\n");
Print("(Expected: 32 from lifting method)\\n");

Print("\\n=====================================\\n");
Print("Debug Complete\\n");
Print("=====================================\\n");
LogTo();
QUIT;
'''

def main():
    print("Launching GAP for full C2 optimization test...")
    print("Output will be logged to debug_c2_full_output.txt")
    print()

    # Write GAP commands to a temporary file
    with open(r"C:\Users\jeffr\Downloads\Lifting\debug_c2_full_commands.g", "w") as f:
        f.write(gap_commands)

    # GAP paths
    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

    # Convert Windows path to Cygwin path for the script
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_c2_full_commands.g"

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
        output_file = r"C:\Users\jeffr\Downloads\Lifting\debug_c2_full_output.txt"
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
