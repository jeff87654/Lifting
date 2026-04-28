"""Investigate the header/line mismatch in
[6,4,4,2,2]/[2,1]_[2,1]_[4,1]_[4,3]_[6,9].g — header says 4140 but file has
5158 '['-prefixed lines (1018 extra). Check:
  1. Are duplicates present WITHIN the file?
  2. Are the extras present in adjacent combo files?
"""
import os
import re
from collections import Counter

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18\[6,4,4,2,2]"
TARGET = "[2,1]_[2,1]_[4,1]_[4,3]_[6,9].g"


def read_gen_lines(path):
    """Return the list of generator-list lines (each raw line starting with
    '['). Lines can be continued across multiple source lines via trailing
    backslashes, so re-join them first."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return None, None
    # Unwrap GAP's line-continuation backslashes
    text = text.replace("\\\n", "")
    header = None
    m = re.search(r"#\s*deduped:\s*(\d+)", text)
    if m:
        header = int(m.group(1))
    lines = [ln for ln in text.splitlines() if ln.startswith("[")]
    return header, lines


def normalise(line):
    return line.strip()


def main():
    target_path = os.path.join(BASE, TARGET)
    header, lines = read_gen_lines(target_path)
    if lines is None:
        print("could not read target")
        return
    print(f"TARGET: {TARGET}")
    print(f"  header deduped: {header}")
    print(f"  gen-lines:      {len(lines)}")

    # 1. Duplicates within the file?
    ctr = Counter(normalise(ln) for ln in lines)
    dups = {k: v for k, v in ctr.items() if v > 1}
    total_dup_rows = sum(v - 1 for v in dups.values())
    print(f"  unique lines:   {len(ctr)}")
    print(f"  duplicate keys: {len(dups)}")
    print(f"  extra rows from dups: {total_dup_rows}")
    if dups:
        print("  sample repeated line counts:")
        for line, n in list(dups.items())[:5]:
            print(f"    x{n}: {line[:80]}...")

    # 2. Check how many extra lines are exactly the first or last N lines
    #    (would indicate a repeated segment, e.g., mid-combo checkpoint
    #    replay duplicating the head or tail).
    if len(lines) >= 2 * 1018:
        head = set(normalise(l) for l in lines[:1018])
        tail = set(normalise(l) for l in lines[-1018:])
        head_match = sum(1 for l in lines[1018:] if normalise(l) in head)
        tail_match = sum(1 for l in lines[:-1018] if normalise(l) in tail)
        print(f"  lines 1..1018 matched later in file:       {head_match}")
        print(f"  lines (end-1018..end) matched earlier:     {tail_match}")

    # 3. Adjacent combo files — same prefix, +/- neighbours
    prefix = "[2,1]_[2,1]_[4,1]_[4,3]_[6,"
    adj_files = sorted(
        f for f in os.listdir(BASE)
        if f.startswith(prefix) and f.endswith(".g")
    )
    target_set = set(normalise(l) for l in lines)
    print("\nADJACENT FILES with prefix [2,1]_[2,1]_[4,1]_[4,3]_[6,j]:")
    for name in adj_files:
        if name == TARGET:
            continue
        hdr, other_lines = read_gen_lines(os.path.join(BASE, name))
        if other_lines is None:
            continue
        other_set = set(normalise(l) for l in other_lines)
        overlap = len(target_set & other_set)
        marker = f"  overlap={overlap}" if overlap > 0 else ""
        print(f"  {name}: header={hdr} lines={len(other_lines)}{marker}")

    # 4. Check the two neighbouring 4-block variations too
    for nb in ("[2,1]_[2,1]_[4,1]_[4,2]_[6,9].g",
               "[2,1]_[2,1]_[4,1]_[4,4]_[6,9].g"):
        p = os.path.join(BASE, nb)
        if os.path.exists(p):
            hdr, other_lines = read_gen_lines(p)
            if other_lines:
                other_set = set(normalise(l) for l in other_lines)
                overlap = len(target_set & other_set)
                print(f"  {nb}: header={hdr} lines={len(other_lines)} overlap={overlap}")


if __name__ == "__main__":
    main()
