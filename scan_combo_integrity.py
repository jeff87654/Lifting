"""Scan all combo .g files in parallel_sn_v2 and report any mismatch
between '# deduped: N' header and actual generator-line count."""
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting") / "parallel_sn_v2"

mismatches = []
ok = 0
total = 0
for f in ROOT.rglob("*.g"):
    if f.name.startswith("_"):
        continue
    total += 1
    try:
        text = f.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        mismatches.append((f, "read-error", str(e)))
        continue
    # Strip GAP line continuations.
    joined = re.sub(r"\\\r?\n", "", text)
    m = re.search(r"^# deduped:\s*(\d+)\s*$", joined, re.MULTILINE)
    if not m:
        mismatches.append((f, "no-deduped-header", ""))
        continue
    expected = int(m.group(1))
    actual = sum(1 for ln in joined.splitlines() if ln.startswith("["))
    if actual != expected:
        delta = actual - expected
        mismatches.append((f, f"deduped={expected} gens={actual} delta={delta:+d}", ""))
    else:
        ok += 1

print(f"Total scanned: {total}")
print(f"OK (deduped == gens): {ok}")
print(f"Mismatches: {len(mismatches)}")
print()
# Print all mismatches grouped by partition
by_part = {}
for f, msg, _ in mismatches:
    part = f.parent.name
    by_part.setdefault(part, []).append((f.name, msg))
for part, items in sorted(by_part.items()):
    print(f"=== {part} ({len(items)}) ===")
    for name, msg in items[:15]:
        print(f"  {name} -> {msg}")
    if len(items) > 15:
        print(f"  ... +{len(items)-15} more")
