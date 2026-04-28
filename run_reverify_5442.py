import subprocess
import os
import time

gens_file = r"C:\Users\jeffr\Downloads\Lifting\parallel_s15\gens\gens_5_4_4_2.txt"
parsed_file = r"C:\Users\jeffr\Downloads\Lifting\temp_reverify_groups.g"
commands_file = r"C:\Users\jeffr\Downloads\Lifting\temp_reverify_commands.g"
log_file = "C:/Users/jeffr/Downloads/Lifting/gap_reverify_5442.log"

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
    f.write("_REVERIFY_GROUPS := [\n")
    for i, entry in enumerate(entries):
        comma = "," if i < len(entries) - 1 else ""
        f.write(f"  Group({entry}){comma}\n")
    f.write("];\n")

print(f"Wrote {parsed_file}")

# Step 2: Write GAP commands - fully self-contained, no external libraries
gap_commands = r'''
LogTo("''' + log_file + r'''");

Print("=== INDEPENDENT RE-VERIFICATION OF 5442 PARTITION ===\n");
Print("Method: Novel invariants + full S15 conjugacy testing\n");
Print("Started\n\n");

# Load the pre-parsed groups
Read("C:/Users/jeffr/Downloads/Lifting/temp_reverify_groups.g");
groups := _REVERIFY_GROUPS;
Print("Loaded ", Length(groups), " groups\n");

# Standalone InvariantKey - hash long keys to valid GAP record identifiers
InvariantKey := function(inv)
    local s, hash, i, c;
    s := String(inv);
    if Length(s) <= 900 then
        # Make it a valid identifier: replace non-alphanumeric with _
        s := ReplacedString(s, " ", "");
        s := ReplacedString(s, "[", "L");
        s := ReplacedString(s, "]", "R");
        s := ReplacedString(s, ",", "_");
        s := ReplacedString(s, "(", "P");
        s := ReplacedString(s, ")", "Q");
        s := ReplacedString(s, "-", "M");
        s := ReplacedString(s, "\"", "");
        s := ReplacedString(s, ".", "D");
        s := ReplacedString(s, "/", "S");
        s := ReplacedString(s, ":", "C");
        s := Concatenation("k", s);
        return s;
    fi;
    # Hash for long strings
    hash := 0;
    for i in [1..Length(s)] do
        c := IntChar(s[i]);
        hash := (hash * 31 + c) mod (2^28);
    od;
    return Concatenation("h", String(hash), "L", String(Length(s)));
end;

########################################
# PHASE 1: Novel Cheap Invariants
########################################
Print("\n=== PHASE 1: Novel Cheap Invariants ===\n");

NewCheapInvariant := function(H)
    local inv, sizeH, primes, sylSizes, p;
    sizeH := Size(H);
    inv := [sizeH];
    Add(inv, Size(FrattiniSubgroup(H)));
    Add(inv, Size(FittingSubgroup(H)));
    Add(inv, Size(Socle(H)));
    Add(inv, IsSupersolvable(H));
    primes := PrimeDivisors(sizeH);
    sylSizes := List(primes, p -> [p, Size(SylowSubgroup(H, p))]);
    Add(inv, sylSizes);
    Add(inv, Length(MaximalSubgroupClassReps(H)));
    return inv;
end;

byInvariant := rec();
t0 := Runtime();
for i in [1..Length(groups)] do
    H := groups[i];
    key := InvariantKey(NewCheapInvariant(H));
    if not IsBound(byInvariant.(key)) then
        byInvariant.(key) := [];
    fi;
    Add(byInvariant.(key), [i, H]);
    if i mod 250 = 0 then
        Print("  Phase 1 invariants: ", i, "/", Length(groups), "\n");
    fi;
od;
t1 := Runtime();
Print("Phase 1 time: ", StringTime(t1 - t0), "\n");

keys := RecNames(byInvariant);
Print("Phase 1 buckets: ", Length(keys), "\n");

sizes := List(keys, k -> Length(byInvariant.(k)));
Sort(sizes);
Print("Bucket sizes: min=", sizes[1], " max=", sizes[Length(sizes)],
      " median=", sizes[Int(Length(sizes)/2)+1], "\n");
nontrivial := Filtered(sizes, s -> s > 1);
Print("Buckets of size > 1: ", Length(nontrivial), "\n");
totalP1Pairs := Sum(sizes, s -> s*(s-1)/2);
Print("Total pairs after Phase 1: ", totalP1Pairs, "\n");

########################################
# PHASE 2: Expensive Novel Invariants (collision buckets only)
########################################
Print("\n=== PHASE 2: Expensive Novel Invariants ===\n");

NewExpensiveInvariant := function(H)
    local inv, sizeH, orderHist, x, o, okey, okeys, sorted;
    sizeH := Size(H);
    inv := [];
    if sizeH <= 50000 then
        Add(inv, Length(NormalSubgroups(H)));
    else
        Add(inv, -1);
    fi;
    Add(inv, Length(ChiefSeries(H)) - 1);
    # Element order histogram
    if sizeH <= 5000 then
        orderHist := rec();
        for x in H do
            o := Order(x);
            okey := String(o);
            if IsBound(orderHist.(okey)) then
                orderHist.(okey) := orderHist.(okey) + 1;
            else
                orderHist.(okey) := 1;
            fi;
        od;
        # Convert to sorted list of pairs for canonical form
        okeys := RecNames(orderHist);
        sorted := List(okeys, ok -> [Int(ok), orderHist.(ok)]);
        Sort(sorted);
        Add(inv, sorted);
    else
        Add(inv, -1);
    fi;
    return inv;
end;

refinedBuckets := rec();
singletonsP1 := 0;
groupsNeedingP2 := 0;
t0 := Runtime();
bucketNum := 0;
for k in keys do
    bucket := byInvariant.(k);
    if Length(bucket) = 1 then
        singletonsP1 := singletonsP1 + 1;
        continue;
    fi;
    groupsNeedingP2 := groupsNeedingP2 + Length(bucket);
    # Refine this bucket with expensive invariants
    for entry in bucket do
        i := entry[1];
        H := entry[2];
        expKey := InvariantKey(Concatenation(String(NewCheapInvariant(H)),
                               String(NewExpensiveInvariant(H))));
        if not IsBound(refinedBuckets.(expKey)) then
            refinedBuckets.(expKey) := [];
        fi;
        Add(refinedBuckets.(expKey), [i, H]);
    od;
    bucketNum := bucketNum + 1;
    if bucketNum mod 50 = 0 then
        Print("  Phase 2: refined ", bucketNum, " buckets\n");
    fi;
od;
t1 := Runtime();
Print("Phase 2 time: ", StringTime(t1 - t0), "\n");

rkeys := RecNames(refinedBuckets);
Print("Refined buckets: ", Length(rkeys), "\n");
Print("Groups needing Phase 2: ", groupsNeedingP2, "\n");

rsizes := List(rkeys, k -> Length(refinedBuckets.(k)));
Sort(rsizes);
Print("Refined bucket sizes: min=", rsizes[1], " max=", rsizes[Length(rsizes)],
      " median=", rsizes[Int(Length(rsizes)/2)+1], "\n");
rnontrivial := Filtered(rsizes, s -> s > 1);
Print("Refined buckets of size > 1: ", Length(rnontrivial), "\n");
totalP2Pairs := Sum(rsizes, s -> s*(s-1)/2);
Print("Total pairs after Phase 2: ", totalP2Pairs, "\n");

########################################
# PHASE 3: Full S15 Conjugacy Testing
########################################
Print("\n=== PHASE 3: Full S15 Conjugacy Testing ===\n");
Print("Using RepresentativeAction(SymmetricGroup(15), H1, H2)\n");
Print("This is STRICTLY STRONGER than the original normalizer test\n\n");

S15 := SymmetricGroup(15);
duplicates := [];
checkedPairs := 0;
bucketsDone := 0;
t0 := Runtime();

for k in rkeys do
    bucket := refinedBuckets.(k);
    if Length(bucket) > 1 then
        bucketsDone := bucketsDone + 1;
        if Length(bucket) > 10 then
            Print("  Large bucket (size ", Length(bucket), "): checking...\n");
        fi;
        for i in [1..Length(bucket)] do
            for j in [i+1..Length(bucket)] do
                checkedPairs := checkedPairs + 1;
                if RepresentativeAction(S15, bucket[i][2], bucket[j][2]) <> fail then
                    Add(duplicates, [bucket[i][1], bucket[j][1]]);
                    Print("  DUPLICATE FOUND: group ", bucket[i][1],
                          " ~ group ", bucket[j][1], "\n");
                fi;
            od;
        od;
        if bucketsDone mod 50 = 0 then
            Print("  Phase 3: checked ", checkedPairs, " pairs in ",
                  bucketsDone, " buckets (", Length(duplicates), " duplicates)\n");
        fi;
    fi;
od;
t1 := Runtime();
Print("Phase 3 time: ", StringTime(t1 - t0), "\n");

########################################
# FINAL RESULTS
########################################
Print("\n========================================\n");
Print("=== INDEPENDENT RE-VERIFICATION RESULTS ===\n");
Print("========================================\n");
Print("Total groups: ", Length(groups), "\n");
Print("Phase 1 buckets (novel cheap invariants): ", Length(keys), "\n");
Print("Phase 1 singletons: ", singletonsP1, "\n");
Print("Phase 2 refined buckets: ", Length(rkeys), "\n");
Print("Phase 2 non-singletons: ", Length(rnontrivial), "\n");
Print("Phase 3 pairwise checks (full S15): ", checkedPairs, "\n");
Print("DUPLICATES FOUND: ", Length(duplicates), "\n");

if Length(duplicates) > 0 then
    Print("\nDuplicate pairs (group indices):\n");
    for pair in duplicates do
        Print("  group ", pair[1], " ~ group ", pair[2], "\n");
    od;
    Print("\nDistinct classes: ", Length(groups) - Length(duplicates), "\n");
else
    Print("\nALL ", Length(groups),
          " GROUPS ARE PAIRWISE NON-CONJUGATE IN S15\n");
    Print("(tested with full SymmetricGroup(15), not just Young normalizer)\n");
fi;

########################################
# SANITY CHECK: Group order distribution
########################################
Print("\n=== SANITY CHECK: Group Order Distribution ===\n");
orderDist := rec();
for i in [1..Length(groups)] do
    o := Size(groups[i]);
    key := String(o);
    if IsBound(orderDist.(key)) then
        orderDist.(key) := orderDist.(key) + 1;
    else
        orderDist.(key) := 1;
    fi;
od;
odKeys := RecNames(orderDist);
odPairs := List(odKeys, k -> [Int(k), orderDist.(k)]);
Sort(odPairs);
Print("Order -> Count (", Length(odPairs), " distinct orders):\n");
for pair in odPairs do
    Print("  ", pair[1], " -> ", pair[2], "\n");
od;

Print("\n=== COMPARISON WITH ORIGINAL ===\n");
Print("Original: 4407 buckets, 191 non-singletons, 2778 pairs, 0 duplicates\n");
Print("This run: ", Length(keys), " buckets, ", Length(nontrivial),
      " non-singletons, ", checkedPairs, " pairs (full S15), ",
      Length(duplicates), " duplicates\n");

LogTo();
QUIT;
'''

with open(commands_file, "w") as f:
    f.write(gap_commands)

print(f"Wrote GAP commands to {commands_file}")

# Step 3: Launch GAP
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_reverify_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting GAP re-verification at {time.strftime('%H:%M:%S')}")
print("Expected runtime: 17-40 minutes")
print(f"Log file: {log_file}")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 8g "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=14400)

print(f"\nGAP finished at {time.strftime('%H:%M:%S')}")
print(f"Exit code: {process.returncode}")

if stderr.strip():
    err_lines = [l for l in stderr.split('\n') if 'Error' in l]
    if err_lines:
        print(f"ERRORS:\n" + "\n".join(err_lines[:10]))

# Print the log
log_path = log_file.replace("/", os.sep)
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    print(log[-8000:] if len(log) > 8000 else log)
else:
    print("WARNING: Log file not created")
    if stdout.strip():
        print("STDOUT:")
        print(stdout[-5000:] if len(stdout) > 5000 else stdout)
