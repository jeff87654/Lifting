"""Create 5 worker scripts (worker_501..505.g) with partitions distributed
for balanced re-run cost. Each partition needs its affected combos re-run;
non-affected combos short-circuit via COMBO FILE EXISTS.

Distribution strategy: greedy bin-packing by current total deduped count in
affected combos per partition (proxy for re-run work).
"""
import os
import re
from collections import defaultdict

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"
MANIFEST = r"C:\Users\jeffr\Downloads\Lifting\affected_combos.txt"

# Per-partition weight = number of affected combos (proxy for re-run time).
# Sum deduped isn't a good proxy because low-deduped combos can still take
# long if they have many candidates. But number of affected combos correlates
# with re-run time.
weights = defaultdict(int)
with open(MANIFEST) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        weights[parts[0]] += 1

# Parse partition name string like "[8,4,2,2,2]" into list of ints
def parse(p):
    return [int(x) for x in p[1:-1].split(",")]

# Sort partitions by weight descending for greedy bin-packing
partitions = sorted(weights.items(), key=lambda kv: -kv[1])

# 5 bins
NWORKERS = 5
bins = [[] for _ in range(NWORKERS)]
totals = [0] * NWORKERS
for p, w in partitions:
    # Assign to least-loaded bin
    idx = totals.index(min(totals))
    bins[idx].append((p, w))
    totals[idx] += w

print(f"Distribution across {NWORKERS} workers:")
for i, (b, total) in enumerate(zip(bins, totals)):
    print(f"  Worker 50{i+1}: {len(b)} partitions, {total} affected combos")

# Emit worker scripts
for i, b in enumerate(bins):
    wid = 501 + i
    log_file = f"C:/Users/jeffr/Downloads/Lifting/parallel_s18/worker_{wid}.log"
    result_file = f"C:/Users/jeffr/Downloads/Lifting/parallel_s18/worker_{wid}_results.txt"
    heartbeat = f"C:/Users/jeffr/Downloads/Lifting/parallel_s18/worker_{wid}_heartbeat.txt"
    ckpt = f"C:/Users/jeffr/Downloads/Lifting/parallel_s18/checkpoints/worker_{wid}"
    gens_dir = "C:/Users/jeffr/Downloads/Lifting/parallel_s18/gens"

    part_list_str = ",\n    ".join(str(parse(p)) for p, _ in b)

    script = f'''
LogTo("{log_file}");
Print("Worker {wid} (bugfix rerun) starting at ", StringTime(Runtime()), "\\n");
Print("Processing {len(b)} partitions with {totals[i]} affected combos\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

CHECKPOINT_DIR := "{ckpt}";
_HEARTBEAT_FILE := "{heartbeat}";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

myPartitions := [
    {part_list_str}
];

totalCount := 0;
workerStart := Runtime();

for part in myPartitions do
    Print("\\n========================================\\n");
    Print("Partition ", part, ":\\n");
    partStart := Runtime();

    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation(
        "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[", _partStr, "]");
    Print("  COMBO_OUTPUT_DIR = ", COMBO_OUTPUT_DIR, "\\n");

    FPF_SUBDIRECT_CACHE := rec();
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

    PrintTo(_HEARTBEAT_FILE,
        "starting partition ", part, "\\n");

    fpf_classes := FindFPFClassesForPartition(18, part);
    partTime := (Runtime() - partStart) / 1000.0;
    Print("  => ", Length(fpf_classes), " classes (", partTime, "s)\\n");
    totalCount := totalCount + Length(fpf_classes);

    if _FORCE_RESTART then
        Print("\\n*** CLEAN RESTART requested after ", partTime, "s ***\\n");
        PrintTo(_HEARTBEAT_FILE,
            "RESTART after partition ", part, " (partial)\\n");
        LogTo();
        QuitGap(0);
    fi;

    # Write heartbeat for completed partition (preserves RESTART semantics)
    PrintTo(_HEARTBEAT_FILE,
        "completed partition ", part, " = ", Length(fpf_classes), " classes\\n");

    # Append to results file
    AppendTo("{result_file}",
        String(part), " ", String(Length(fpf_classes)), "\\n");
od;

workerTime := (Runtime() - workerStart) / 1000.0;
Print("\\nWorker {wid} complete: ", totalCount, " total classes in ",
      workerTime, "s\\n");
AppendTo("{result_file}", "TOTAL ", String(totalCount), "\\n");
AppendTo("{result_file}", "TIME ", String(workerTime), "\\n");

if IsBound(SaveFPFSubdirectCache) then
    SaveFPFSubdirectCache();
fi;

LogTo();
QUIT;
'''
    out_path = f"C:/Users/jeffr/Downloads/Lifting/parallel_s18/worker_{wid}.g"
    with open(out_path.replace("/", os.sep), "w") as f:
        f.write(script)
    print(f"Wrote: {out_path}")

    # Ensure the checkpoint dir exists
    os.makedirs(ckpt, exist_ok=True)

# Ensure gens dir exists
os.makedirs(gens_dir, exist_ok=True)
print("\nAll 5 worker scripts created. Checkpoint dirs prepared.")
