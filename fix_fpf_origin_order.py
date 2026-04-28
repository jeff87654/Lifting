"""
Re-sort the factor list in s18_origin_combos_fpf.g (and the corresponding
section of s18_origin_combos.g) so factors are sorted DESCENDING by degree
to match the partition order. Within same-degree, ascending by transitive id.
"""
import os
import re

CACHE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache"
SRC = os.path.join(CACHE, "s18_origin_combos_fpf.g")
DST = os.path.join(CACHE, "s18_origin_combos_fpf.g")  # overwrite
TMP = os.path.join(CACHE, "s18_origin_combos_fpf.g.tmp")

# Each entry line: "  [[partition],[[d,id],[d,id],...]],\n"
# Where partition is sorted descending, but factors may be ascending.
ENTRY_RE = re.compile(r"^  \[(\[\d+(?:,\d+)*\]),\[(.*)\]\],?\s*$")

def parse_factor_list(s):
    # s = "[d1,id1],[d2,id2],..."
    pairs = re.findall(r"\[(\d+),(\d+)\]", s)
    return [[int(d), int(i)] for d, i in pairs]

def factor_str(factors):
    return "[" + ",".join(f"[{d},{i}]" for d, i in factors) + "]"

print(f"Re-sorting factors in {os.path.basename(SRC)}")
n_in = 0
n_changed = 0
with open(SRC) as fin, open(TMP, "w", encoding="utf-8") as fout:
    for line in fin:
        if line.startswith("#") or line.strip() in ("return [", "];", ""):
            fout.write(line)
            continue
        m = ENTRY_RE.match(line)
        if not m:
            fout.write(line)
            continue
        n_in += 1
        partition_str = m.group(1)
        factors = parse_factor_list(m.group(2))
        # Sort: descending degree, ascending id within same degree
        new_factors = sorted(factors, key=lambda p: (-p[0], p[1]))
        if new_factors != factors:
            n_changed += 1
        fout.write(f"  [{partition_str},{factor_str(new_factors)}],\n")

print(f"  Entries processed: {n_in}")
print(f"  Reordered: {n_changed}")

# Replace
os.replace(TMP, DST)
print(f"  Written: {DST}")
