"""Deduplicate checkpoint .g files by removing duplicate combo keys and generator sets.

Handles the full checkpoint format:
- _CKPT_COMPLETED_KEYS (list of string keys)
- _CKPT_ALL_FPF_GENS (list of generator lists in GAP cycle notation)
- _CKPT_TOTAL_CANDIDATES, _CKPT_ADDED_COUNT (integers)
- _CKPT_INV_KEYS (list of invariant key strings, optional)

Also applies .log deltas before deduping.
"""
import os
import re
import shutil

CKPT_BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17\checkpoints"

WORKERS = {
    177: "8_6_3",
    178: "8_4_3_2",
    180: "6_4_4_3",
}


def parse_gap_list(content, start_marker):
    """Parse a GAP list starting at start_marker, handling nested brackets.
    Returns (list_of_raw_entries, end_position)."""
    idx = content.find(start_marker)
    if idx == -1:
        return None, -1

    # Find the opening [
    bracket_start = content.find('[', idx + len(start_marker))
    if bracket_start == -1:
        return None, -1

    # Parse entries: each entry is delimited by commas at depth 0
    entries = []
    pos = bracket_start + 1
    depth = 0
    current = ""
    in_string = False

    while pos < len(content):
        ch = content[pos]

        if ch == '"' and (pos == 0 or content[pos-1] != '\\'):
            in_string = not in_string
            current += ch
        elif in_string:
            current += ch
        elif ch == '[':
            depth += 1
            current += ch
        elif ch == ']':
            if depth == 0:
                # End of the outer list
                stripped = current.strip().rstrip(',').strip()
                if stripped:
                    entries.append(stripped)
                return entries, pos + 1
            depth -= 1
            current += ch
        elif ch == ',' and depth == 0:
            stripped = current.strip()
            if stripped:
                entries.append(stripped)
            current = ""
        elif ch == '\n' and depth == 0 and not current.strip():
            # Skip blank lines between entries
            pass
        else:
            current += ch
        pos += 1

    return entries, pos


def parse_checkpoint_g(filepath):
    """Parse a checkpoint .g file."""
    with open(filepath, 'r', errors='replace') as f:
        content = f.read()

    # Remove GAP line continuations
    content = content.replace('\\\n', '')

    result = {}

    # Parse completed keys
    keys, _ = parse_gap_list(content, '_CKPT_COMPLETED_KEYS :=')
    if keys is not None:
        # Keys are quoted strings like "key1"
        result['completedKeys'] = [k.strip('"') for k in keys]
    else:
        result['completedKeys'] = []

    # Parse total candidates
    m = re.search(r'_CKPT_TOTAL_CANDIDATES\s*:=\s*(\d+)', content)
    result['totalCandidates'] = int(m.group(1)) if m else 0

    # Parse added count
    m = re.search(r'_CKPT_ADDED_COUNT\s*:=\s*(\d+)', content)
    result['addedCount'] = int(m.group(1)) if m else 0

    # Parse generator sets - keep as raw strings for exact comparison
    gens, _ = parse_gap_list(content, '_CKPT_ALL_FPF_GENS :=')
    result['allFpfGens'] = gens if gens is not None else []

    # Parse invariant keys (optional)
    inv_keys, _ = parse_gap_list(content, '_CKPT_INV_KEYS :=')
    if inv_keys is not None:
        result['invKeys'] = [k.strip('"') for k in inv_keys]
    else:
        result['invKeys'] = None

    return result


def apply_log_deltas(ckpt, log_filepath):
    """Apply .log deltas to checkpoint data."""
    if not os.path.exists(log_filepath):
        return

    with open(log_filepath, 'r', errors='replace') as f:
        content = f.read()

    if content.strip() == '# Merged into .g checkpoint':
        return

    # Remove line continuations
    content = content.replace('\\\n', '')

    # Parse Add(_CKPT_COMPLETED_KEYS, "key"); lines
    for m in re.finditer(r'Add\(_CKPT_COMPLETED_KEYS,\s*"([^"]+)"\)', content):
        ckpt['completedKeys'].append(m.group(1))

    # Parse Add(_CKPT_ALL_FPF_GENS, [...]); lines
    for m in re.finditer(r'Add\(_CKPT_ALL_FPF_GENS,\s*(\[.*?\])\);', content):
        ckpt['allFpfGens'].append(m.group(1))

    # Parse updated totals (last occurrence wins)
    for m in re.finditer(r'_CKPT_TOTAL_CANDIDATES\s*:=\s*(\d+)', content):
        ckpt['totalCandidates'] = int(m.group(1))
    for m in re.finditer(r'_CKPT_ADDED_COUNT\s*:=\s*(\d+)', content):
        ckpt['addedCount'] = int(m.group(1))


