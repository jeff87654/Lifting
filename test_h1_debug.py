#!/usr/bin/env python3
"""Debug script to understand the H^1 generator correspondence issue."""

import subprocess
import os
import sys

gap_commands = '''
# Load the lifting algorithm (which loads cohomology and modules)
Read("C:/Users/jeffr/Downloads/Lifting/cohomology.g");
Read("C:/Users/jeffr/Downloads/Lifting/modules.g");

# Debug function to analyze generator correspondence
DebugGeneratorCorrespondence := function(Q, M_bar)
    local module, G, pcgsG, i, hom;

    Print("\\n=== Debug Generator Correspondence ===\\n");

    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));

    if module = fail then
        Print("ChiefFactorAsModule returned fail\\n");
        return;
    fi;

    G := module.group;
    Print("G = ", G, "\\n");
    Print("|G| = ", Size(G), "\\n");
    Print("module.generators = ", module.generators, "\\n");

    if CanEasilyComputePcgs(G) then
        pcgsG := Pcgs(G);
        Print("Pcgs(G) = ", List(pcgsG), "\\n");
        Print("Length(Pcgs(G)) = ", Length(pcgsG), "\\n");
        Print("Length(module.generators) = ", Length(module.generators), "\\n");

        Print("\\nComparison:\\n");
        for i in [1..Minimum(Length(module.generators), Length(pcgsG))] do
            Print("  module.generators[", i, "] = ", module.generators[i], "\\n");
            Print("  pcgs[", i, "]             = ", pcgsG[i], "\\n");
            Print("  Equal? ", module.generators[i] = pcgsG[i], "\\n\\n");
        od;
    else
        Print("Cannot easily compute Pcgs for G\\n");
    fi;
end;

# Test with S4/V4 (Klein 4-group example)
Print("\\n=== Test Case: S4 with V4 as normal subgroup ===\\n");
S4 := SymmetricGroup(4);
V4 := Group([(1,2)(3,4), (1,3)(2,4)]);
Print("S4 = ", S4, "\\n");
Print("V4 = ", V4, "\\n");
Print("|V4| = ", Size(V4), "\\n");
Print("IsNormal(S4, V4) = ", IsNormal(S4, V4), "\\n");

DebugGeneratorCorrespondence(S4, V4);

# Test with S3 x S3 / diagonal
Print("\\n=== Test Case: S3 x S3 with diagonal S3 ===\\n");
S3 := SymmetricGroup(3);
S3x := Group((1,2,3), (1,2));
S3y := Group((4,5,6), (4,5));
S3xS3 := Group(Concatenation(GeneratorsOfGroup(S3x), GeneratorsOfGroup(S3y)));
Print("S3 x S3 = ", S3xS3, "\\n");
Print("|S3 x S3| = ", Size(S3xS3), "\\n");

# Find a normal subgroup
normSubs := NormalSubgroups(S3xS3);
Print("Normal subgroups: ", List(normSubs, Size), "\\n");

# Test with first non-trivial proper normal subgroup
for N in normSubs do
    if Size(N) > 1 and Size(N) < Size(S3xS3) and IsElementaryAbelian(N) then
        Print("\\nTesting with N of size ", Size(N), "\\n");
        DebugGeneratorCorrespondence(S3xS3, N);
        break;
    fi;
od;

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_debug_h1.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_debug_h1.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running H^1 debug test...")
print("=" * 50)

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
