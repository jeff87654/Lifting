"""Generate a GAP script that loads all 1283 groups, buckets by cheap invariants,
then does pairwise conjugacy testing within each multi-group bucket."""
import re

INPUT_FILE = r"C:\Users\jeffr\Downloads\Lifting\old_655_groups.txt"
GAP_SCRIPT = r"C:\Users\jeffr\Downloads\Lifting\conjugacy_test.g"
OUTPUT_FILE = r"C:\Users\jeffr\Downloads\Lifting\conjugacy_test_output.txt"

# Parse the groups file
with open(INPUT_FILE) as f:
    text = f.read()

lines = text.split('\n')
entries = []
current = ""
for line in lines:
    stripped = line.strip()
    if not stripped:
        continue
    if re.match(r'^\d+:', stripped):
        if current:
            entries.append(current)
        current = stripped
    else:
        current += " " + stripped
if current:
    entries.append(current)

groups = []
for entry in entries:
    m = re.match(r'^(\d+):\s*\|G\|=(\d+)\s*gens=\s*\[(.+)\]\s*$', entry)
    if not m:
        print(f"FAILED to parse: {entry[:80]}...")
        continue
    idx = int(m.group(1))
    order = int(m.group(2))
    gens_str = m.group(3).strip()
    groups.append((idx, order, gens_str))

print(f"Parsed {len(groups)} groups")

with open(GAP_SCRIPT, "w") as f:
    f.write('# Conjugacy testing for 1283 groups in S16\n')
    f.write('# Bucket by cheap invariants, then pairwise IsConjugate within each bucket\n\n')
    f.write('startTime := Runtime();;\n')
    f.write(f'LogTo("{OUTPUT_FILE.replace(chr(92), "/")}");;  \n\n')

    f.write('S16 := SymmetricGroup(16);;\n')
    f.write('groups := [];;\n')
    f.write('orders := [];;\n\n')
    f.write('Print("Loading groups...\\n");;\n\n')

    for idx, order, gens_str in groups:
        f.write(f'Add(groups, Group([{gens_str}]));;\n')
        f.write(f'Add(orders, {order});;\n')

    f.write("""
nGroups := Length(groups);;
Print("Loaded ", nGroups, " groups\\n");;

# Compute invariants
Print("Computing invariants...\\n");;

invariants := [];;
for i in [1..nGroups] do
    G := groups[i];;
    ord := orders[i];;

    orbs := Orbits(G, [1..16]);;
    orbSizes := List(orbs, Length);;
    Sort(orbSizes);;

    if ord <= 100000 then
        nrCC := NrConjugacyClasses(G);;
    else
        nrCC := -1;;
    fi;;

    if IsSolvableGroup(G) then
        dl := DerivedLength(G);;
    else
        dl := -1;;
    fi;;

    cSize := Size(Center(G));;
    exp := Exponent(G);;
    ai := ShallowCopy(AbelianInvariants(G));;
    Sort(ai);;

    inv := [ord, orbSizes, nrCC, dl, cSize, exp, ai];;
    Add(invariants, inv);;

    if i mod 100 = 0 then
        Print("  Invariants: ", i, "/", nGroups, " (", Int((Runtime()-startTime)/1000), "s)\\n");;
    fi;;
od;;

Print("Invariants computed in ", Int((Runtime()-startTime)/1000), "s\\n");;

# Bucket
Print("\\nBucketing...\\n");;
bucketMap := rec();;
for i in [1..nGroups] do
    key := String(invariants[i]);;
    if not IsBound(bucketMap.(key)) then
        bucketMap.(key) := [];;
    fi;;
    Add(bucketMap.(key), i);;
od;;

bucketKeys := RecNames(bucketMap);;
nBuckets := Length(bucketKeys);;

singletons := 0;;
multiGroup := [];;
for key in bucketKeys do
    members := bucketMap.(key);;
    if Length(members) = 1 then
        singletons := singletons + 1;;
    else
        Add(multiGroup, members);;
    fi;;
od;;

# Sort multi-group buckets by size descending for progress tracking
Sort(multiGroup, function(a,b) return Length(a) > Length(b); end);;

Print("Singletons: ", singletons, "\\n");;
Print("Multi-group buckets: ", Length(multiGroup), "\\n");;

totalGroupsInMulti := Sum(multiGroup, Length);;
Print("Groups in multi-group buckets: ", totalGroupsInMulti, "\\n");;

# Conjugacy testing within each bucket
Print("\\n=== CONJUGACY TESTING ===\\n");;
conjTime := Runtime();;

totalPairs := 0;;
conjugatePairs := 0;;
nonConjugatePairs := 0;;
totalReps := singletons;;  # start with singletons

for bIdx in [1..Length(multiGroup)] do
    members := multiGroup[bIdx];;
    bSize := Length(members);;

    Print("\\nBucket ", bIdx, "/", Length(multiGroup),
          " (size ", bSize, ", indices: ", members, ")\\n");;

    # Track which members are already merged (conjugate to an earlier one)
    merged := List([1..bSize], x -> false);;
    reps := 0;;

    for i in [1..bSize] do
        if merged[i] then continue; fi;;
        reps := reps + 1;;
        gi := groups[members[i]];;

        for j in [i+1..bSize] do
            if merged[j] then continue; fi;;
            gj := groups[members[j]];;
            totalPairs := totalPairs + 1;;

            isConj := IsConjugate(S16, gi, gj);;

            if isConj then
                conjugatePairs := conjugatePairs + 1;;
                merged[j] := true;;
                Print("  CONJUGATE: ", members[i], " ~ ", members[j], "\\n");;
            else
                nonConjugatePairs := nonConjugatePairs + 1;;
            fi;;
        od;;
    od;;

    totalReps := totalReps + reps;;
    Print("  Reps in this bucket: ", reps, "/", bSize,
          " (", Int((Runtime()-conjTime)/1000), "s elapsed)\\n");;
od;;

Print("\\n=== FINAL SUMMARY ===\\n");;
Print("Total groups: ", nGroups, "\\n");;
Print("Singleton buckets: ", singletons, "\\n");;
Print("Multi-group buckets: ", Length(multiGroup), "\\n");;
Print("Conjugacy pairs tested: ", totalPairs, "\\n");;
Print("  Conjugate pairs found: ", conjugatePairs, "\\n");;
Print("  Non-conjugate pairs: ", nonConjugatePairs, "\\n");;
Print("\\nTotal non-conjugate representatives: ", totalReps, "\\n");;
Print("Total time: ", Int((Runtime()-startTime)/1000), "s\\n");;

LogTo();;
QUIT;;
""")

print(f"GAP script written to {GAP_SCRIPT}")
print(f"Output: {OUTPUT_FILE}")