def dedup_checkpoint(ckpt):
    """Remove duplicate completed keys and generator sets."""
    # Dedup completed keys (preserve order)
    seen_keys = set()
    unique_keys = []
    dup_keys = 0
    for k in ckpt['completedKeys']:
        if k not in seen_keys:
            seen_keys.add(k)
            unique_keys.append(k)
        else:
            dup_keys += 1

    # Dedup generator sets (preserve order, match inv keys)
    seen_gens = set()
    unique_gens = []
    unique_inv = [] if ckpt['invKeys'] is not None else None
    dup_gens = 0
    for i, g in enumerate(ckpt['allFpfGens']):
        if g not in seen_gens:
            seen_gens.add(g)
            unique_gens.append(g)
            if unique_inv is not None and ckpt['invKeys'] is not None and i < len(ckpt['invKeys']):
                unique_inv.append(ckpt['invKeys'][i])
        else:
            dup_gens += 1

    return {
        'completedKeys': unique_keys,
        'allFpfGens': unique_gens,
        'invKeys': unique_inv,
        'totalCandidates': ckpt['totalCandidates'],
        'addedCount': len(unique_gens),  # Corrected added count
    }, dup_keys, dup_gens


def write_checkpoint_g(ckpt, filepath):
    """Write a clean checkpoint .g file in GAP format."""
    with open(filepath, 'w') as f:
        f.write("# Checkpoint file - auto-generated\n")
        f.write(f"# {len(ckpt['completedKeys'])} combos, {len(ckpt['allFpfGens'])} groups\n\n")

        # Completed keys
        f.write("_CKPT_COMPLETED_KEYS := [\n")
        for i, k in enumerate(ckpt['completedKeys']):
            f.write(f'"{k}"')
            if i < len(ckpt['completedKeys']) - 1:
                f.write(",\n")
            else:
                f.write("\n")
        f.write("];\n\n")

        # Totals
        f.write(f"_CKPT_TOTAL_CANDIDATES := {ckpt['totalCandidates']};\n")
        f.write(f"_CKPT_ADDED_COUNT := {ckpt['addedCount']};\n\n")

        # Generator sets
        f.write("_CKPT_ALL_FPF_GENS := [\n")
        for i, g in enumerate(ckpt['allFpfGens']):
            f.write(g)
            if i < len(ckpt['allFpfGens']) - 1:
                f.write(",\n")
            else:
                f.write("\n")
        f.write("];\n")

        # Invariant keys
        if ckpt['invKeys'] is not None and len(ckpt['invKeys']) == len(ckpt['allFpfGens']):
            f.write("\n_CKPT_INV_KEYS := [\n")
            for i, k in enumerate(ckpt['invKeys']):
                f.write(f'"{k}"')
                if i < len(ckpt['invKeys']) - 1:
                    f.write(",\n")
                else:
                    f.write("\n")
            f.write("];\n")


if __name__ == "__main__":
    for wid, part_str in WORKERS.items():
        print(f"\n{'='*60}")
        print(f"Worker {wid} [{part_str}]")
        print(f"{'='*60}")

        g_file = os.path.join(CKPT_BASE, f"worker_{wid}", f"ckpt_17_{part_str}.g")
        log_file = os.path.join(CKPT_BASE, f"worker_{wid}", f"ckpt_17_{part_str}.log")

        if not os.path.exists(g_file):
            print(f"  ERROR: No checkpoint .g file found")
            continue

        # Backup
        backup = g_file + ".inflated.bak"
        if not os.path.exists(backup):
            shutil.copy2(g_file, backup)
            print(f"  Backed up to {os.path.basename(backup)}")

        # Parse
        print(f"  Parsing .g file ({os.path.getsize(g_file) // 1024}KB)...")
        ckpt = parse_checkpoint_g(g_file)
        print(f"  Loaded: {len(ckpt['completedKeys'])} combos, {len(ckpt['allFpfGens'])} groups"
              f"{', ' + str(len(ckpt['invKeys'])) + ' inv keys' if ckpt['invKeys'] else ''}")

        # Apply log deltas
        if os.path.exists(log_file) and os.path.getsize(log_file) > 30:
            print(f"  Applying .log deltas...")
            apply_log_deltas(ckpt, log_file)
            print(f"  After deltas: {len(ckpt['completedKeys'])} combos, {len(ckpt['allFpfGens'])} groups")

        # Dedup
        deduped, dup_keys, dup_gens = dedup_checkpoint(ckpt)
        print(f"  Dedup: removed {dup_keys} duplicate keys, {dup_gens} duplicate gen sets")
        print(f"  Result: {len(deduped['completedKeys'])} combos, {len(deduped['allFpfGens'])} groups")

        if dup_keys == 0 and dup_gens == 0:
            print(f"  No duplicates found - checkpoint is clean!")
            continue

        # Write deduped checkpoint
        print(f"  Writing clean checkpoint...")
        write_checkpoint_g(deduped, g_file)
        new_size = os.path.getsize(g_file) // 1024
        old_size = os.path.getsize(backup) // 1024
        print(f"  Done: {old_size}KB -> {new_size}KB ({100 * new_size // old_size}% of original)")

        # Truncate .log (all data is now in .g)
        with open(log_file, 'w') as f:
            f.write("# Merged into .g checkpoint\n")
        print(f"  .log truncated")

    print(f"\n{'='*60}")
    print("All checkpoints processed!")
