"""Count groups found across all S_18 partition combo files.

Each combo file has a '# deduped: N' header and N subsequent lines starting
with '[' (one per group's generator list). Sum both and cross-check.
"""
import os
import re

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"


def count_combo_file(path):
    """Return (header_count, actual_line_count). -1 header if missing."""
    header = -1
    actual = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if header < 0 and line.startswith("# deduped:"):
                    m = re.search(r"# deduped:\s*(\d+)", line)
                    if m:
                        header = int(m.group(1))
                elif line.startswith("["):
                    actual += 1
    except OSError:
        pass
    return header, actual


def main():
    per_partition = []
    grand_header = 0
    grand_actual = 0
    missing_header = 0
    mismatch = 0

    for name in sorted(os.listdir(BASE)):
        full = os.path.join(BASE, name)
        if not os.path.isdir(full):
            continue
        if "bogus" in name:
            continue
        if not (name.startswith("[") and name.endswith("]")):
            continue

        part_header = 0
        part_actual = 0
        nfiles = 0
        for f in os.listdir(full):
            if not f.endswith(".g"):
                continue
            nfiles += 1
            h, a = count_combo_file(os.path.join(full, f))
            if h < 0:
                missing_header += 1
                part_header += a  # fall back to actual
            else:
                part_header += h
                if h != a:
                    mismatch += 1
            part_actual += a

        per_partition.append((name, nfiles, part_header, part_actual))
        grand_header += part_header
        grand_actual += part_actual

    # Print per-partition (compact)
    print(f"{'partition':<28} {'files':>7} {'header_sum':>12} {'line_sum':>12}")
    print("-" * 64)
    for name, nfiles, h, a in per_partition:
        marker = "" if h == a else "  <-- mismatch"
        print(f"{name:<28} {nfiles:>7} {h:>12,} {a:>12,}{marker}")

    print()
    print(f"Total partitions scanned: {len(per_partition)}")
    print(f"Combo files missing header: {missing_header}")
    print(f"Combo files header/line mismatch: {mismatch}")
    print()
    print(f"GRAND TOTAL (headers):  {grand_header:,}")
    print(f"GRAND TOTAL (lines):    {grand_actual:,}")


if __name__ == "__main__":
    main()
