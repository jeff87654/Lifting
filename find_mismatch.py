import os
import re

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"

for d in sorted(os.listdir(BASE)):
    full = os.path.join(BASE, d)
    if not os.path.isdir(full) or "bogus" in d or not d.startswith("["):
        continue
    for f in os.listdir(full):
        if not f.endswith(".g"):
            continue
        path = os.path.join(full, f)
        header = -1
        actual = 0
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if header < 0 and line.startswith("# deduped:"):
                    m = re.search(r"# deduped:\s*(\d+)", line)
                    if m:
                        header = int(m.group(1))
                elif line.startswith("["):
                    actual += 1
        if header >= 0 and header != actual:
            print(f"{d}/{f}: header={header} actual={actual} diff={actual-header}")
