"""
Debug H^1 computation.
"""
import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/cohomology.g");
Read("C:/Users/jeffr/Downloads/Lifting/modules.g");

# Test case: C2 x C2, compute H^1(C2, C2) with trivial action
Print("\\nTest: C2 x C2 (direct product)\\n");
Print("================================\\n");

G := DirectProduct(CyclicGroup(2), CyclicGroup(2));
M := Image(Embedding(G, 2));

Print("|G| = ", Size(G), ", |M| = ", Size(M), "\\n");

module := ChiefFactorAsModule(G, M, TrivialSubgroup(M));

Print("\\nModule info:\\n");
Print("  p = ", module.p, "\\n");
Print("  dim = ", module.dimension, "\\n");
Print("  |acting group| = ", Size(module.group), "\\n");
Print("  #generators = ", Length(module.generators), "\\n");
Print("  matrices:\\n");
for i in [1..Length(module.matrices)] do
    Print("    M", i, " = ", module.matrices[i], "\\n");
od;

Print("\\nComputing cocycle/coboundary spaces...\\n");
Z1 := ComputeCocycleSpace(module);
B1 := ComputeCoboundarySpace(module);

Print("  dim Z^1 = ", Length(Z1), "\\n");
Print("  dim B^1 = ", Length(B1), "\\n");
if Length(Z1) > 0 then
    Print("  Z^1 basis:\\n");
    for v in Z1 do
        Print("    ", v, "\\n");
    od;
fi;
if Length(B1) > 0 then
    Print("  B^1 basis:\\n");
    for v in B1 do
        Print("    ", v, "\\n");
    od;
fi;

H1 := ComputeH1(module);
Print("\\nH^1 result:\\n");
Print("  dim H^1 = ", H1.H1Dimension, "\\n");
Print("  #representatives = ", Length(H1.H1Representatives), "\\n");

# Compare with GAP
gapComps := ComplementClassesRepresentatives(G, M);
Print("\\nGAP ComplementClassesRepresentatives: ", Length(gapComps), " classes\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_debug.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_debug.g"

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
