"""
Build s18_subgroups_cycles.g (7,274,651 entries) + companion files:
  - s18_origin_combos_fpf.g  (FPF portion: 5,808,293 entries)

Order:
  1. S17 subgroups (1,466,358) — point 18 fixed, copied verbatim
  2. S18 FPF subgroups (5,808,293) — read from parallel_s18/<part>/<combo>.g

For the origin file (FPF portion):
  Each entry = ( <partition>, [<factor pairs>] )
  e.g. ( [8,5,5], [[8,3],[5,5],[5,5]] )

S17 origins still need to be computed separately via GAP and prepended.
"""
import os
import re
import sys

ROOT = r"C:\Users\jeffr\Downloads\Lifting"
S18_DIR = os.path.join(ROOT, "parallel_s18")
CACHE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache"
S17_CYCLES = os.path.join(CACHE, "s17_subgroups_cycles.g")

# Outputs
OUT_CYCLES = os.path.join(CACHE, "s18_subgroups_cycles.g")
OUT_ORIGINS_FPF = os.path.join(CACHE, "s18_origin_combos_fpf.g")

S17_COUNT = 1466358
S18_FPF_COUNT = 5808293
TOTAL = 7274651

PARTITION_RE = re.compile(r"\[(\d+(?:,\d+)*)\]")


def parse_partition(name):
    """Parse '[8,5,5]' -> [8,5,5]."""
    m = PARTITION_RE.fullmatch(name)
    if not m:
        return None
    return [int(x) for x in m.group(1).split(",")]


def parse_combo_header(text):
    """Parse '# combo: [ [ 3, 2 ], [ 5, 5 ], [ 10, 22 ] ]' -> [[3,2],[5,5],[10,22]]."""
    m = re.search(r"# combo:\s*(\[.*\])", text)
    if not m:
        return None
    s = m.group(1).replace(" ", "")
    # s = "[[3,2],[5,5],[10,22]]"
    pairs = re.findall(r"\[(\d+),(\d+)\]", s)
    return [[int(a), int(b)] for a, b in pairs]


def stream_s17_body(in_fh, out_fh):
    """Copy S17 body (between 'return [' and ');') verbatim. Returns count."""
    in_body = False
    count = 0
    pending = ""  # accumulate continuation lines
    for line in in_fh:
        stripped = line.rstrip("\n")
        if not in_body:
            if stripped == "return [":
                in_body = True
            continue
        # End of body
        if stripped in ("];", "]; ", "];\r"):
            break
        # Detect logical-group lines (after counting continuations)
        if stripped.endswith("\\"):
            # Continuation
            pending += stripped[:-1]  # drop trailing backslash
            continue
        # End of logical line
        full = pending + stripped
        pending = ""
        # Each logical line is one group, ending with comma (except maybe the last)
        out_fh.write(full + "\n")
        if full.strip().startswith("["):
            count += 1
    return count


def stream_s18_fpf(out_cycles, out_origins):
    """Iterate partitions/combo files, write groups + origins. Returns count."""
    partitions = sorted([d for d in os.listdir(S18_DIR)
                         if os.path.isdir(os.path.join(S18_DIR, d))
                         and d.startswith("[")])
    total = 0
    for pname in partitions:
        partition = parse_partition(pname)
        if partition is None:
            continue
        pdir = os.path.join(S18_DIR, pname)
        files = sorted(os.listdir(pdir))
        for fname in files:
            if not fname.endswith(".g"):
                continue
            fpath = os.path.join(pdir, fname)
            with open(fpath) as fh:
                content = fh.read()
            combo = parse_combo_header(content)
            if combo is None:
                print(f"  WARN: no combo header in {fname}", file=sys.stderr)
                continue
            origin_str = "[" + str(partition).replace(" ", "") + "," + str(combo).replace(" ", "") + "]"
            # Now extract group lines (any line starting with `[` outside header)
            in_group = False
            pending = ""
            count_in_file = 0
            for raw_line in content.splitlines():
                stripped = raw_line.rstrip()
                if stripped.startswith("#"):
                    continue
                if not stripped:
                    continue
                if stripped.endswith("\\"):
                    pending += stripped[:-1]
                    continue
                full = pending + stripped
                pending = ""
                if not full.startswith("["):
                    continue
                # Write group line and origin
                out_cycles.write("  " + full + ",\n")
                out_origins.write("  " + origin_str + ",\n")
                count_in_file += 1
                total += 1
    return total


def main():
    print(f"Building {OUT_CYCLES}")
    print(f"Building {OUT_ORIGINS_FPF}")
    print()

    cycles_fh = open(OUT_CYCLES, "w", encoding="utf-8")
    origins_fpf_fh = open(OUT_ORIGINS_FPF, "w", encoding="utf-8")

    # Headers
    cycles_fh.write("# Conjugacy class representatives for S18 (cycle notation)\n")
    cycles_fh.write(f"# Total: {TOTAL} classes\n")
    cycles_fh.write(f"# S17 groups ({S17_COUNT}) extended to 18 points + "
                    f"S18 FPF groups ({S18_FPF_COUNT})\n")
    cycles_fh.write("return [\n")

    origins_fpf_fh.write("# Origin combos for S18 FPF groups (5,808,293 entries)\n")
    origins_fpf_fh.write("# Each entry: [partition, [factor_pairs...]]\n")
    origins_fpf_fh.write("# This is ONLY the FPF portion. The S17 inherited\n")
    origins_fpf_fh.write("# origins must be computed separately and prepended.\n")
    origins_fpf_fh.write("return [\n")

    # Stream S17 body into cycles file
    print("Streaming S17 body...")
    with open(S17_CYCLES) as in_fh:
        s17_count = stream_s17_body(in_fh, cycles_fh)
    print(f"  S17 lines emitted: {s17_count}")

    # Stream S18 FPF
    print("Streaming S18 FPF combo files...")
    s18_count = stream_s18_fpf(cycles_fh, origins_fpf_fh)
    print(f"  S18 FPF lines emitted: {s18_count}")

    cycles_fh.write("];\n")
    origins_fpf_fh.write("];\n")

    cycles_fh.close()
    origins_fpf_fh.close()

    print()
    print(f"Total cycles entries: {s17_count + s18_count}")
    print(f"Expected:             {TOTAL}")
    if s17_count + s18_count == TOTAL:
        print("MATCH ✓")
    else:
        print(f"MISMATCH (delta {s17_count + s18_count - TOTAL})")
    print()
    print(f"S18 cycles file: {OUT_CYCLES}")
    print(f"  size: {os.path.getsize(OUT_CYCLES):,} bytes")
    print(f"S18 origins (FPF): {OUT_ORIGINS_FPF}")
    print(f"  size: {os.path.getsize(OUT_ORIGINS_FPF):,} bytes")


if __name__ == "__main__":
    main()
