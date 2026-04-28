"""Test per-combo dedup on S14 partition [4,4,4,2] against brute-force ground truth."""
import subprocess
import os

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_s14_4442.log"

gap_commands = f'''
LogTo("{log_file}");

# Ground truth from brute-force S14 cache
Print("=== Computing ground truth for [4,4,4,2] from S14 cache ===\\n");
allGenSets := ReadAsFunction("C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache/s14_subgroups.g")();
Print("Loaded ", Length(allGenSets), " S14 conjugacy class reps\\n");

count_4442 := 0;
for genSet in allGenSets do
    if Length(genSet) > 0 then
        G := Group(List(genSet, p -> PermList(p)));
    else
        G := Group(());
    fi;
    orbs := Orbits(G, [1..14]);
    orbSizes := Reversed(SortedList(List(orbs, Length)));
    if orbSizes = [4,4,4,2] then
        count_4442 := count_4442 + 1;
    fi;
od;
Print("Ground truth [4,4,4,2]: ", count_4442, "\\n\\n");

# Test our lifting code
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

startT := Runtime();
result := FindFPFClassesForPartition(14, [4,4,4,2]);
elapsed := (Runtime() - startT) / 1000.0;
got := Length(result);

if got = count_4442 then
    Print("[4,4,4,2] : ", got, " PASS (", elapsed, "s)\\n");
else
    Print("[4,4,4,2] : ", got, " FAIL (expected ", count_4442, ") (", elapsed, "s)\\n");
fi;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands_4442.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands_4442.g"

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

stdout, stderr = process.communicate(timeout=3600)

with open(r"C:\Users\jeffr\Downloads\Lifting\gap_output_s14_4442.log", "r") as f:
    log = f.read()

for line in log.split('\n'):
    if any(k in line for k in ['PASS', 'FAIL', 'Ground truth', 'ground truth']):
        print(line)
