###############################################################################
# verify_s18.py - Verify S18 computation results
#
# Walks per-partition directories in parallel_s18/, counts groups from
# per-combo .g files, compares against summary.txt, and sums totals.
#
# Since OEIS A000638(18) is unknown, verification is by:
#   1. Per-combo vs summary.txt consistency
#   2. Gens file vs combo file cross-check (catches truncation)
#   3. Spot checks (e.g., [18] == NrTransitiveGroups(18) = 983)
#   4. Bounds check on FPF growth ratio vs S17
#
# Usage:
#   python verify_s18.py
#
###############################################################################

import os
import sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s18")
GENS_DIR = os.path.join(OUTPUT_DIR, "gens")
N = 18
INHERITED_FROM_PREV = 1466358   # OEIS A000638(17)
FPF_S17 = 780193                # FPF(S17) for growth ratio check

SPOT_CHECKS = {
    "[18]": 983,                # NrTransitiveGroups(18)
}


def join_gap_continuation_lines(filepath):
    """Read a file and join GAP's backslash-continuation lines."""
    with open(filepath, "r") as f:
        raw_lines = f.readlines()
    joined = []
    current = ""
    for raw_line in raw_lines:
        line = raw_line.rstrip("\n").rstrip("\r")
        if line.endswith("\\"):
            current += line[:-1]
        else:
            current += line
            if current.strip():
                joined.append(current)
            current = ""
    if current.strip():
        joined.append(current)
    return joined


def count_groups_in_combo_file(filepath):
    """Count generator lines in a combo .g file."""
    count = 0
    try:
        lines = join_gap_continuation_lines(filepath)
        for line in lines:
            if line.strip().startswith("["):
                count += 1
    except (OSError, IOError):
        pass
    return count


def count_groups_in_gens_file(filepath):
    """Count generator lines in a gens_*.txt file."""
    if not os.path.exists(filepath):
        return -1
    try:
        lines = join_gap_continuation_lines(filepath)
        return sum(1 for line in lines if line.strip().startswith("["))
    except (OSError, IOError):
        return -1


def parse_summary(filepath):
    """Parse summary.txt, returns dict of key->value."""
    result = {}
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if ": " in line:
                    key, val = line.split(": ", 1)
                    result[key.strip()] = val.strip()
    except (OSError, IOError):
        pass
    return result


def verify():
    """Walk partition directories and verify counts."""
    if not os.path.isdir(OUTPUT_DIR):
        print(f"ERROR: Output directory not found: {OUTPUT_DIR}")
        sys.exit(1)

    total_fpf = 0
    partition_results = []
    issues = []

    entries = sorted(os.listdir(OUTPUT_DIR))
    for entry in entries:
        part_dir = os.path.join(OUTPUT_DIR, entry)
        if not os.path.isdir(part_dir):
            continue
        if not entry.startswith("["):
            continue

        # Count groups from combo .g files
        combo_total = 0
        combo_files = 0
        zero_combos = []

        for fname in sorted(os.listdir(part_dir)):
            if not fname.endswith(".g"):
                continue
            fpath = os.path.join(part_dir, fname)
            n = count_groups_in_combo_file(fpath)
            combo_total += n
            combo_files += 1
            if n == 0:
                zero_combos.append(fname)

        # Parse summary.txt
        summary_file = os.path.join(part_dir, "summary.txt")
        summary = parse_summary(summary_file)
        summary_count = None
        elapsed = None
        if "total_classes" in summary:
            try:
                summary_count = int(summary["total_classes"])
            except ValueError:
                pass
        if "elapsed_seconds" in summary:
            elapsed = summary.get("elapsed_seconds")

        # Cross-check: gens file vs combo files
        part_key = entry.strip("[]").replace(",", "_")
        gens_file = os.path.join(GENS_DIR, f"gens_{part_key}.txt")
        gens_count = count_groups_in_gens_file(gens_file)

        # Determine status
        status = "OK"
        if summary_count is not None and combo_total != summary_count:
            status = (f"COMBO/SUMMARY MISMATCH (combos={combo_total}, "
                      f"summary={summary_count})")
            issues.append((entry, status))
        elif summary_count is None and combo_files > 0:
            status = "NO SUMMARY"
        elif combo_files == 0:
            status = "EMPTY"
            issues.append((entry, status))

        # Check gens vs combo
        gens_status = ""
        if gens_count >= 0:
            if gens_count < combo_total:
                gens_status = (f" GENS TRUNCATED ({gens_count} vs "
                               f"{combo_total} combos)")
                issues.append((entry, f"GENS TRUNCATED: {gens_count} vs "
                                      f"{combo_total}"))
            elif gens_count > combo_total:
                gens_status = (f" GENS EXCESS ({gens_count} vs "
                               f"{combo_total} combos)")
        else:
            gens_status = " NO GENS FILE"

        count_to_use = (summary_count if summary_count is not None
                        else combo_total)
        total_fpf += count_to_use

        time_str = f" ({elapsed}s)" if elapsed else ""
        print(f"  {entry:30s}: {count_to_use:>7d} classes, "
              f"{combo_files:>4d} combos  {status}{gens_status}{time_str}")

        if zero_combos:
            for zf in zero_combos[:5]:
                print(f"    WARNING: {zf} has 0 generators")
            if len(zero_combos) > 5:
                print(f"    ... and {len(zero_combos)-5} more "
                      f"zero-generator combos")

        partition_results.append((entry, count_to_use, combo_files))

    # Spot checks
    print(f"\nSpot checks:")
    spot_ok = True
    for part_name, expected in SPOT_CHECKS.items():
        found = None
        for entry, count, _ in partition_results:
            if entry == part_name:
                found = count
                break
        if found is not None:
            ok = found == expected
            status = "OK" if ok else f"FAIL (expected {expected})"
            if not ok:
                spot_ok = False
            print(f"  {part_name:20s}: {found:>7d}  {status}")
        else:
            print(f"  {part_name:20s}: not found")

    # Summary
    total = INHERITED_FROM_PREV + total_fpf
    print(f"\n{'='*60}")
    print(f"Partitions found:  {len(partition_results)}")
    print(f"FPF total:         {total_fpf}")
    print(f"Inherited (S{N-1}):  {INHERITED_FROM_PREV}")
    print(f"Grand total:       {total}")
    print(f"\n*** OEIS A000638({N}) = {total} ***")

    # Growth ratio check
    if total_fpf > 0:
        ratio = total_fpf / FPF_S17
        print(f"\nFPF growth ratio vs S17: {ratio:.2f}x")
        if ratio < 0.5:
            print(f"  WARNING: Ratio suspiciously low (<0.5x)")
        elif ratio > 10:
            print(f"  WARNING: Ratio suspiciously high (>10x)")
        else:
            print(f"  Growth ratio looks reasonable (expected 1-5x)")

    if issues:
        print(f"\nISSUES ({len(issues)}):")
        for part, issue in issues:
            print(f"  {part}: {issue}")

    all_ok = len(issues) == 0 and spot_ok
    if all_ok:
        print(f"\nAll checks PASSED")
    else:
        print(f"\nSome checks FAILED - investigate before submitting")

    return all_ok


if __name__ == "__main__":
    ok = verify()
    sys.exit(0 if ok else 1)
