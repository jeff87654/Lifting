###############################################################################
# verify_s17_v2.py - Verify S17 v2 computation results
#
# Walks per-partition directories in parallel_s17_v2/, counts groups from
# per-combo .g files, compares against summary.txt, and sums to OEIS target.
#
# Usage:
#   python verify_s17_v2.py
#
###############################################################################

import os
import sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s17_v2")
INHERITED_FROM_S16 = 686165
OEIS_S17 = 1466358
EXPECTED_FPF = OEIS_S17 - INHERITED_FROM_S16  # 780,193


def count_groups_in_combo_file(filepath):
    """Count generator lines (lines starting with '[') in a combo .g file."""
    count = 0
    try:
        with open(filepath, "r", errors="replace") as f:
            for line in f:
                if line.strip().startswith("["):
                    count += 1
    except (OSError, IOError):
        pass
    return count


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

    # Find all partition directories (start with '[')
    entries = sorted(os.listdir(OUTPUT_DIR))
    for entry in entries:
        part_dir = os.path.join(OUTPUT_DIR, entry)
        if not os.path.isdir(part_dir):
            continue
        # Skip non-partition dirs
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

        # Parse summary.txt if present
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

        # Compare combo file total vs summary
        status = "OK"
        if summary_count is not None and combo_total != summary_count:
            status = (f"MISMATCH (combos={combo_total}, "
                      f"summary={summary_count})")
            issues.append((entry, status))
        elif summary_count is None and combo_files > 0:
            status = "NO SUMMARY"
        elif combo_files == 0:
            status = "EMPTY"
            issues.append((entry, status))

        count_to_use = (summary_count if summary_count is not None
                        else combo_total)
        total_fpf += count_to_use

        time_str = f" ({elapsed}s)" if elapsed else ""
        print(f"  {entry:30s}: {count_to_use:>6d} classes, "
              f"{combo_files:>4d} combos  {status}{time_str}")

        if zero_combos:
            for zf in zero_combos[:5]:
                print(f"    WARNING: {zf} has 0 generators")
            if len(zero_combos) > 5:
                print(f"    ... and {len(zero_combos)-5} more "
                      f"zero-generator combos")

        partition_results.append((entry, count_to_use, combo_files))

    # Summary
    total = INHERITED_FROM_S16 + total_fpf
    print(f"\n{'='*60}")
    print(f"Partitions found:  {len(partition_results)}")
    print(f"FPF total:         {total_fpf}")
    print(f"Expected FPF:      {EXPECTED_FPF}")
    print(f"Inherited (S16):   {INHERITED_FROM_S16}")
    print(f"Grand total:       {total}")
    print(f"OEIS target:       {OEIS_S17}")

    if total_fpf == EXPECTED_FPF:
        print(f"\nMATCH: FPF total {total_fpf} == expected {EXPECTED_FPF}")
    else:
        diff = total_fpf - EXPECTED_FPF
        print(f"\nDIFFERENCE: {diff:+d} "
              f"(got {total_fpf}, expected {EXPECTED_FPF})")

    if issues:
        print(f"\nISSUES ({len(issues)}):")
        for part, issue in issues:
            print(f"  {part}: {issue}")

    return total_fpf == EXPECTED_FPF


if __name__ == "__main__":
    ok = verify()
    sys.exit(0 if ok else 1)
