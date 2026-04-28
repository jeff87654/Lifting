"""Find and optionally delete S_18 combo files where # deduped > # candidates.

The PARTIAL RESUME bug (fixed in lifting_method_fast_v2.g) caused some STALE
CHECKPOINT REDO combos to dump the entire in-memory all_fpf as their output,
with a deduped count massively larger than the candidates count.
"""
import os, sys
from pathlib import Path

BASE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s18")
DELETE = "--delete" in sys.argv

bad = []
for d in sorted(os.listdir(BASE)):
    if not d.startswith("["): continue
    dpath = BASE / d
    if not dpath.is_dir(): continue
    for cf in dpath.glob("*.g"):
        try:
            with open(cf, "r", encoding="utf-8", errors="replace") as f:
                # Read header only (first ~400 bytes)
                cands = None
                deduped = None
                for line in f:
                    s = line.rstrip()
                    if s.startswith("# candidates:"):
                        try: cands = int(s.split(":",1)[1].strip())
                        except ValueError: pass
                    elif s.startswith("# deduped:"):
                        try: deduped = int(s.split(":",1)[1].strip())
                        except ValueError: pass
                    elif s.startswith("["):
                        break  # past header
        except OSError:
            continue
        if cands is not None and deduped is not None and deduped > cands:
            bad.append((cf, cands, deduped))

print(f"Found {len(bad)} corrupt combo files (deduped > candidates):")
total_spurious = 0
for cf, c, d in bad[:30]:
    print(f"  {cf.relative_to(BASE)}: cands={c}, deduped={d}")
    total_spurious += (d - c)
if len(bad) > 30:
    print(f"  ... and {len(bad)-30} more")
print(f"\nTotal spurious rows across all corrupt files: {total_spurious}")

if DELETE:
    for cf, _, _ in bad:
        cf.unlink()
    print(f"\nDeleted {len(bad)} corrupt combo files.")
else:
    print("\nRun with --delete to remove them. They'll be recomputed by the workers.")
