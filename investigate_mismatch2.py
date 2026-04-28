"""Deeper analysis of the duplicate pattern in the combo file."""
import os
import re
from collections import OrderedDict

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18\[6,4,4,2,2]"
TARGET = os.path.join(BASE, "[2,1]_[2,1]_[4,1]_[4,3]_[6,9].g")


def read_gen_lines(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    text = text.replace("\\\n", "")
    header = None
    m = re.search(r"#\s*deduped:\s*(\d+)", text)
    if m:
        header = int(m.group(1))
    lines = [ln for ln in text.splitlines() if ln.startswith("[")]
    return header, lines


header, lines = read_gen_lines(TARGET)
print(f"header: {header}, total lines: {len(lines)}")

# Find first duplicate and check layout
seen_at = OrderedDict()
dup_pairs = []
for i, ln in enumerate(lines):
    key = ln.strip()
    if key in seen_at:
        dup_pairs.append((seen_at[key], i))
    else:
        seen_at[key] = i

print(f"duplicate pairs: {len(dup_pairs)}")
if dup_pairs:
    first_orig, first_dup = dup_pairs[0]
    last_orig, last_dup = dup_pairs[-1]
    print(f"first duplicate: original at line {first_orig}, copy at line {first_dup}")
    print(f"last duplicate:  original at line {last_orig}, copy at line {last_dup}")
    # Are all original indices < all duplicate indices?
    min_dup = min(d for _, d in dup_pairs)
    max_orig = max(o for o, _ in dup_pairs)
    print(f"min duplicate index: {min_dup}")
    print(f"max original index:  {max_orig}")
    if min_dup >= max_orig + 1:
        print("=> all duplicates are in a contiguous tail block appended after originals")
    # Check if the tail 800 lines exactly match a contiguous earlier block
    # (i.e., file = [prefix][middle][prefix repeated])
    tail = [ln.strip() for ln in lines[min_dup:]]
    # See if tail is a prefix of earlier lines starting at some offset
    for start in range(0, min(500, len(lines) - len(tail))):
        if [ln.strip() for ln in lines[start:start + len(tail)]] == tail:
            print(f"tail (lines {min_dup}..{len(lines)-1}) == earlier block starting at line {start}")
            break
