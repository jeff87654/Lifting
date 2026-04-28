"""Diagnose the [9,8] partition hang.

Checks:
1. Which TG(8,j) have >50 normal subgroups (triggering Goursat fallback)?
2. What is the group structure of the stuck combo?
3. How expensive is the lifting for that combo?
"""
import subprocess
import os
import time

LOG_FILE = "C:/Users/jeffr/Downloads/Lifting/diagnose_9_8.log"

gap_commands = f'''
LogTo("{LOG_FILE}");

# Check normal subgroup counts for all TG(8,j)
Print("=== Normal subgroup counts for TG(8,j), j=1..50 ===\\n");
for j in [1..50] do
    G := TransitiveGroup(8, j);
    n := Length(NormalSubgroups(G));
    if n > 20 then
        Print("  TG(8,", j, "): |G|=", Size(G), ", normals=", n,
              ", name=", StructureDescription(G), "\\n");
    fi;
od;

Print("\\n=== Normal subgroup counts for TG(9,k), k=1..34 ===\\n");
for k in [1..34] do
    G := TransitiveGroup(9, k);
    n := Length(NormalSubgroups(G));
    if n > 20 then
        Print("  TG(9,", k, "): |G|=", Size(G), ", normals=", n,
              ", name=", StructureDescription(G), "\\n");
    fi;
od;

# Now check the specific stuck combo: TG(8,4) x TG(9,14)
# (combo after [8,3] [9,14])
Print("\\n=== Stuck combo analysis ===\\n");
for j in [3..8] do
    T2 := TransitiveGroup(8, j);
    T1 := TransitiveGroup(9, 14);
    n1 := Length(NormalSubgroups(T1));
    n2 := Length(NormalSubgroups(T2));
    Print("  TG(8,", j, ") x TG(9,14): |P|=", Size(T1)*Size(T2),
          ", normals=", n1, "x", n2);
    if n1 > 50 or n2 > 50 then
        Print(" -> GOURSAT SKIP (lifting)");
    else
        Print(" -> Goursat OK");
    fi;
    Print(", TG(8,", j, ")=", StructureDescription(T2),
          " |G|=", Size(T2), "\\n");
od;

# Check chief series length for the stuck combo
Print("\\n=== Chief series for TG(8,4) x TG(9,14) ===\\n");
T1 := TransitiveGroup(9, 14);
T2 := TransitiveGroup(8, 4);
P := DirectProduct(T1, T2);
cs := ChiefSeries(P);
Print("  Chief series length: ", Length(cs), "\\n");
for i in [1..Length(cs)-1] do
    Print("  Layer ", i, ": |factor| = ", Size(cs[i])/Size(cs[i+1]),
          ", abelian = ", IsAbelian(cs[i]/cs[i+1]), "\\n");
od;
Print("  |P| = ", Size(P), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_diagnose.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_diagnose.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running GAP diagnostic...")
t0 = time.time()
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
elapsed = time.time() - t0
print(f"Done in {elapsed:.1f}s")

with open(LOG_FILE, "r") as f:
    print(f.read())
