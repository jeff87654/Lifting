"""Test per-combo dedup on big S14 partitions against brute-force ground truth."""
import subprocess
import os

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_s14_test.log"

# Step 1: Compute ground truth per-partition FPF counts from S14 brute-force cache
# Step 2: Run our lifting code on selected big partitions and compare
gap_commands = f'''
LogTo("{log_file}");

# === Step 1: Ground truth from brute-force S14 cache ===
Print("=== Computing ground truth from S14 brute-force cache ===\\n");
allGenSets := ReadAsFunction("C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache/s14_subgroups.g")();
Print("Loaded ", Length(allGenSets), " S14 conjugacy class reps\\n");

# For each subgroup, compute its orbit partition on {{1..14}}
# FPF = no fixed points (no 1-parts in partition)
partitionCounts := rec();
for genSet in allGenSets do
    if Length(genSet) > 0 then
        G := Group(List(genSet, p -> PermList(p)));
    else
        G := Group(());
    fi;
    orbs := Orbits(G, [1..14]);
    orbSizes := SortedList(List(orbs, Length));
    # Reverse to get descending partition
    orbSizes := Reversed(orbSizes);
    key := String(orbSizes);
    if not IsBound(partitionCounts.(key)) then
        partitionCounts.(key) := 0;
    fi;
    partitionCounts.(key) := partitionCounts.(key) + 1;
od;

# Print all FPF partition counts (no 1-parts)
Print("\\n=== S14 FPF partition counts (ground truth) ===\\n");
fpfTotal := 0;
for key in SortedList(RecNames(partitionCounts)) do
    part := EvalString(key);
    if part[Length(part)] > 1 then
        Print("  ", key, " : ", partitionCounts.(key), "\\n");
        fpfTotal := fpfTotal + partitionCounts.(key);
    fi;
od;
Print("FPF total: ", fpfTotal, "\\n\\n");

# === Step 2: Test our lifting code on selected partitions ===
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed S1-S13 caches
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Clear FPF cache to test fresh
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Test partitions: pick a mix of sizes
testPartitions := [
    [7,7],        # 2-part equal
    [8,6],        # 2-part distinct
    [5,5,4],      # 3-part with repeats
    [4,4,4,2],    # 4-part with repeats
    [7,4,3],      # 3-part distinct
    [5,3,2,2,2],  # 5-part
    [3,3,2,2,2,2],# 6-part
    [8,4,2],      # 3-part distinct
];

Print("=== Testing lifting code on S14 partitions ===\\n");
allPass := true;
for part in testPartitions do
    key := String(part);
    if IsBound(partitionCounts.(key)) then
        expected := partitionCounts.(key);
    else
        Print("WARNING: no ground truth for ", key, "\\n");
        continue;
    fi;

    # Clear per-partition caches
    FPF_SUBDIRECT_CACHE := rec();

    startT := Runtime();
    result := FindFPFClassesForPartition(14, part);
    elapsed := (Runtime() - startT) / 1000.0;
    got := Length(result);

    if got = expected then
        Print("  ", key, " : ", got, " PASS (", elapsed, "s)\\n");
    else
        Print("  ", key, " : ", got, " FAIL (expected ", expected, ") (", elapsed, "s)\\n");
        allPass := false;
    fi;
od;

if allPass then
    Print("\\nAll partitions PASS!\\n");
else
    Print("\\nSome partitions FAILED!\\n");
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

with open(r"C:\Users\jeffr\Downloads\Lifting\gap_output_s14_test.log", "r") as f:
    log = f.read()

# Print just the key results
for line in log.split('\n'):
    if any(k in line for k in ['PASS', 'FAIL', 'ground truth', 'FPF total',
                                 'Testing lifting', 'All partitions', 'WARNING']):
        print(line)
    elif line.strip().startswith('[') and ':' in line:
        print(line)
