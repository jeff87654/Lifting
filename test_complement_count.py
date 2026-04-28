"""
Test to compare complement counts from H^1 vs GAP for specific cases
"""
import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/modules.g");

# Compare complement counts
TestComplementCounts := function(Q, M_bar, testName)
    local gap_complements, h1_result, module, H1;

    Print("\\n=== ", testName, " ===\\n");
    Print("  |Q|=", Size(Q), ", |M_bar|=", Size(M_bar), "\\n");

    # GAP's built-in method (ground truth)
    gap_complements := ComplementClassesRepresentatives(Q, M_bar);
    Print("  GAP built-in: ", Length(gap_complements), " complements\\n");

    # H^1 method
    h1_result := GetComplementsViaH1(Q, M_bar);
    Print("  H^1 method: ", Length(h1_result), " complements\\n");

    if Length(gap_complements) <> Length(h1_result) then
        Print("  *** MISMATCH! ***\\n");

        # Also check H^1 dimension directly
        module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
        if module <> fail then
            H1 := ComputeH1(module);
            Print("  H^1 dimension: ", H1.H1Dimension, " (expected ",
                  Log2Int(Length(gap_complements)), " for p=2)\\n");
            Print("  H^1 numComplements: ", H1.numComplements, "\\n");
        fi;

        return false;
    fi;
    return true;
end;

Print("\\n========== Testing Complement Counts ==========\\n");

# Test 1: S4 / V4
Print("\\nTest 1: S4 / V4 (from partition [4])\\n");
S4 := SymmetricGroup(4);
V4 := Group([(1,2)(3,4), (1,3)(2,4)]);
TestComplementCounts(S4, V4, "S4/V4");

# Test 2: S4 x S4 chief factor
Print("\\nTest 2: S4 x S4 structure\\n");
S4_1 := SymmetricGroup(4);
S4_2 := ShiftGroup(S4_1, 4);
P := Group(Concatenation(GeneratorsOfGroup(S4_1), GeneratorsOfGroup(S4_2)));
# Test various chief factors
chief := ChiefSeries(P);
for i in [1..Length(chief)-1] do
    if IsElementaryAbelian(chief[i+1]) and Size(chief[i+1]) > 1 then
        TestComplementCounts(chief[i], chief[i+1],
            Concatenation("P chief factor ", String(i)));
    fi;
od;

# Test 3: Quotient structures that arise in [4,4] partition
Print("\\nTest 3: Structures from [4,4] partition\\n");
# Build the actual structures used in FindFPFClassesForPartition
T := TransitiveGroup(4, 4);  # S4
shifted := [T, ShiftGroup(T, 4)];
offsets := [0, 4];
P := Group(Concatenation(GeneratorsOfGroup(shifted[1]), GeneratorsOfGroup(shifted[2])));
Print("  P = S4 x S4, |P|=", Size(P), "\\n");

# Get chief series of P
chief := ChiefSeries(P);
Print("  Chief series: ");
for term in chief do Print(Size(term), " "); od;
Print("\\n");

# Test complements through layers
for i in [1..Length(chief)-1] do
    M := chief[i];
    N := chief[i+1];
    if M = N then continue; fi;

    # Form quotient S/L where L = some subgroup containing N
    # In the lifting, we look at S = P, L = N, Q = S/L, M_bar = M/L
    if IsNormal(P, N) and Size(M) > Size(N) then
        hom := NaturalHomomorphismByNormalSubgroup(P, N);
        Q := ImagesSource(hom);
        M_bar := Image(hom, M);
        if IsElementaryAbelian(M_bar) and Size(M_bar) > 1 then
            TestComplementCounts(Q, M_bar,
                Concatenation("Layer M=", String(Size(M)), "/N=", String(Size(N))));
        fi;
    fi;
od;

QUIT;
'''

# Write commands to temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_complement_test.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_complement_test.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running complement count comparison tests...")
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
    if stderr and "Error" in stderr:
        print("STDERR:", stderr)
except subprocess.TimeoutExpired:
    process.kill()
    print("ERROR: Test timed out")
    sys.exit(1)
