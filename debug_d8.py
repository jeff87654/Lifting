"""
Debug D8 with V4 case.
"""
import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/cohomology.g");
Read("C:/Users/jeffr/Downloads/Lifting/modules.g");

Print("\\nTest: D8 with V4 normal subgroup\\n");
Print("===================================\\n");

D8 := DihedralGroup(8);
M := First(NormalSubgroups(D8), N -> Size(N) = 4 and IsElementaryAbelian(N));

Print("|D8| = ", Size(D8), ", |M| = ", Size(M), "\\n");
Print("D8 generators: ", GeneratorsOfGroup(D8), "\\n");
Print("M generators: ", GeneratorsOfGroup(M), "\\n");

# Check GAP's complement
gapComps := ComplementClassesRepresentatives(D8, M);
Print("GAP finds ", Length(gapComps), " complement class(es)\\n");
if Length(gapComps) > 0 then
    Print("  GAP complement: ", gapComps[1], "\\n");
    Print("  |GAP comp| = ", Size(gapComps[1]), "\\n");
fi;

# Create module
module := ChiefFactorAsModule(D8, M, TrivialSubgroup(M));

Print("\\nModule info:\\n");
Print("  p = ", module.p, "\\n");
Print("  dim = ", module.dimension, "\\n");
Print("  |G = D8/M| = ", Size(module.group), "\\n");
Print("  G generators: ", module.generators, "\\n");
Print("  preimage generators: ", module.preimageGens, "\\n");
Print("  matrices:\\n");
for i in [1..Length(module.matrices)] do
    Print("    M", i, " = ", module.matrices[i], "\\n");
od;

Print("\\nComputing H^1...\\n");
H1 := ComputeH1(module);
Print("  dim H^1 = ", H1.H1Dimension, "\\n");
Print("  #representatives = ", Length(H1.H1Representatives), "\\n");
Print("  representatives:\\n");
for v in H1.H1Representatives do
    Print("    ", v, "\\n");
od;

Print("\\nConverting cocycles to complements...\\n");
complementInfo := BuildComplementInfo(D8, M, module);

for i in [1..Length(H1.H1Representatives)] do
    Print("\\nCocycle ", i, ": ", H1.H1Representatives[i], "\\n");
    C := CocycleToComplement(H1.H1Representatives[i], complementInfo);
    Print("  Generated group: ", C, "\\n");
    Print("  |C| = ", Size(C), "\\n");
    Print("  C int M = ", Intersection(C, M), ", |C int M| = ", Size(Intersection(C, M)), "\\n");
od;

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_debug_d8.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_debug_d8.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=120)
print(stdout)
if stderr:
    print("STDERR:", stderr)
