"""Compute combo [[5,2],[5,2],[6,14]] and save generators for dedup."""

import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

LOG_FILE = "C:/Users/jeffr/Downloads/Lifting/combo201_gens.log"
GENS_FILE = "C:/Users/jeffr/Downloads/Lifting/combo201_gens.txt"
SCRIPT_FILE = os.path.join(LIFTING_DIR, "combo201_gens.g")

gap_code = f'''
LogTo("{LOG_FILE}");
Print("Computing combo [[5,2],[5,2],[6,14]] and saving generators\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

N := 16;
offsets := [0, 6, 11];

s1 := ShiftGroup(TransitiveGroup(6, 14), offsets[1]);
s2 := ShiftGroup(TransitiveGroup(5, 2), offsets[2]);
s3 := ShiftGroup(TransitiveGroup(5, 2), offsets[3]);
shifted := [s1, s2, s3];

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P order = ", Size(P), "\\n");

result := FindFPFClassesByLifting(P, shifted, offsets, N);
Print("Found ", Length(result), " FPF subgroups\\n");

# Save generators
PrintTo("{GENS_FILE}", "");
for i in [1..Length(result)] do
    gens := List(GeneratorsOfGroup(result[i]), g -> ListPerm(g, N));
    AppendTo("{GENS_FILE}", String(gens), "\\n");
od;
Print("Generators saved to {GENS_FILE}\\n");

# Now dedup against existing [6,5,5] groups
Print("\\nLoading existing [6,5,5] generators for dedup...\\n");
existingFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s16/gens/gens_6_5_5.txt";
existing := [];
_lines := SplitString(StringFile(existingFile), "\\n");
for _l in _lines do
    _l := NormalizedWhitespace(_l);
    if Length(_l) > 2 then
        _parsed := EvalString(_l);
        if IsList(_parsed) and Length(_parsed) > 0 then
            _gens := List(_parsed, PermList);
            Add(existing, Group(_gens));
        fi;
    fi;
od;
Print("Loaded ", Length(existing), " existing groups\\n");

# Check each new group against existing
newCount := 0;
for H in result do
    isNew := true;
    for E in existing do
        if Size(H) = Size(E) then
            ra := RepresentativeAction(SymmetricGroup(N), H, E);
            if ra <> fail then
                isNew := false;
                break;
            fi;
        fi;
    od;
    if isNew then
        newCount := newCount + 1;
        Print("  NEW group: order ", Size(H), "\\n");
    fi;
od;

Print("\\nCombo 201 result: ", Length(result), " FPF subgroups, ",
      newCount, " new (not conjugate to existing)\\n");
Print("Corrected [6,5,5] count: ", Length(existing) + newCount, "\\n");

LogTo();
QUIT;
'''

with open(SCRIPT_FILE, "w") as f:
    f.write(gap_code)

script_cygwin = SCRIPT_FILE.replace("C:\\", "/cygdrive/c/").replace("\\", "/")
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print(f"Launching...", flush=True)
start = time.time()
process = subprocess.Popen(
    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    env=env, cwd=GAP_RUNTIME
)
print(f"PID: {process.pid}", flush=True)

try:
    process.wait(timeout=600)  # 10 min timeout
    elapsed = time.time() - start
    print(f"Done in {elapsed:.0f}s", flush=True)
except subprocess.TimeoutExpired:
    process.kill()
    print("TIMEOUT", flush=True)

# Show log
log_win = LOG_FILE.replace("/", "\\")
if os.path.exists(log_win):
    with open(log_win) as f:
        print(f.read(), flush=True)
