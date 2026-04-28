import subprocess
import os

gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_cocycle_debug_output.txt");
Print("Cocycle-to-Complement Debug Test\\n");
Print("=================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/cohomology.g");
Read("C:/Users/jeffr/Downloads/Lifting/modules.g");

# Test case: S4 with Klein four-group V4
Print("Test: S4 with M_bar = V4\\n");
Print("========================\\n\\n");

S4 := SymmetricGroup(4);
V4 := Group((1,2)(3,4), (1,3)(2,4));

Print("|S4| = ", Size(S4), "\\n");
Print("|V4| = ", Size(V4), "\\n");
Print("V4 is normal in S4: ", IsNormal(S4, V4), "\\n");
Print("IsElementaryAbelian(V4): ", IsElementaryAbelian(V4), "\\n\\n");

# What complements should exist?
comps := ComplementClassesRepresentatives(S4, V4);
Print("GAP's ComplementClassesRepresentatives found: ", Length(comps), " classes\\n");
for i in [1..Length(comps)] do
    Print("  C[", i, "]: |C| = ", Size(comps[i]), "\\n");
od;
Print("\\n");

# Now use our module and H^1 approach
Print("Using ChiefFactorAsModule and H^1...\\n");
module := ChiefFactorAsModule(S4, V4, TrivialSubgroup(V4));

if IsRecord(module) and IsBound(module.isNonSplit) then
    Print("Non-split extension (no complements)\\n");
elif IsRecord(module) and IsBound(module.isModuleConstructionFailed) then
    Print("Module construction failed\\n");
else
    Print("Module created successfully\\n");
    Print("  dim = ", module.dimension, "\\n");
    Print("  p = ", module.p, "\\n");
    Print("  |generators| = ", Length(module.generators), "\\n");
    Print("  |preimageGens| = ", Length(module.preimageGens), "\\n");
    Print("\\n");

    # Compute H^1
    H1 := ComputeH1(module);
    Print("H^1 computation:\\n");
    Print("  dim(Z^1) = ", Length(H1.cocycleBasis), "\\n");
    Print("  dim(B^1) = ", Length(H1.coboundaryBasis), "\\n");
    Print("  dim(H^1) = ", H1.H1Dimension, "\\n");
    Print("  |H^1| = ", H1.numComplements, " (2^dimH1 = ", 2^H1.H1Dimension, ")\\n");
    Print("\\n");

    # Build complement info
    complementInfo := BuildComplementInfo(S4, V4, module);
    Print("ComplementInfo built\\n");
    Print("  |preimageGens| = ", Length(complementInfo.preimageGens), "\\n");
    Print("  preimageGens[1] in S4: ", complementInfo.preimageGens[1] in S4, "\\n");
    Print("\\n");

    # Test cocycle enumeration
    Print("Testing CocycleToComplement:\\n");
    Print("============================\\n");

    validCount := 0;
    invalidCount := 0;

    for rep in H1.H1Representatives do
        Print("\\nCocycle: ", rep, "\\n");

        # Create complement
        C := CocycleToComplement(rep, complementInfo);
        Print("  |C| = ", Size(C), "\\n");
        Print("  Expected |C| = ", Size(S4)/Size(V4), " = 6\\n");

        # Validate
        inter := Intersection(C, V4);
        Print("  |C inter V4| = ", Size(inter), " (should be 1)\\n");
        Print("  |C * V4| = ", Size(ClosureGroup(C, V4)), " (should be ", Size(S4), ")\\n");

        if Size(C) = Size(S4)/Size(V4) and Size(inter) = 1 then
            Print("  => VALID\\n");
            validCount := validCount + 1;
        else
            Print("  => INVALID\\n");
            invalidCount := invalidCount + 1;
        fi;
    od;

    Print("\\n================\\n");
    Print("Summary: ", validCount, " valid, ", invalidCount, " invalid\\n");
    Print("Expected: ", H1.numComplements, " complements\\n");
fi;

Print("\\n========================================\\n");
Print("Debug Test Complete\\n");
Print("========================================\\n");
LogTo();
QUIT;
'''

def main():
    print("Cocycle-to-Complement Debug Test")
    print("=" * 50)
    print()

    with open(r"C:\Users\jeffr\Downloads\Lifting\test_cocycle_debug_commands.g", "w") as f:
        f.write(gap_commands)

    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_cocycle_debug_commands.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    try:
        process = subprocess.Popen(
            [bash_exe, "--login", "-c", f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=gap_runtime
        )

        stdout, stderr = process.communicate(timeout=300)

        if stdout:
            print(stdout)

        output_file = r"C:\Users\jeffr\Downloads\Lifting\test_cocycle_debug_output.txt"
        if os.path.exists(output_file):
            print("\n" + "=" * 50)
            print("Full output from log file:")
            print("=" * 50)
            with open(output_file, 'r') as f:
                print(f.read())

    except subprocess.TimeoutExpired:
        print("Process timed out")
        process.kill()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
