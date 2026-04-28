"""Identify the specific combos where the iso-transport bug changed class counts.
Compares per-combo `# deduped:` headers between buggy and corrected dirs."""
import re
from pathlib import Path

PARTS = ["[8,4,4]", "[8,6,2]"]
BASE = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s16_m6m7")

def parse_deduped(path):
    try:
        with open(path) as f:
            for line in f:
                m = re.match(r"#\s*deduped:\s*(\d+)", line)
                if m:
                    return int(m.group(1))
    except Exception:
        return None
    return None

for part in PARTS:
    buggy_dir = BASE / f"{part}_buggy_iso"
    correct_dir = BASE / part
    if not buggy_dir.exists() or not correct_dir.exists():
        print(f"{part}: missing dirs, skip")
        continue
    buggy_files = {f.name: parse_deduped(f) for f in buggy_dir.glob("*.g")}
    correct_files = {f.name: parse_deduped(f) for f in correct_dir.glob("*.g")}
    mismatches = []
    all_combos = set(buggy_files) | set(correct_files)
    for c in sorted(all_combos):
        b = buggy_files.get(c)
        cr = correct_files.get(c)
        if b != cr:
            mismatches.append((c, b, cr))
    print(f"\n== {part} ==")
    print(f"  buggy files: {len(buggy_files)}, correct files: {len(correct_files)}")
    b_sum = sum(v for v in buggy_files.values() if v is not None)
    c_sum = sum(v for v in correct_files.values() if v is not None)
    print(f"  buggy sum: {b_sum}, correct sum: {c_sum}, delta: {c_sum - b_sum:+d}")
    if mismatches:
        print(f"  Mismatched combos ({len(mismatches)}):")
        for c, b, cr in mismatches:
            print(f"    {c}: buggy={b}, correct={cr}, delta={(cr or 0) - (b or 0):+d}")
    else:
        print("  no per-combo differences")
