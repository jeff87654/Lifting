"""Build worker_506 script + 160-combo manifest for focused S_n fast path
validation.

Each combo is re-computed from scratch with the new code, and the result
is written to parallel_s18/[partition]/<combofile>.g — replacing the old
entry. This feeds into diff_rerun.py naturally for before/after comparison.
"""
import os, re
from collections import defaultdict

NATURAL_SN_TAGS = {(5, 5), (6, 16), (7, 7), (8, 50), (9, 34), (10, 45)}
ISO_SN = {
    5: [(5,5), (6,14), (10,12), (10,13), (12,74), (15,10)],
    6: [(6,16), (10,32), (12,183), (15,28)],
    7: [(7,7), (14,46)],
    8: [(8,50), (16,1838)],
}
iso_sn_by_deg = defaultdict(list)
for n, tags in ISO_SN.items():
    for d, t in tags:
        iso_sn_by_deg[d].append((d, t, n))

def bug_sig(fn):
    tags = [(int(d), int(t)) for d, t in re.findall(r"\[(\d+),(\d+)\]", fn)]
    if len(tags) < 3: return None
    naturals = [(i, t) for i, t in enumerate(tags) if t in NATURAL_SN_TAGS]
    if not naturals: return None
    for i, (nd, nt) in naturals:
        for j, (d, t) in enumerate(tags):
            if j == i: continue
            for (cd, ct, cn) in iso_sn_by_deg.get(d, []):
                if ct == t and cn == nd:
                    return tags
    return None

PREBUG = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18_prebugfix_backup"

# Collect (partition_tuple, [factor_tuples in ASCENDING degree order])
combos = []
for part_dir in sorted(os.listdir(PREBUG)):
    d = os.path.join(PREBUG, part_dir)
    if not os.path.isdir(d): continue
    partition = tuple(int(x) for x in part_dir.strip("[]").split(","))
    for combo_file in os.listdir(d):
        if not combo_file.endswith(".g"): continue
        tags = bug_sig(combo_file)
        if tags is None: continue
        combos.append((partition, combo_file, tags))

print(f"Collected {len(combos)} bug-signature combos.")

# Write worker_506 script. Each combo:
#  1. Sort partition descending (matches existing pipeline).
#  2. Map combo_file tags (ASCENDING order) to partition-descending order.
#     Multiset match: given partition [10,6,2] (desc), tags [(2,1),(6,16),(10,32)]
#     (asc): we need factors in order matching each block's degree.
#     For each block degree from high to low, pull the factor tag whose
#     degree matches (first-match, consuming tag).
#  3. Shift each factor by cumulative offset.
#  4. Run FindFPFClassesByLifting.
#  5. Dedup with BuildPerComboNormalizer.
#  6. Write via _WriteComboResults.

# GAP array-of-records: each record has partition, cacheKey (combo file),
# factor tuples in DESCENDING degree order matching partition.
gap_combos = []
for partition, combo_file, tags in combos:
    desc_part = sorted(partition, reverse=True)
    # tags are already sorted (file format is ASCENDING by deg).
    # Map to DESCENDING.
    remaining = list(tags)
    factor_order = []
    for deg in desc_part:
        # Pick first tag with matching degree
        for k, (d, t) in enumerate(remaining):
            if d == deg:
                factor_order.append((d, t))
                remaining.pop(k)
                break
    assert len(factor_order) == len(desc_part), f"Mismatch for {combo_file}"
    # cacheKey: GAP list-of-lists string.  Example:
    # "[ [ 2, 1 ], [ 5, 5 ], [ 10, 32 ] ]"  (this is what ComputeCacheKey
    # returns via String(...).) _CacheKeyToFileName strips spaces, removes
    # outer brackets, replaces "],[" with "]_[", appends ".g".  Using
    # Python's str(list_of_lists) produces a compatible format.
    ascending_tags = sorted(factor_order)
    ascending_pairs = [[d, t] for d, t in ascending_tags]
    cacheKey_str = str(ascending_pairs)
    # Factors in GAP order (DESCENDING by deg):
    factor_list_gap = ", ".join(f"TransitiveGroup({d},{t})" for d, t in factor_order)
    gap_combos.append({
        "partition_desc": desc_part,
        "factor_list_gap": factor_list_gap,
        "cacheKey_str": cacheKey_str,
        "part_dir": "[" + ",".join(str(p) for p in partition) + "]",
    })

