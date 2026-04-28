import subprocess
import os

gap_commands = '''
Print("=== S4 ===\\n");
G := SymmetricGroup(4);
Print("IsSolvable: ", IsSolvableGroup(G), "\\n");
Print("CanEasilyComputePcgs: ", CanEasilyComputePcgs(G), "\\n");
pcgs := Pcgs(G);
Print("Pcgs(G) = ", pcgs, "\\n");
Print("Length(Pcgs(G)) = ", Length(pcgs), "\\n");

Print("\\n=== PC group (cyclic) ===\\n");
C6 := CyclicGroup(6);
Print("IsSolvable: ", IsSolvableGroup(C6), "\\n");
Print("CanEasilyComputePcgs: ", CanEasilyComputePcgs(C6), "\\n");

Print("\\n=== Quotient group S4/V4 ===\\n");
V4 := Group([(1,2)(3,4), (1,3)(2,4)]);
hom := NaturalHomomorphismByNormalSubgroup(G, V4);
Q := ImagesSource(hom);
Print("Q = ", Q, "\\n");
Print("IsSolvable: ", IsSolvableGroup(Q), "\\n");
Print("CanEasilyComputePcgs: ", CanEasilyComputePcgs(Q), "\\n");
pcgsQ := Pcgs(Q);
Print("Pcgs(Q) = ", List(pcgsQ), "\\n");

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_pcgs.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_pcgs.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=60)
print(stdout)
if stderr:
    print("STDERR:", stderr)
