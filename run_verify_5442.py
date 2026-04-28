import subprocess
import os
import time
import re

gens_file = r"C:\Users\jeffr\Downloads\Lifting\parallel_s15\gens\gens_5_4_4_2.txt"
parsed_file = r"C:\Users\jeffr\Downloads\Lifting\temp_parsed_groups.g"
log_file = "C:/Users/jeffr/Downloads/Lifting/gap_verify_5442.log"

# Step 1: Preprocess gens file - join continuation lines and wrap in Group()
print("Preprocessing gens file...")
with open(gens_file, "r") as f:
    content = f.read()

# Join continuation lines: lines that don't start with '[' are continuations
lines = content.split('\n')
entries = []
current = ""
for line in lines:
    stripped = line.strip()
    if not stripped:
        if current:
            entries.append(current)
            current = ""
        continue
    if stripped.startswith('[') and current:
        entries.append(current)
        current = stripped
    elif stripped.startswith('['):
        current = stripped
    else:
        current += " " + stripped
if current:
    entries.append(current)

print(f"Found {len(entries)} groups")

# Write as GAP-readable file
with open(parsed_file, "w") as f:
    f.write("_VERIFY_GROUPS := [\n")
    for i, entry in enumerate(entries):
        comma = "," if i < len(entries) - 1 else ""
        f.write(f"  Group({entry}){comma}\n")
    f.write("];\n")

print(f"Wrote {parsed_file}")

# Step 2: Run GAP verification
gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load the pre-parsed groups
Read("C:/Users/jeffr/Downloads/Lifting/temp_parsed_groups.g");
groups := _VERIFY_GROUPS;
Print("Loaded ", Length(groups), " groups\\n");

# Build the partition normalizer N for [5,4,4,2]
partition := [5,4,4,2];
n := Sum(partition);
N := BuildConjugacyTestGroup(n, partition);
Print("|N| = ", Size(N), "\\n");

# Set block ranges for invariant computation
CURRENT_BLOCK_RANGES := [];
off_acc := 0;
for i in [1..Length(partition)] do
    Add(CURRENT_BLOCK_RANGES, [off_acc + 1, off_acc + partition[i]]);
    off_acc := off_acc + partition[i];
od;

# Choose invariant function (repeated parts -> full invariant)
if Length(partition) <> Length(Set(partition)) then
    invFunc := ComputeSubgroupInvariant;
else
    invFunc := CheapSubgroupInvariant;
fi;
Print("Using full invariant (repeated parts)\\n");

# Bucket by invariant
Print("Computing invariants...\\n");
byInvariant := rec();
t0 := Runtime();
for i in [1..Length(groups)] do
    H := groups[i];
    key := InvariantKey(invFunc(H));
    if not IsBound(byInvariant.(key)) then
        byInvariant.(key) := [];
    fi;
    Add(byInvariant.(key), [i, H]);
    if i mod 500 = 0 then
        Print("  invariants computed: ", i, "/", Length(groups), "\\n");
    fi;
od;
t1 := Runtime();
Print("Invariant computation: ", StringTime(t1 - t0), "\\n");

keys := RecNames(byInvariant);
Print("Number of invariant buckets: ", Length(keys), "\\n");

# Show bucket size distribution
sizes := List(keys, k -> Length(byInvariant.(k)));
Sort(sizes);
Print("Bucket sizes: min=", sizes[1], " max=", sizes[Length(sizes)],
      " median=", sizes[Int(Length(sizes)/2)+1], "\\n");
nontrivial := Filtered(sizes, s -> s > 1);
Print("Buckets of size > 1: ", Length(nontrivial), "\\n");
totalPairs := Sum(sizes, s -> s*(s-1)/2);
Print("Total pairwise checks needed: ", totalPairs, "\\n");

# Check pairwise conjugacy within each bucket
duplicates := [];
t0 := Runtime();
checkedPairs := 0;
bucketsDone := 0;
for k in keys do
    bucket := byInvariant.(k);
    if Length(bucket) > 1 then
        bucketsDone := bucketsDone + 1;
        for i in [1..Length(bucket)] do
            for j in [i+1..Length(bucket)] do
                checkedPairs := checkedPairs + 1;
                if RepresentativeAction(N, bucket[i][2], bucket[j][2]) <> fail then
                    Add(duplicates, [bucket[i][1], bucket[j][1]]);
                    Print("  DUPLICATE: group ", bucket[i][1], " ~ group ", bucket[j][1], "\\n");
                fi;
            od;
        od;
        if bucketsDone mod 100 = 0 then
            Print("  checked ", checkedPairs, " pairs in ", bucketsDone,
                  " buckets (", Length(duplicates), " duplicates)\\n");
        fi;
    fi;
od;
t1 := Runtime();

Print("\\n=== RESULTS ===\\n");
Print("Total groups: ", Length(groups), "\\n");
Print("Invariant buckets: ", Length(keys), "\\n");
Print("Pairwise checks: ", checkedPairs, "\\n");
Print("Time for conjugacy checks: ", StringTime(t1 - t0), "\\n");
Print("Duplicates found: ", Length(duplicates), "\\n");

if Length(duplicates) > 0 then
    Print("\\nDuplicate pairs (group indices):\\n");
    for pair in duplicates do
        Print("  group ", pair[1], " ~ group ", pair[2], "\\n");
    od;
    Print("\\nDistinct classes: ", Length(groups) - Length(duplicates), "\\n");
else
    Print("ALL ", Length(groups), " GROUPS ARE PAIRWISE NON-CONJUGATE\\n");
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

print(f"Starting GAP verification at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=14400)

print(f"GAP finished at {time.strftime('%H:%M:%S')}")
if stderr.strip():
    err_lines = [l for l in stderr.split('\n') if 'Error' in l]
    if err_lines:
        print(f"ERRORS:\n" + "\n".join(err_lines[:10]))
with open(log_file.replace("/", os.sep), "r") as f:
    log = f.read()
print(log[-5000:] if len(log) > 5000 else log)
