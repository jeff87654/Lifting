"""Clean up the newly-discovered combo files with dedup > candidates.
Same approach as cleanup_anomalous_combos.py: back up, then rewrite
each file keeping only groups UNIQUE to it (set difference vs other
combo files in the same partition)."""
import os
import re
import shutil
import datetime

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"
TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

ANOMALOUS = [
    ("[8,4,2,2,2]", "[2,1]_[2,1]_[2,1]_[4,4]_[8,26].g"),
    ("[6,4,4,2,2]", "[2,1]_[2,1]_[4,2]_[4,4]_[6,9].g"),
]


def parse_combo_file_preserving(fp):
    with open(fp, 'r') as f:
        lines = f.readlines()
    header_lines = []
    groups = []
    current_raw = []
    current_joined = ""
    in_header = True
    for line in lines:
        stripped_nl = line.rstrip('\n')
        if in_header and stripped_nl.startswith('#'):
            header_lines.append(line)
            continue
        if in_header and stripped_nl == '':
            header_lines.append(line)
            continue
        in_header = False
        if current_raw:
            current_raw.append(line)
            if stripped_nl.endswith('\\'):
                current_joined += stripped_nl[:-1]
            else:
                current_joined += stripped_nl
                groups.append((current_joined, current_raw))
                current_raw = []
                current_joined = ""
        else:
            if stripped_nl == '':
                continue
            current_raw = [line]
            if stripped_nl.endswith('\\'):
                current_joined = stripped_nl[:-1]
            else:
                current_joined = stripped_nl
                groups.append((current_joined, current_raw))
                current_raw = []
                current_joined = ""
    if current_raw:
        groups.append((current_joined, current_raw))
    return header_lines, groups


def joined_groups_in_file(fp):
    try:
        with open(fp, 'r') as f:
            content = f.read()
    except Exception:
        return set()
    content = re.sub(r'\\\n', '', content)
    out = set()
    for line in content.split('\n'):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        if s.startswith('['):
            out.add(s)
    return out


print(f"Timestamp: {TS}")

for part_name, fname in ANOMALOUS:
    part_dir = os.path.join(BASE, part_name)
    fp = os.path.join(part_dir, fname)
    if not os.path.exists(fp):
        print(f"  SKIP: {fp} not found")
        continue
    print(f"\n--- Cleaning {fname} in {part_name} ---")
    # Backup
    bak = fp + f".backup_{TS}"
    shutil.copy2(fp, bak)
    print(f"  BACKUP: {bak} ({os.path.getsize(bak):,} bytes)")
    # Collect groups in all OTHER combo files of the same partition
    others = set()
    for other in sorted(os.listdir(part_dir)):
        if other == fname or not other.endswith('.g'):
            continue
        if 'backup' in other or 'Copy' in other:
            continue
        others |= joined_groups_in_file(os.path.join(part_dir, other))
    # Parse this file preserving line format
    header, groups = parse_combo_file_preserving(fp)
    kept = []
    dropped = 0
    for joined, raw in groups:
        if joined in others:
            dropped += 1
        else:
            kept.append(raw)
    # Rewrite header with corrected deduped count
    new_header = []
    for line in header:
        m = re.match(r'(# deduped:\s*)(\d+)', line)
        if m:
            new_header.append(f"# deduped: {len(kept)}\n")
        else:
            new_header.append(line)
    with open(fp, 'w') as f:
        for line in new_header:
            f.write(line)
        for raw in kept:
            for l in raw:
                f.write(l)
    print(f"  REWROTE {fname}: kept {len(kept)}, dropped {dropped} duplicates")
    print(f"  Final size: {os.path.getsize(fp):,} bytes")

print("\nDone.")
