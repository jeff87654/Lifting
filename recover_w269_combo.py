#!/usr/bin/env python3
"""
Recovery script for [4,4,4,4,2] partition's C_2 x D_4^4 combo file.

Context:
- W269's first run found 113,381 N-orbit reps via partial dedup on
  [2,1],[4,3],[4,3],[4,3],[4,3] (C_2 x D_4^4), then crashed.
- W269's current run loaded these 113K from checkpoint, resumed dedup,
  and is still running. When the combo completes, the CURRENT code
  writes only the NEW groups (found in current run) to the combo file,
  losing the 113K.
- This script extracts the 113K groups from the backup checkpoint .log
  and appends them to the combo file, restoring the full count.

Usage:
  python recover_w269_combo.py [--dry-run]

Run AFTER W269 completes the C_2 x D_4^4 combo (when the file
parallel_s18/[4,4,4,4,2]/[2,1]_[4,3]_[4,3]_[4,3]_[4,3].g exists).
"""
import os
import re
import sys
from datetime import datetime

BACKUP_LOG = "parallel_s18/checkpoints/worker_269/ckpt_18_4_4_4_4_2.log.backup_113k_20260414_233533"
COMBO_FILE = "parallel_s18/[4,4,4,4,2]/[2,1]_[4,3]_[4,3]_[4,3]_[4,3].g"


def extract_first_session_groups(log_path, count):
    """
    Extract the first N group generator lists from the checkpoint .log.
    Returns a list of strings, each a [(perm1),(perm2),...] generator list.

    The .log has lines like:
        Add(_CKPT_ALL_FPF_GENS, [(1,2,3,4),(1,3),...]);
    possibly with backslash line continuations:
        Add(_CKPT_ALL_FPF_GENS, [(1,2,3,4),(1,3),(5,6,7,8),(5,7),(9,10,11,12),(9,11),(\\
        13,15)(14,16),(14,16),(13,14,15,16)(17,18)]);
    """
    with open(log_path, 'r') as f:
        content = f.read()

    # Remove backslash-newline continuations so each Add() is on one logical line
    content = re.sub(r'\\\n', '', content)

    # Find all Add(_CKPT_ALL_FPF_GENS, [...]); entries
    # Match the bracket content using balanced parentheses logic
    groups = []
    pos = 0
    marker = "Add(_CKPT_ALL_FPF_GENS, "
    while True:
        idx = content.find(marker, pos)
        if idx == -1:
            break
        # Skip past the marker
        start = idx + len(marker)
        # Expect an opening '[' at start
        if content[start] != '[':
            pos = start
            continue
        # Find matching closing bracket (track nesting)
        depth = 0
        end = start
        while end < len(content):
            c = content[end]
            if c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    break
            end += 1
        if depth != 0:
            print(f"ERROR: unbalanced brackets at pos {start}")
            break
        gen_list = content[start:end+1]
        groups.append(gen_list)
        pos = end + 1
        if len(groups) >= count:
            break
    return groups


def count_groups_in_combo_file(path):
    """Count lines starting with '[' in the combo file."""
    count = 0
    with open(path, 'r') as f:
        for line in f:
            if line.startswith('['):
                count += 1
    return count


def main():
    dry_run = '--dry-run' in sys.argv

    print(f"Recovery script for W269's C_2 x D_4^4 combo")
    print(f"Backup .log: {BACKUP_LOG}")
    print(f"Combo file: {COMBO_FILE}")
    print()

    if not os.path.exists(BACKUP_LOG):
        print(f"ERROR: Backup .log not found")
        return 1

    if not os.path.exists(COMBO_FILE):
        print(f"NOTE: Combo file doesn't exist yet. Run this script AFTER W269")
        print(f"      completes the combo. For now, validating extraction logic...")
        # Continue for validation
        combo_exists = False
    else:
        combo_exists = True
        existing_count = count_groups_in_combo_file(COMBO_FILE)
        print(f"Combo file currently has {existing_count} groups")

    # Extract first 113381 groups from backup (these are session 1's groups)
    print(f"Extracting first 113,381 groups from backup .log...")
    target_count = 113381
    groups = extract_first_session_groups(BACKUP_LOG, target_count)
    print(f"Extracted {len(groups)} group generator lists")

    if len(groups) < target_count:
        print(f"WARNING: Only found {len(groups)}, expected {target_count}")

    if not combo_exists:
        # Validate a few extracted groups
        print()
        print("Validation (first 3 extracted groups):")
        for i, g in enumerate(groups[:3]):
            truncated = g if len(g) < 200 else g[:200] + "..."
            print(f"  [{i}] {truncated}")
        print()
        print("Re-run this script after W269 completes the combo.")
        return 0

    if dry_run:
        print(f"\nDRY RUN: would append {len(groups)} groups to {COMBO_FILE}")
        print(f"  Current count: {existing_count}")
        print(f"  Final count would be: {existing_count + len(groups)}")
        return 0

    # Back up the combo file before modifying
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    combo_backup = f"{COMBO_FILE}.backup_{ts}"
    with open(COMBO_FILE, 'r') as fi, open(combo_backup, 'w') as fo:
        fo.write(fi.read())
    print(f"Backed up combo file: {combo_backup}")

    # Read existing combo file
    with open(COMBO_FILE, 'r') as f:
        lines = f.readlines()

    # Find and update the `# deduped: N` header line
    new_count = existing_count + len(groups)
    for i, line in enumerate(lines):
        if line.startswith('# deduped:'):
            old_line = line.strip()
            lines[i] = f"# deduped: {new_count}\n"
            print(f"Updated header: '{old_line}' -> '# deduped: {new_count}'")
            break

    # Append the new groups
    with open(COMBO_FILE, 'w') as f:
        f.writelines(lines)
        for g in groups:
            f.write(g + '\n')

    # Verify
    final_count = count_groups_in_combo_file(COMBO_FILE)
    print(f"\nFinal group count in combo file: {final_count}")
    if final_count == new_count:
        print(f"SUCCESS: combo file updated. Run summary.txt regen if needed.")
    else:
        print(f"WARNING: expected {new_count}, got {final_count}. Check file.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
