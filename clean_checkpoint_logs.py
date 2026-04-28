"""Clean checkpoint .log files by removing entries that overlap with the .g base.

The .log files contain delta entries (Add() calls). Some of these may
correspond to combos already present in the .g file. This script filters
the .log to keep only entries whose combo key is NOT in the .g file.
"""
import re
import os
import sys

def get_completed_keys_from_g(g_file):
    """Extract the set of completed combo keys from a .g checkpoint file."""
    keys = set()
    with open(g_file, 'r') as f:
        content = f.read()
    # Keys are quoted strings in _CKPT_COMPLETED_KEYS list
    for m in re.finditer(r'"(\[.*?\])"', content[:200000]):  # keys are near the top
        keys.add(m.group(1))
    return keys

def clean_log_file(g_file, log_file):
    """Remove .log entries whose combo key is already in the .g file."""
    if not os.path.exists(g_file):
        print(f"  No .g file found, skipping")
        return
    if not os.path.exists(log_file):
        print(f"  No .log file found, skipping")
        return

    base_keys = get_completed_keys_from_g(g_file)
    print(f"  .g has {len(base_keys)} combo keys")

    with open(log_file, 'r') as f:
        content = f.read()

    # Split into combo blocks. Each block starts with "# combo: ..."
    blocks = re.split(r'(?=# combo: )', content)
    blocks = [b for b in blocks if b.strip()]  # remove empty

    kept = []
    removed = 0
    for block in blocks:
        # Extract the combo key from the Add(_CKPT_COMPLETED_KEYS, "...") line
        m = re.search(r'Add\(_CKPT_COMPLETED_KEYS, "(.+?)"\)', block)
        if m:
            key = m.group(1)
            if key in base_keys:
                removed += 1
                continue
        kept.append(block)

    print(f"  .log had {len(blocks)} entries: keeping {len(kept)}, removing {removed} overlapping")

    if removed > 0:
        # Backup original
        backup = log_file + '.bak'
        os.rename(log_file, backup)
        print(f"  Backed up original to {backup}")

        if kept:
            with open(log_file, 'w') as f:
                f.write(''.join(kept))
            print(f"  Wrote cleaned .log with {len(kept)} entries")
        else:
            print(f"  All entries were duplicates, deleting .log")
            # Don't create empty file - let resume code skip it
    else:
        print(f"  No overlapping entries, .log is clean")


workers = {
    100: "ckpt_16_8_8",
    102: "ckpt_16_4_4_4_4",
}

base_dir = r"C:\Users\jeffr\Downloads\Lifting\parallel_s16\checkpoints"

for wid, prefix in workers.items():
    ckpt_dir = os.path.join(base_dir, f"worker_{wid}")
    g_file = os.path.join(ckpt_dir, f"{prefix}.g")
    log_file = os.path.join(ckpt_dir, f"{prefix}.log")
    print(f"\n=== Worker {wid} ===")
    clean_log_file(g_file, log_file)

print("\nDone. Workers can now be relaunched.")
