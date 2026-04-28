"""Parse old_655_groups.txt and create a GAP script that computes cheap invariants."""
import re
import os

INPUT_FILE = r"C:\Users\jeffr\Downloads\Lifting\old_655_groups.txt"
GAP_SCRIPT = r"C:\Users\jeffr\Downloads\Lifting\bucket_invariants.g"
OUTPUT_FILE = r"C:\Users\jeffr\Downloads\Lifting\bucket_invariants_output.txt"

# Parse the groups file - entries are "N: |G|=ORDER gens=[ ... ]" possibly multi-line
with open(INPUT_FILE) as f:
    text = f.read()

# Join continuation lines (lines that don't start with a digit followed by colon)
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

print(f"Parsed {len(entries)} group entries")

# Extract group number, order, and generators string
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

print(f"Successfully parsed {len(groups)} groups")

# Write GAP script
with open(GAP_SCRIPT, "w") as f:
    f.write("""# Compute cheap invariants for 1283 groups and bucket by conjugacy invariants
# Invariants: order, orbit_structure, nrCC, derived_length, center_size, exponent, abelian_invariants

startTime := Runtime();;

LogTo("{output}");;

groups := [];;
orders := [];;

Print("Loading groups...\\n");;

""".format(output=OUTPUT_FILE.replace("\\", "/")))

    # Write all groups
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

    # Orbit structure on [1..16]
    orbs := Orbits(G, [1..16]);;
    orbSizes := List(orbs, Length);;
    Sort(orbSizes);;

    # Number of conjugacy classes (can be slow for large groups)
    if ord <= 100000 then
        nrCC := NrConjugacyClasses(G);;
    else
        nrCC := -1;;  # skip for very large groups
    fi;;

    # Derived length
    if IsSolvableGroup(G) then
        dl := DerivedLength(G);;
    else
        dl := -1;;
    fi;;

    # Center size
    cSize := Size(Center(G));;

    # Exponent
    exp := Exponent(G);;

    # Abelian invariants
    ai := ShallowCopy(AbelianInvariants(G));;
    Sort(ai);;

    inv := [ord, orbSizes, nrCC, dl, cSize, exp, ai];;
    Add(invariants, inv);;

    if i mod 100 = 0 then
        Print("  Computed invariants for ", i, "/", nGroups, " groups (",
              Int((Runtime() - startTime)/1000), "s)\\n");;
    fi;;
od;;

Print("All invariants computed in ", Int((Runtime() - startTime)/1000), "s\\n");;

# Bucket by invariant key
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
Print("Total buckets: ", nBuckets, "\\n");;

# Count singletons vs multi-group buckets
singletons := 0;;
multiGroup := 0;;
maxBucketSize := 0;;
multiGroupList := [];;
for key in bucketKeys do
    sz := Length(bucketMap.(key));;
    if sz = 1 then
        singletons := singletons + 1;;
    else
        multiGroup := multiGroup + 1;;
        Add(multiGroupList, [sz, key, bucketMap.(key)]);;
        if sz > maxBucketSize then
            maxBucketSize := sz;;
        fi;;
    fi;;
od;;

Print("\\n=== BUCKETING SUMMARY ===\\n");;
Print("Total groups: ", nGroups, "\\n");;
Print("Total buckets: ", nBuckets, "\\n");;
Print("Singleton buckets (guaranteed non-conjugate): ", singletons, "\\n");;
Print("Multi-group buckets (need conjugacy test): ", multiGroup, "\\n");;
Print("Max bucket size: ", maxBucketSize, "\\n");;

# Count groups in multi-group buckets
groupsInMulti := 0;;
for entry in multiGroupList do
    groupsInMulti := groupsInMulti + entry[1];;
od;;
Print("Groups in multi-group buckets: ", groupsInMulti, "\\n");;
Print("Groups confirmed non-conjugate by invariants: ", nGroups - groupsInMulti + multiGroup, "\\n");;

# Show multi-group buckets
Sort(multiGroupList, function(a,b) return a[1] > b[1]; end);;
Print("\\n=== MULTI-GROUP BUCKETS (sorted by size) ===\\n");;
for entry in multiGroupList do
    Print("  Size ", entry[1], ": invariants=", entry[2], "\\n");;
    Print("    Group indices: ", entry[3], "\\n");;
od;;

Print("\\nTotal time: ", Int((Runtime() - startTime)/1000), "s\\n");;

LogTo();;
QUIT;;
""")

print(f"GAP script written to {GAP_SCRIPT}")
print(f"Output will go to {OUTPUT_FILE}")

# Count unique orders for info
from collections import Counter
order_counts = Counter(o for _, o, _ in groups)
print(f"Unique orders: {len(order_counts)}")
print(f"Largest order: {max(order_counts.keys())}")
