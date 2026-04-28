import subprocess
import os

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_onsetsets.log"

gap_commands = f'''
LogTo("{log_file}");

# Test if OnSetsSets is available with MinimalImage from images package
if TestPackageAvailability("images") <> fail then
    LoadPackage("images", false);
    Print("images package loaded\\n");
else
    Print("images package NOT available\\n");
fi;

# Check if OnSetsSets is bound
if IsBound(OnSetsSets) then
    Print("OnSetsSets is available\\n");
else
    Print("OnSetsSets is NOT available\\n");
fi;

# Test basic usage: S3 acting on {{1..3}} pairs
G := SymmetricGroup(3);
Print("Test group: S3\\n");

# Encode S3 action on {{1..9}} (deg=3, deg^2=9)
deg := 3;
gens := GeneratorsOfGroup(G);
encodedGens := [];
for g in gens do
    img := [];
    for i in [1..deg] do
        for j in [1..deg] do
            img[(i-1)*deg + j] := (i^g - 1)*deg + j^g;
        od;
    od;
    Add(encodedGens, PermList(img));
od;
N_encoded := Group(encodedGens);
Print("N_encoded order: ", Size(N_encoded), "\\n");

# Test subgroup: C3 = <(1,2,3)>
H := Group((1,2,3));
Print("H = C3, order ", Size(H), "\\n");

# Build set-of-sets encoding
faithful_table := Set(List(Elements(H), h ->
    Set([1..deg], i -> (i-1)*deg + i^h)));
Print("F(H) = ", faithful_table, "\\n");

# Try MinimalImage with OnSetsSets
if IsBound(OnSetsSets) then
    Print("Trying MinimalImage with OnSetsSets...\\n");
    result := MinimalImage(N_encoded, faithful_table, OnSetsSets);
    Print("MinimalImage result: ", result, "\\n");
    Print("SUCCESS: OnSetsSets works with MinimalImage\\n");
fi;

# Test distinguishing C3 vs identity in S3
H2 := Group(());
faithful_table2 := Set(List(Elements(H2), h ->
    Set([1..deg], i -> (i-1)*deg + i^h)));
Print("F(trivial) = ", faithful_table2, "\\n");

if IsBound(OnSetsSets) then
    result2 := MinimalImage(N_encoded, faithful_table2, OnSetsSets);
    Print("MinimalImage(trivial) = ", result2, "\\n");
    if result = result2 then
        Print("BUG: same canonical form for different groups!\\n");
    else
        Print("GOOD: different canonical forms for different groups\\n");
    fi;
fi;

# Now test the key case: C4 vs V4 in S6
Print("\\n=== Key test: C4 vs V4 in S6 ===\\n");
deg := 6;
N := SymmetricGroup(6);
gens := GeneratorsOfGroup(N);
encodedGens := [];
for g in gens do
    img := [];
    for i in [1..deg] do
        for j in [1..deg] do
            img[(i-1)*deg + j] := (i^g - 1)*deg + j^g;
        od;
    od;
    Add(encodedGens, PermList(img));
od;
N6_encoded := Group(encodedGens);

# C4 x C2 = <(1,2,3,4), (5,6)>
HC4 := Group((1,2,3,4), (5,6));
FC4 := Set(List(Elements(HC4), h -> Set([1..deg], i -> (i-1)*deg + i^h)));
Print("C4xC2 order: ", Size(HC4), ", |F| = ", Length(FC4), "\\n");

# V4 x C2 = <(1,2)(3,4), (1,3)(2,4), (5,6)>
HV4 := Group((1,2)*(3,4), (1,3)*(2,4), (5,6));
FV4 := Set(List(Elements(HV4), h -> Set([1..deg], i -> (i-1)*deg + i^h)));
Print("V4xC2 order: ", Size(HV4), ", |F| = ", Length(FV4), "\\n");

if FC4 = FV4 then
    Print("F(C4xC2) = F(V4xC2) -- STILL NOT FAITHFUL!\\n");
else
    Print("F(C4xC2) <> F(V4xC2) -- encoding is faithful\\n");
fi;

if IsBound(OnSetsSets) then
    canon_C4 := MinimalImage(N6_encoded, FC4, OnSetsSets);
    canon_V4 := MinimalImage(N6_encoded, FV4, OnSetsSets);
    Print("canon(C4xC2) = ", canon_C4, "\\n");
    Print("canon(V4xC2) = ", canon_V4, "\\n");
    if canon_C4 = canon_V4 then
        Print("FAIL: canonical forms match for non-conjugate groups!\\n");
    else
        Print("PASS: canonical forms differ for non-conjugate groups\\n");
    fi;
fi;

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

print("Testing OnSetsSets availability and faithfulness...")

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
    stdout, stderr = process.communicate(timeout=120)
except subprocess.TimeoutExpired:
    print("Timed out")
    process.kill()

log_path = r"C:\Users\jeffr\Downloads\Lifting\gap_output_onsetsets.log"
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    print(log)
else:
    print("Log not found")
    if stdout:
        print("stdout:", stdout[-2000:])
    if stderr:
        print("stderr:", stderr[-2000:])
