"""Fix gens files with checkpoint duplication by removing exact duplicates."""
import os

GENS_DIR = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17\gens"

def load_gens(filepath):
    groups = []
    buf = ""
    with open(filepath, 'r', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            if line.endswith('\\'):
                buf += line[:-1]
            else:
                buf += line
                if buf.strip() and len(buf.strip()) > 2:
                    groups.append(buf.strip())
                buf = ""
    return groups

affected = ["6_5_4_2", "8_5_4", "6_4_3_2_2"]

for part_str in affected:
    filepath = os.path.join(GENS_DIR, f"gens_{part_str}.txt")
    groups = load_gens(filepath)
    original = len(groups)

    # Deduplicate preserving order
    seen = set()
    unique = []
    for g in groups:
        if g not in seen:
            seen.add(g)
            unique.append(g)

    print(f"[{part_str}]: {original} -> {len(unique)} ({original - len(unique)} removed)")

    # Backup and write deduped file
    backup = filepath + ".bak"
    os.rename(filepath, backup)
    with open(filepath, 'w') as f:
        for g in unique:
            f.write(g + '\n')

    print(f"  Written to {filepath} (backup at .bak)")

print("\nDone!")
