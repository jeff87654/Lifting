"""For each S_18 partition, count groups in checkpoint .log files vs combo files.

Checkpoint .log format (from _AppendCheckpointDelta):
  # combo: <cacheKey>
  Add(_CKPT_COMPLETED_KEYS, "<cacheKey>");
  _CKPT_TOTAL_CANDIDATES := N;
  _CKPT_ADDED_COUNT := N;
  Add(_CKPT_ALL_FPF_GENS, [...]);   <-- one per group
  Add(_CKPT_ALL_FPF_GENS, [...]);
  ...
  # end combo (N total fpf)

So `grep -c "Add(_CKPT_ALL_FPF_GENS"` counts the groups recorded.
Multiple checkpoint .log files may exist per partition (across workers);
we want the LARGEST unique-combos set, not the sum.
"""
import os, re
from pathlib import Path
from collections import defaultdict

BASE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
CKPT = BASE / "checkpoints"


def parse_checkpoint_log(path):
    """Return dict: cacheKey -> number of groups added from each delta block.

    Each '# combo: <key>' ... '# end combo' block adds some # of groups.
    Multiple blocks per combo exist (partial-dedup intermediate checkpoints
    within a single run). We keep a *list* of per-block counts per combo;
    the caller decides which to use.
    """
    combos = defaultdict(list)
    current_key = None
    current_count = 0
    try:
        with open(path, errors="replace") as f:
            for line in f:
                if line.startswith("# combo:"):
                    current_key = line[8:].strip()
                    current_count = 0
                elif current_key and line.startswith("Add(_CKPT_ALL_FPF_GENS,"):
                    current_count += 1
                elif line.startswith("# end combo"):
                    if current_key is not None:
                        combos[current_key].append(current_count)
                    current_key = None
                    current_count = 0
    except OSError:
        pass
    return combos


def sum_combo_files(pdir):
    total = 0
    for cf in pdir.glob("*.g"):
        try:
            with open(cf, errors="replace") as f:
                for line in f:
                    if line.startswith("# deduped:"):
                        total += int(line.split(":",1)[1].strip())
                        break
                    if line.startswith("["):
                        break
        except OSError:
            pass
    return total


def collect_ckpt_per_partition():
    """Merge checkpoint logs per partition.

    For each combo:
      - Per log: sum all delta blocks (partial-dedup checkpoints are cumulative)
      - Across logs: take max (different workers may have processed the combo
        at different points)
    """
    result = defaultdict(lambda: defaultdict(int))  # part -> cacheKey -> max_count
    if not CKPT.is_dir():
        return result
    for wdir in CKPT.iterdir():
        if not wdir.is_dir() or not wdir.name.startswith("worker_"):
            continue
        for logf in wdir.glob("ckpt_18_*.log"):
            m = re.match(r"ckpt_18_(.+)\.log$", logf.name)
            if not m: continue
            part_str = "[" + m.group(1).replace("_", ",") + "]"
            combos = parse_checkpoint_log(logf)
            for ck, block_counts in combos.items():
                # Within one log, sum all partial-dedup blocks for this combo
                total_in_log = sum(block_counts)
                if total_in_log > result[part_str][ck]:
                    result[part_str][ck] = total_in_log
    return result


ckpt_by_part = collect_ckpt_per_partition()

print(f"{'partition':22} {'combo_sum':>10} {'ckpt_sum':>10} {'diff':>8}  notes")
print("-" * 70)

discrepancies = []
for d in sorted(os.listdir(BASE)):
    if not d.startswith("["): continue
    pdir = BASE / d
    if not pdir.is_dir(): continue
    A = sum_combo_files(pdir)
    ckpt_combos = ckpt_by_part.get(d, {})
    ckpt_sum = sum(ckpt_combos.values())
    diff = A - ckpt_sum
    note = ""
    if ckpt_sum > A:
        note = f"ckpt has {ckpt_sum - A} groups not in combo files"
        discrepancies.append((d, A, ckpt_sum, ckpt_sum - A))
    print(f"{d:22} {A:>10} {ckpt_sum:>10} {diff:>8}  {note}")

print()
if discrepancies:
    total_hidden = sum(x[3] for x in discrepancies)
    print(f"STALE: {len(discrepancies)} partitions have ckpt groups not in combo files")
    print(f"Total groups in ckpt but missing from combo files: {total_hidden:,}")
