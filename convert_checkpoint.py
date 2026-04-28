"""
convert_checkpoint.py - Convert old checkpoint to new format

Reads an old-format .log checkpoint, deduplicates, separates completed-combo
groups from partial groups, and writes a clean new-format checkpoint with
_CKPT_PARTIAL_START.

Also cross-checks against per-combo output files to verify completed-combo
group counts.

Usage:
    python convert_checkpoint.py --dry-run    # Verify without writing
    python convert_checkpoint.py              # Convert and write
"""

import os
import re
import sys
import argparse

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
PARTITION = "8_4_4_2"
PARTITION_DIR_NAME = "[8,4,4,2]"

CKPT_LOG = os.path.join(
    LIFTING_DIR, "parallel_s18", "checkpoints", "worker_22",
    f"ckpt_18_{PARTITION}.log")
COMBO_DIR = os.path.join(
    LIFTING_DIR, "parallel_s18", PARTITION_DIR_NAME)
OUTPUT_LOG = os.path.join(
    LIFTING_DIR, "parallel_s18", "checkpoints_best",
    f"ckpt_18_{PARTITION}.log")


def parse_checkpoint_log(filepath):
    """Parse checkpoint log into structured data.

    Returns:
        completed_combos: list of (combo_key, [gen_strings], total_candidates, added_count)
        partial_entries: list of (partial_key, [gen_strings], total_candidates, added_count)
    """
    print(f"Parsing {filepath}...")

    completed_combos = []
    partial_entries = []

    current_key = None
    current_gens = []
    current_total_candidates = 0
    current_added_count = 0

    # Join backslash continuation lines first
    raw_lines = []
    current = ""
    with open(filepath, "r", errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n").rstrip("\r")
            if line.endswith("\\"):
                current += line[:-1]
            else:
                current += line
                raw_lines.append(current)
                current = ""
    if current:
        raw_lines.append(current)

    for line in raw_lines:
        line = line.rstrip()

        # Combo start marker
        if line.startswith("# combo: "):
            current_key = line[9:]
            current_gens = []
            continue

        # Completed key
        m = re.match(r'Add\(_CKPT_COMPLETED_KEYS, "(.*?)"\);', line)
        if m:
            continue  # key already captured from comment

        # Total candidates
        m = re.match(r'_CKPT_TOTAL_CANDIDATES := (\d+);', line)
        if m:
            current_total_candidates = int(m.group(1))
            continue

        # Added count
        m = re.match(r'_CKPT_ADDED_COUNT := (\d+);', line)
        if m:
            current_added_count = int(m.group(1))
            continue

        # Generator line
        if line.startswith("Add(_CKPT_ALL_FPF_GENS, "):
            gen_str = line[len("Add(_CKPT_ALL_FPF_GENS, "):-2]  # strip ");"
            current_gens.append(gen_str)
            continue

        # Inv key line (new format - preserve if present)
        if line.startswith("Add(_CKPT_ALL_INV_KEYS, "):
            continue  # skip old inv keys, we'll recompute positions

        # Partial start (ignore old injected values)
        if line.startswith("_CKPT_PARTIAL_START"):
            continue

        # End combo marker
        if line.startswith("# end combo"):
            if current_key is not None:
                entry = (current_key, current_gens,
                         current_total_candidates, current_added_count)
                if current_key.startswith("_dedup_partial_"):
                    partial_entries.append(entry)
                else:
                    completed_combos.append(entry)
            current_key = None
            current_gens = []
            continue

    return completed_combos, partial_entries


def count_combo_output_groups(combo_dir):
    """Count total groups across all per-combo .g output files."""
    total = 0
    n_files = 0
    if not os.path.isdir(combo_dir):
        return 0, 0
    for fname in sorted(os.listdir(combo_dir)):
        if not fname.endswith(".g"):
            continue
        n_files += 1
        fpath = os.path.join(combo_dir, fname)
        with open(fpath, "r", errors="replace") as f:
            for line in f:
                if line.strip().startswith("["):
                    total += 1
    return total, n_files


def deduplicate_gens(gen_lists):
    """Deduplicate generator strings, preserving order."""
    seen = set()
    unique = []
    dupes = 0
    for gens in gen_lists:
        key = gens  # generator string is the dedup key
        if key not in seen:
            seen.add(key)
            unique.append(gens)
        else:
            dupes += 1
    return unique, dupes


def write_new_checkpoint(filepath, completed_combos, partial_gens,
                         total_candidates, added_count, partial_start):
    """Write clean new-format checkpoint."""
    print(f"Writing {filepath}...")

    with open(filepath, "w") as f:
        # Write completed combos
        for combo_key, gens, tc, ac in completed_combos:
            f.write(f"# combo: {combo_key}\n")
            f.write(f'Add(_CKPT_COMPLETED_KEYS, "{combo_key}");\n')
            f.write(f"_CKPT_TOTAL_CANDIDATES := {tc};\n")
            f.write(f"_CKPT_ADDED_COUNT := {ac};\n")
            for g in gens:
                # GAP uses backslash continuations for long lines
                stmt = f"Add(_CKPT_ALL_FPF_GENS, {g});\n"
                f.write(stmt)
            f.write(f"# end combo ({ac} total fpf)\n\n")

        # Write partial start marker
        f.write(f"_CKPT_PARTIAL_START := {partial_start};\n")

        # Write partial groups as a single _dedup_partial entry
        if partial_gens:
            f.write(f"# combo: _dedup_partial_all\n")
            f.write(f'Add(_CKPT_COMPLETED_KEYS, "_dedup_partial_all");\n')
            f.write(f"_CKPT_TOTAL_CANDIDATES := {total_candidates};\n")
            f.write(f"_CKPT_ADDED_COUNT := {added_count};\n")
            for g in partial_gens:
                stmt = f"Add(_CKPT_ALL_FPF_GENS, {g});\n"
                f.write(stmt)
            f.write(f"# end combo ({added_count} total fpf)\n\n")

    size_mb = os.path.getsize(filepath) / 1024 / 1024
    print(f"Written: {size_mb:.1f} MB")


def main():
    parser = argparse.ArgumentParser(
        description="Convert checkpoint to new format")
    parser.add_argument("--dry-run", action="store_true",
                       help="Verify without writing")
    args = parser.parse_args()

    # Step 1: Parse checkpoint log
    completed, partials = parse_checkpoint_log(CKPT_LOG)
    print(f"  {len(completed)} completed combos")
    print(f"  {len(partials)} partial entries")

    # Step 2: Count groups per section
    completed_gens_raw = []
    for _, gens, _, _ in completed:
        completed_gens_raw.extend(gens)

    partial_gens_raw = []
    for _, gens, _, _ in partials:
        partial_gens_raw.extend(gens)

    print(f"\n  Raw counts:")
    print(f"    Completed combo groups: {len(completed_gens_raw)}")
    print(f"    Partial groups: {len(partial_gens_raw)}")
    print(f"    Total raw: {len(completed_gens_raw) + len(partial_gens_raw)}")

    # Step 3: Deduplicate each section independently
    completed_unique, completed_dupes = deduplicate_gens(completed_gens_raw)
    partial_unique, partial_dupes = deduplicate_gens(partial_gens_raw)

    print(f"\n  After dedup:")
    print(f"    Completed: {len(completed_unique)} "
          f"({completed_dupes} dupes removed)")
    print(f"    Partial: {len(partial_unique)} "
          f"({partial_dupes} dupes removed)")

    # Step 4: Remove partial groups that are also in completed set
    completed_set = set(completed_unique)
    partial_only = [g for g in partial_unique if g not in completed_set]
    overlap = len(partial_unique) - len(partial_only)

    print(f"    Partial-only (not in completed): {len(partial_only)} "
          f"({overlap} overlap removed)")
    print(f"    Final total: {len(completed_unique) + len(partial_only)}")

    # Step 5: Cross-check with per-combo output files
    combo_count, combo_files = count_combo_output_groups(COMBO_DIR)
    print(f"\n  Cross-check: {combo_files} combo output files, "
          f"{combo_count} groups")
    if combo_count == len(completed_unique):
        print(f"  MATCH: combo output == completed checkpoint groups")
    else:
        print(f"  MISMATCH: combo output {combo_count} != "
              f"completed {len(completed_unique)}")
        print(f"  Difference: {combo_count - len(completed_unique)}")

    # Step 6: Get final metadata
    if partials:
        last_tc = partials[-1][2]
        last_ac = partials[-1][3]
    elif completed:
        last_tc = completed[-1][2]
        last_ac = completed[-1][3]
    else:
        last_tc = 0
        last_ac = 0

    partial_start = len(completed_unique) + 1
    final_total = len(completed_unique) + len(partial_only)

    print(f"\n  New checkpoint format:")
    print(f"    {len(completed)} completed combos")
    print(f"    {len(completed_unique)} unique completed groups")
    print(f"    {len(partial_only)} unique partial groups")
    print(f"    _CKPT_PARTIAL_START = {partial_start}")
    print(f"    Total unique groups: {final_total}")
    print(f"    _CKPT_TOTAL_CANDIDATES = {last_tc}")
    print(f"    _CKPT_ADDED_COUNT = {last_ac}")

    if args.dry_run:
        print("\n[DRY RUN] Would write to:", OUTPUT_LOG)
        return

    # Step 7: Rebuild completed combos with deduplicated gens
    # Each combo keeps only its unique gens (removing cross-combo dupes)
    seen_global = set()
    clean_completed = []
    for combo_key, gens, tc, ac in completed:
        clean_gens = []
        for g in gens:
            if g not in seen_global:
                seen_global.add(g)
                clean_gens.append(g)
        clean_completed.append((combo_key, clean_gens, tc, ac))

    # Step 8: Write
    write_new_checkpoint(OUTPUT_LOG, clean_completed, partial_only,
                         last_tc, last_ac, partial_start)

    print(f"\nDone! New checkpoint: {OUTPUT_LOG}")
    print(f"Verify with: grep -c 'Add(_CKPT_ALL_FPF_GENS' {OUTPUT_LOG}")


if __name__ == "__main__":
    main()