# Write the GAP worker script
worker_path = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18\worker_506.g"
log_path = r"C:/Users/jeffr/Downloads/Lifting/parallel_s18/worker_506.log"
heartbeat_path = r"C:/Users/jeffr/Downloads/Lifting/parallel_s18/worker_506_heartbeat.txt"

# Build a GAP list: each combo is [ partition, cacheKey, [factor triples] ]
# to keep the worker simple.
entries = []
for c in gap_combos:
    part = "[" + ",".join(str(x) for x in c["partition_desc"]) + "]"
    entries.append('    [ ' + part + ', "' + c["cacheKey_str"] + '", [ ' +
                   c["factor_list_gap"] + ' ], "' + c["part_dir"] + '" ]')

joined_entries = ",\n".join(entries)
n_partitions_unique = len(set(c[0] for c in combos))

worker_script = f'''
LogTo("{log_path}");

# Disable GeneralAutHomComplements (correctness issue: misses complements
# with phi(K) a supplement of Inn(M_bar) rather than a complement).
# Narrow S_n fast path fix remains in effect (that's independent).
USE_GENERAL_AUT_HOM := false;

Print("Worker 506 (S_n fast path validation, USE_GENERAL_AUT_HOM=false) starting at ",
      StringTime(Runtime()), "\\n");
Print("Processing {len(combos)} bug-signature combos across {n_partitions_unique} partitions\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

_HEARTBEAT_FILE := "{heartbeat_path}";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Each entry: [partition (desc), cacheKey_str, [factor groups in desc order], part_dir_str]
myCombos := [
{joined_entries}
];

workerStart := Runtime();
processed := 0;
for entry in myCombos do
    partition := entry[1];
    cacheKey_str := entry[2];
    factors := entry[3];
    part_dir_str := entry[4];

    comboStart := Runtime();
    Print("\\n[", processed + 1, "/", Length(myCombos), "] partition=", partition,
          " combo=", cacheKey_str, "\\n");
    PrintTo(_HEARTBEAT_FILE, "combo ", processed + 1, "/", Length(myCombos),
            " ", part_dir_str, "/", cacheKey_str, ".g\\n");

    # Build shifted factors + offsets in partition (descending) order.
    offsets := [];
    shifted := [];
    off_ := 0;
    for k in [1..Length(factors)] do
        Add(offsets, off_);
        Add(shifted, ShiftGroup(factors[k], off_));
        off_ := off_ + NrMovedPoints(factors[k]);
    od;
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));

    # Per-combo normalizer
    N := BuildPerComboNormalizer(partition, factors, 18);

    # Clear FPF_SUBDIRECT_CACHE for this combo (force recompute with new code)
    FPF_SUBDIRECT_CACHE := rec();

    # Lifting
    fpf := FindFPFClassesByLifting(P, shifted, offsets, N);

    # Dedup under N using per-block invariant
    CURRENT_BLOCK_RANGES := [];
    off_ := 0;
    for k in [1..Length(partition)] do
        Add(CURRENT_BLOCK_RANGES, [off_ + 1, off_ + partition[k]]);
        off_ := off_ + partition[k];
    od;
    deduped := [];
    byInv := rec();
    for H in fpf do
        AddIfNotConjugate(N, H, deduped, byInv, ComputeSubgroupInvariant);
    od;

    elapsed := Runtime() - comboStart;
    Print("  candidates=", Length(fpf), " deduped=", Length(deduped),
          " time=", elapsed, "ms\\n");

    # Write output file (overwrite prior)
    out_dir := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_s18/", part_dir_str);
    _WriteComboResults(out_dir, cacheKey_str, deduped, Length(fpf), elapsed);

    processed := processed + 1;

    # Periodic flush
    if processed mod 10 = 0 then
        workerTime := (Runtime() - workerStart) / 1000.0;
        Print("\\n[progress] ", processed, "/", Length(myCombos),
              " combos done, ", workerTime, "s elapsed\\n");
    fi;
od;

workerTime := (Runtime() - workerStart) / 1000.0;
Print("\\nWorker 506 complete: ", processed, " combos in ", workerTime, "s\\n");

LogTo();
QUIT;
'''

with open(worker_path, "w") as f:
    f.write(worker_script)

print(f"Wrote worker script to {worker_path}")
print(f"Log will be at {log_path}")
