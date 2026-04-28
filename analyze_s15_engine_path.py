"""Classify each S_15 combo by engine path: clean Holt vs legacy.
Infers from log patterns in per-worker logs of parallel_s15_m6m7_v2/.

Taxonomy:
  legacy_fast   - dispatcher routed to legacy via _HoltIsLegacyFastPathCase
                  (Goursat / S_n / SmallGroup / D_4^3 fast path fired)
  legacy_chief  - clean pipeline errored, CALL_WITH_CATCH routed to legacy
                  chief-series lift ("Layer N/M: |M/N|=..." pattern)
  clean         - clean pipeline succeeded (no legacy signature in combo block)
"""
import re
from pathlib import Path

V2 = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s15_m6m7_v2")

LEGACY_FAST_PATHS = re.compile(
    r"^  (Goursat fast path:|S_n fast path:|SmallGroup fast path:|D_4\^3 fast path:)",
    re.MULTILINE,
)
LEGACY_LAYER = re.compile(r"^    >> Layer \d+/\d+:", re.MULTILINE)

counts = {"legacy_fast": 0, "legacy_chief": 0, "clean": 0}
per_combo_classes = {"legacy_fast": 0, "legacy_chief": 0, "clean": 0}

for log in sorted(V2.glob("worker_*.log")):
    if "- Copy" in log.name:
        continue
    try:
        text = open(log, encoding="utf-8", errors="replace").read()
    except Exception:
        continue
    combos_in_log = text.split(">> combo [[")
    for block in combos_in_log[1:]:
        has_legacy_fast = bool(LEGACY_FAST_PATHS.search(block))
        has_legacy_chief = bool(LEGACY_LAYER.search(block))
        new_m = re.search(r"combo: \d+ candidates -> (\d+) new \(\d+ total\)", block)
        new_classes = int(new_m.group(1)) if new_m else 0

        if has_legacy_fast:
            key = "legacy_fast"
        elif has_legacy_chief:
            key = "legacy_chief"
        else:
            key = "clean"
        counts[key] += 1
        per_combo_classes[key] += new_classes

print(f"{'path':<16} {'combos':>10} {'new classes':>14}")
print("-" * 44)
for k in ["clean", "legacy_fast", "legacy_chief"]:
    print(f"{k:<16} {counts[k]:>10} {per_combo_classes[k]:>14}")
print("-" * 44)
total_c = sum(counts.values())
total_n = sum(per_combo_classes.values())
print(f"{'TOTAL':<16} {total_c:>10} {total_n:>14}")

print()
print("Classes-weighted share:")
for k in ["clean", "legacy_fast", "legacy_chief"]:
    share = 100.0 * per_combo_classes[k] / total_n if total_n else 0
    print(f"  {k:<16} {share:>5.1f}%")

print()
print("Combo-weighted share:")
for k in ["clean", "legacy_fast", "legacy_chief"]:
    share = 100.0 * counts[k] / total_c if total_c else 0
    print(f"  {k:<16} {share:>5.1f}%")
