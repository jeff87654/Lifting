"""Scan parallel_s18 vs parallel_s18_prebugfix_backup for combos where the
current dedup count is less than the prebugfix count. Cross-reference
with combo filename to identify partitions that contain a natural S_n
(n>=5) factor plus another factor isomorphic to S_n.

The S_n fast path bug specifically affects 3+ factor partitions where:
  1. Some factor is natural S_n (n >= 5).
  2. Some OTHER factor is also isomorphic to S_n (different action).

Natural S_n factors for TG(n, t):
  n=5: TG(5, 5) = S_5
  n=6: TG(6, 16) = S_6
  n=7: TG(7, 7) = S_7
  n=8: TG(8, 50) = S_8
  ...

A factor TG(n, t) has a quotient isomorphic to S_m iff TG(n, t) has
the same composition factors as S_m. For the bug to trigger, we need
a factor with |TG(n,t)| = m! and structure similar to S_m.

For the specific failure mode (T_10 = S_6 acting on 10 pts), this is
TG(10, 32). In general, any factor isomorphic to S_m for m >= 5 where
there's ALSO a natural S_m in the partition will trigger the bug.

Strategy:
  1. Enumerate all combo result files.
  2. Parse each for "# deduped: N".
  3. Compare current vs prebugfix per combo.
  4. Collect regressions (current < prebug) with factor info.
  5. Identify subset matching the S_n-bug signature:
     partition has "natural S_n" factor AND another factor that might be
     isomorphic to the same S_n.

For speed: match the known pairs of (natural S_n, non-natural S_n):
  - S_5 (natural on 5 pts): TG(5,5). Known non-natural isomorphic: none
    obvious (S_5 has no non-natural transitive action except via wreath
    embeddings).
  - S_6 (natural on 6 pts): TG(6,16). Non-natural: TG(10,32), TG(15,14),
    TG(20,91) — all S_6 in outer-aut-related actions.
  - S_7 (natural on 7 pts): TG(7,7). Non-natural: TG(15,22) = S_7 on 15
    pairs, TG(21,?)...
  - S_8 (natural on 8 pts): TG(8,50). Non-natural: TG(28,?)...

We don't need to be exhaustive — just identify combos in parallel_s18
where the bug signature clearly matches.
"""
import os, re, glob
from collections import defaultdict

ROOT = r"C:\Users\jeffr\Downloads\Lifting"
CURRENT = os.path.join(ROOT, "parallel_s18")
PREBUG = os.path.join(ROOT, "parallel_s18_prebugfix_backup")

def parse_count(path):
    """Parse '# deduped: N' from combo result file."""
    try:
        with open(path, "r") as f:
            head = f.read(500)
        m = re.search(r"^#\s*deduped:\s*(\d+)", head, flags=re.MULTILINE)
        if m:
            return int(m.group(1))
    except FileNotFoundError:
        return None
    return None

# Known "natural-S_n" IDs (degree, t-number)
NATURAL_SN = {(5, 5), (6, 16), (7, 7), (8, 50), (9, 34), (10, 45)}

# Factors on degree > n that are isomorphic to S_n (known cases).
# These come from S_n having transitive actions on C(n, k) points.
# Populate the obvious ones from group-size and a quick GAP check offline.
# For scanning, we just flag ANY factor where degree * |factor order| fits
# a plausible S_m. Instead of being fancy, iterate and check combo
# factor labels against a targeted pattern.

# The bug signature: combo filename has "_[n,tn]_" where (n, tn) is natural
# S_m for some m, AND another factor "_[d,td]_" where d > m and t_d refers
# to an S_m-like action. Without actually loading groups, flag any combo
# with (6,16) + any factor whose degree > 6 as a suspect, filter later.

# Simpler: exhaustively parse and rank by regression magnitude.

regressions = []
for part_dir in sorted(os.listdir(CURRENT)):
    current_dir = os.path.join(CURRENT, part_dir)
    prebug_dir = os.path.join(PREBUG, part_dir)
    if not os.path.isdir(current_dir) or not os.path.isdir(prebug_dir):
        continue
    for combo_file in os.listdir(current_dir):
        if not combo_file.endswith(".g"):
            continue
        cur = parse_count(os.path.join(current_dir, combo_file))
        pre = parse_count(os.path.join(prebug_dir, combo_file))
        if cur is None or pre is None:
            continue
        if cur < pre:
            regressions.append((part_dir, combo_file, pre, cur, pre - cur))

# Sort by diff magnitude
regressions.sort(key=lambda r: -r[4])

print(f"Total regressions (current < prebug): {len(regressions)}")
print(f"Total lost classes: {sum(r[4] for r in regressions)}")
print()

# Group by partition
by_partition = defaultdict(list)
for r in regressions:
    by_partition[r[0]].append(r)

print("Regressions by partition (sorted by total loss):")
partition_losses = [(p, sum(r[4] for r in regs), len(regs))
                    for p, regs in by_partition.items()]
partition_losses.sort(key=lambda x: -x[1])
for part, loss, count in partition_losses:
    print(f"  {part}: {count} combos, -{loss} classes")
print()

print("Top individual regressions:")
for r in regressions[:25]:
    print(f"  {r[0]}/{r[1]}: {r[2]} -> {r[3]} (-{r[4]})")

# Also detect combos with likely S_n fast path signature:
# combo filename contains at least 2 factor tags with degree >= 5 AND at
# least one is a "natural S_n" tag.
print()
print("Combos with S_n fast path bug signature:")
print("  (partition has a natural S_n factor AND another factor with degree > n)")
sn_natural_tags = {"[5,5]", "[6,16]", "[7,7]", "[8,50]", "[9,34]", "[10,45]"}
bug_signature_regressions = []
for r in regressions:
    tags = re.findall(r"\[\d+,\d+\]", r[1])
    if not tags:
        continue
    natural_sn_idxs = [i for i, t in enumerate(tags) if t in sn_natural_tags]
    if not natural_sn_idxs:
        continue
    # A bug candidate: another factor whose degree > natural S_n's degree
    natural_degs = set()
    for i in natural_sn_idxs:
        deg = int(tags[i].strip("[]").split(",")[0])
        natural_degs.add(deg)
    max_natural_deg = max(natural_degs)
    for i, t in enumerate(tags):
        if i in natural_sn_idxs:
            continue
        other_deg = int(t.strip("[]").split(",")[0])
        if other_deg > max_natural_deg:
            bug_signature_regressions.append(r)
            break
print(f"  Matching combos: {len(bug_signature_regressions)}")
for r in bug_signature_regressions[:20]:
    print(f"  {r[0]}/{r[1]}: {r[2]} -> {r[3]} (-{r[4]})")
if len(bug_signature_regressions) > 20:
    print(f"  ... and {len(bug_signature_regressions) - 20} more")
