"""
Concatenate the 4 origin files into the final s18_origin_combos.g.

Order:
  Part 1: s17_origins.g           (entries 1..889959)
  Part 2: s17_origins_part2.g     (entries 889960..1294129)
  Part 3: s17_origins_part3.g     (entries 1294130..1466358)
  FPF:    s18_origin_combos_fpf.g (entries 1466359..7274651)

Total: 7,274,651 entries.
"""
import os
import sys

CACHE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache"
P1 = os.path.join(CACHE, "s17_origins.g")
P2 = os.path.join(CACHE, "s17_origins_part2.g")
P3 = os.path.join(CACHE, "s17_origins_part3.g")
FPF = os.path.join(CACHE, "s18_origin_combos_fpf.g")
OUT = os.path.join(CACHE, "s18_origin_combos.g")

def stream_entries(path, fout):
    """Stream lines starting with '  [' (entry lines) into fout."""
    n = 0
    with open(path) as fin:
        for line in fin:
            if line.startswith("  ["):
                fout.write(line)
                n += 1
    return n

def main():
    print(f"Building {OUT}")
    fout = open(OUT, "w", encoding="utf-8")
    fout.write("# Origin combos for S18 conjugacy classes of subgroups\n")
    fout.write("# Format per entry: [ partition, [ [degree, transitive_id], ... ] ]\n")
    fout.write("# Order matches s18_subgroups_cycles.g:\n")
    fout.write("#   Entries 1..1466358:        S17 inherited (point 18 fixed)\n")
    fout.write("#   Entries 1466359..7274651:  S18 FPF\n")
    fout.write("# Total: 7274651\n")
    fout.write("return [\n")

    total = 0
    for part in [P1, P2, P3, FPF]:
        print(f"  streaming {os.path.basename(part)}...")
        n = stream_entries(part, fout)
        print(f"    {n} entries")
        total += n

    fout.write("];\n")
    fout.close()

    print(f"\nTotal: {total}  (expected 7274651)")
    if total == 7274651:
        print("MATCH")
    else:
        print(f"MISMATCH delta={total - 7274651}")
    print(f"\nOutput: {OUT}")
    print(f"  size: {os.path.getsize(OUT):,} bytes")

if __name__ == "__main__":
    main()
