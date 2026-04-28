"""
Count conjugacy classes by orbit type in s17_subgroups.g.
Orbit type = sorted partition of 17 given by orbit sizes.
"""
import ast
from collections import defaultdict

S17_FILE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache\s17_subgroups.g"
OUT_FILE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache\s17_orbit_type_counts.txt"

def orbit_type(gens, n=17):
    """Compute orbit type (sorted descending) from generator image lists."""
    # Union-find
    parent = list(range(n + 1))  # 1-indexed

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    for g in gens:
        for i in range(len(g)):
            union(i + 1, g[i])

    # Count orbit sizes
    sizes = defaultdict(int)
    for i in range(1, n + 1):
        sizes[find(i)] += 1
    partition = sorted(sizes.values(), reverse=True)
    return tuple(partition)


def main():
    counts = defaultdict(int)
    total = 0

    with open(S17_FILE, "r") as f:
        buf = ""
        in_data = False
        for line in f:
            stripped = line.strip()
            if not in_data:
                if stripped.startswith("return ["):
                    in_data = True
                continue
            if stripped == "];":
                break
            buf += line.rstrip("\n").rstrip("\r")
            if buf.strip():
                opens = buf.count("[")
                closes = buf.count("]")
                if opens > 0 and opens == closes:
                    entry_str = buf.strip()
                    if entry_str.endswith(","):
                        entry_str = entry_str[:-1]
                    try:
                        gens = ast.literal_eval(entry_str)
                    except:
                        print(f"  WARN: parse error at {total}: {entry_str[:80]}...")
                        buf = ""
                        continue
                    ot = orbit_type(gens)
                    counts[ot] += 1
                    total += 1
                    if total % 200000 == 0:
                        print(f"  {total} groups processed...")
                    buf = ""

    # Sort by partition (descending parts, so [17] first, then [16,1], etc.)
    sorted_types = sorted(counts.items(), key=lambda x: (-x[0][0], x[0]))

    with open(OUT_FILE, "w") as out:
        out.write(f"# S17 conjugacy class counts by orbit type\n")
        out.write(f"# Total: {total} classes\n")
        out.write(f"# {len(counts)} distinct orbit types\n\n")
        out.write(f"{'Orbit type':<40s} {'Count':>8s}\n")
        out.write(f"{'-'*40} {'-'*8}\n")
        for ot, c in sorted_types:
            label = "[" + ",".join(str(x) for x in ot) + "]"
            out.write(f"{label:<40s} {c:>8d}\n")
        out.write(f"{'-'*40} {'-'*8}\n")
        out.write(f"{'TOTAL':<40s} {total:>8d}\n")

    print(f"\nDone! {total} groups, {len(counts)} orbit types")
    print(f"Written to {OUT_FILE}")

    # Print summary
    for ot, c in sorted_types:
        label = "[" + ",".join(str(x) for x in ot) + "]"
        print(f"  {label:<40s} {c:>8d}")
    print(f"  {'TOTAL':<40s} {total:>8d}")


if __name__ == "__main__":
    main()
