"""
Test to compare ComputeCocycleSpaceViaPcgs vs ComputeCocycleSpaceOriginal
"""
import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/modules.g");  # This loads cohomology.g

# Test function to compare the two methods using ChiefFactorAsModule
TestCocycleMethodsViaChiefFactor := function(Q, M_bar)
    local module, Z1_pcgs, Z1_orig, dimPcgs, dimOrig, G;

    Print("  |Q|=", Size(Q), ", |M_bar|=", Size(M_bar), "\\n");

    # Create module using the same method as lifting algorithm
    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
    if module = fail then
        Print("  ChiefFactorAsModule returned fail\\n");
        return true;  # Can't test
    fi;

    G := module.group;
    Print("  |G|=", Size(G), ", IsAbelian=", IsAbelian(G), ", IsSolvable=", IsSolvableGroup(G), "\\n");

    # Force using Pcgs method
    if IsSolvableGroup(G) and CanEasilyComputePcgs(G) then
        Z1_pcgs := ComputeCocycleSpaceViaPcgs(module);
        if Z1_pcgs = fail then
            Print("  Pcgs method returned fail\\n");
            dimPcgs := -1;
        else
            dimPcgs := Length(Z1_pcgs);
        fi;
    else
        Print("  Pcgs method not applicable (non-solvable)\\n");
        dimPcgs := -1;
    fi;

    # Force using Original method
    Z1_orig := ComputeCocycleSpaceOriginal(module);
    dimOrig := Length(Z1_orig);

    Print("  dim(Z1_pcgs) = ", dimPcgs, ", dim(Z1_orig) = ", dimOrig, "\\n");
    if dimPcgs <> dimOrig and dimPcgs >= 0 then
        Print("  *** MISMATCH ***\\n");
        return false;
    fi;
    return true;
end;

Print("\\n========== Testing Cocycle Space Methods ==========\\n\\n");

# Test 1: S4 acting on V4 (this is the structure in partition [4])
Print("Test 1: S4 acting on V4 (Klein 4-group in S4)\\n");
S4 := SymmetricGroup(4);
V4 := Group([(1,2)(3,4), (1,3)(2,4)]);  # Klein 4-group, normal in S4
TestCocycleMethodsViaChiefFactor(S4, V4);

# Test 2: S4 x S4 chief factor
Print("\\nTest 2: S4 x S4 chief factor\\n");
S4 := SymmetricGroup(4);
shifted := ShiftGroup(S4, 4);
P := Group(Concatenation(GeneratorsOfGroup(S4), GeneratorsOfGroup(shifted)));
chief := ChiefSeries(P);
Print("  Chief series: ");
for i in [1..Length(chief)] do
    Print(Size(chief[i]), " ");
od;
Print("\\n");
# Find a solvable chief factor
for i in [1..Length(chief)-1] do
    M_bar := chief[i+1];
    if IsElementaryAbelian(chief[i]) and not IsElementaryAbelian(M_bar) then
        continue;
    fi;
    Q := P;  # Actually should use chief[i], let's simplify
od;
# Test with the second-to-last factor if elementary abelian
if Length(chief) >= 2 then
    M_bar := chief[Length(chief)-1];
    if IsElementaryAbelian(M_bar) then
        Print("  Testing last elementary abelian factor\\n");
        TestCocycleMethodsViaChiefFactor(P, M_bar);
    fi;
fi;

# Test 3: Construct a known problematic case from S8's [4,4] partition
Print("\\nTest 3: Structure from S8 [4,4] partition\\n");
S4_1 := SymmetricGroup(4);
S4_2 := ShiftGroup(S4_1, 4);
P := Group(Concatenation(GeneratorsOfGroup(S4_1), GeneratorsOfGroup(S4_2)));
# The [4,4] partition uses factors [S4, S4] with N = S4 wr C2
# Let's test one of the chief factors
chief := ChiefSeries(P);
Print("  Chief series sizes: ");
for i in [1..Length(chief)] do Print(Size(chief[i]), " "); od;
Print("\\n");
# Find first elementary abelian factor
for i in [1..Length(chief)-1] do
    if IsElementaryAbelian(chief[i+1]) then
        Print("  Testing Q=chief[", i, "], M_bar=chief[", i+1, "]\\n");
        TestCocycleMethodsViaChiefFactor(chief[i], chief[i+1]);
        break;
    fi;
od;

QUIT;
'''

# Write commands to temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_cocycle_test.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_cocycle_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running cocycle space comparison tests...")
print("=" * 60)

# Run GAP via Cygwin bash
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

try:
    stdout, stderr = process.communicate(timeout=300)
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
except subprocess.TimeoutExpired:
    process.kill()
    print("ERROR: Test timed out")
    sys.exit(1)
