"""Check the TG(8,*) family — do 12, 25, 32, 36, 37, 48, 49 really produce
identical counts?  Look at a single partition's [8,Y] variation.
"""
import os
import re

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"


def dedup(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"#\s*deduped:\s*(\d+)", line)
                if m:
                    return int(m.group(1))
    except OSError:
        return None
    return None


# For [8,4,4,2] with fixed [4,3]_[4,3], show all [8,Y]
folder = os.path.join(BASE, "[8,4,4,2]")
for fixed in ["[4,3]_[4,3]", "[4,1]_[4,3]", "[4,3]_[4,4]", "[4,5]_[4,5]", "[4,4]_[4,4]"]:
    print(f"\n=== {folder} / [2,1]_{fixed}_[8,Y] ===")
    results = []
    for Y in range(1, 51):
        f = f"[2,1]_{fixed}_[8,{Y}].g"
        path = os.path.join(folder, f)
        if os.path.exists(path):
            n = dedup(path)
            results.append((Y, n))
    for Y, n in results:
        marker = "  <-- suspicious?" if n is not None and n < 100 else ""
        print(f"  [8,{Y}]: {n}{marker}")

# And [8,4,2,2,2] with [4,3]
print()
folder2 = os.path.join(BASE, "[8,4,2,2,2]")
print(f"=== {folder2} / [2,1]_[2,1]_[2,1]_[4,3]_[8,Y] ===")
for Y in range(1, 51):
    f = f"[2,1]_[2,1]_[2,1]_[4,3]_[8,{Y}].g"
    path = os.path.join(folder2, f)
    if os.path.exists(path):
        n = dedup(path)
        print(f"  [8,{Y}]: {n}")
