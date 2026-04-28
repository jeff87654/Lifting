import subprocess
import os

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_images_check.log"

gap_commands = f'''
LogTo("{log_file}");
LoadPackage("images");

# Test MinimalImage on sets
G := SymmetricGroup(4);
S := [1, 3, 5];
Print("MinimalImage(S4, [1,3,5], OnSets) = ", MinimalImage(G, S, OnSets), "\\n");

# Test on a real subgroup problem
# Two non-conjugate subgroups in S6 with same orbits
H1 := Group((1,2,3,4));  # C4
H2 := Group((1,2)(3,4), (1,3)(2,4));  # V4
Print("H1 = C4, |H1| = ", Size(H1), ", orbits = ", Orbits(H1, [1..6]), "\\n");
Print("H2 = V4, |H2| = ", Size(H2), ", orbits = ", Orbits(H2, [1..6]), "\\n");

# Compute action tables (as in our code)
ActionTable := function(H, deg)
    local table, h, i;
    table := [];
    for h in H do
        for i in [1..deg] do
            AddSet(table, (i-1)*deg + i^h);
        od;
    od;
    return table;
end;

t1 := ActionTable(H1, 6);
t2 := ActionTable(H2, 6);
Print("T(H1) = ", t1, "\\n");
Print("T(H2) = ", t2, "\\n");
Print("T(H1) = T(H2)? ", t1 = t2, "\\n");
Print("H1 = H2? ", H1 = H2, "\\n");

# Better encoding: set of permutation encodings
PermEncode := function(h, deg)
    local code, i;
    code := 0;
    for i in [1..deg] do
        code := code + (i^h) * (deg+1)^(i-1);
    od;
    return code;
end;

GroupEncode := function(H, deg)
    local s;
    s := [];
    for h in H do
        AddSet(s, PermEncode(h, deg));
    od;
    return s;
end;

e1 := GroupEncode(H1, 6);
e2 := GroupEncode(H2, 6);
Print("\\nElement-based encoding:\\n");
Print("E(H1) = ", e1, "\\n");
Print("E(H2) = ", e2, "\\n");
Print("E(H1) = E(H2)? ", e1 = e2, "\\n");

# Can we use MinimalImage on sets of large integers?
# Need to encode the N action on these integers too
# This may be impractical for large groups

# Alternative: use OnSetsSets
# Encode H as set of image-tuples
TupleEncode := function(H, deg)
    local s, h;
    s := [];
    for h in H do
        Add(s, List([1..deg], i -> i^h));
    od;
    Sort(s);
    return s;
end;

te1 := TupleEncode(H1, 6);
te2 := TupleEncode(H2, 6);
Print("\\nTuple encoding:\\n");
Print("TE(H1) = ", te1, "\\n");
Print("TE(H2) = ", te2, "\\n");
Print("TE(H1) = TE(H2)? ", te1 = te2, "\\n");

# Test MinimalImage with OnSetsTuples
Print("\\nTesting MinimalImage with OnSetsTuples:\\n");
N := SymmetricGroup(6);
mi1 := MinimalImage(N, te1, OnSetsTuples);
mi2 := MinimalImage(N, te2, OnSetsTuples);
Print("MI(H1) = ", mi1, "\\n");
Print("MI(H2) = ", mi2, "\\n");
Print("MI(H1) = MI(H2)? ", mi1 = mi2, "\\n");
Print("Should be: ", RepresentativeAction(N, H1, H2) <> fail, "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

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

stdout, stderr = process.communicate(timeout=60)

log_path = r"C:\Users\jeffr\Downloads\Lifting\gap_images_check.log"
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        print(f.read())
else:
    print("Log not found")
    print("stdout:", stdout)
    print("stderr:", stderr)
