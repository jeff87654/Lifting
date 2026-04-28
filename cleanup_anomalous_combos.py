"""Cleanup the 4 anomalous combo files and the stale ' - Copy' file.

Strategy:
  1. Backup every file we're about to modify with a timestamp suffix.
  2. For each anomalous combo file, compute the set difference
     (this_file_groups - groups_in_other_combo_files).
  3. Rewrite the anomalous file keeping only groups unique to it,
     preserving the original multi-line format. Update '# deduped: N'.
  4. Backup then delete the stale ' - Copy' file in [4,4,4,4,2].
"""
import os
import re
import shutil
import datetime

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"
TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

ANOMALOUS = [
    ("[4,4,4,4,2]", "[2,1]_[4,3]_[4,3]_[4,4]_[4,4].g"),
    ("[6,4,4,2,2]", "[2,1]_[2,1]_[4,3]_[4,4]_[6,3].g"),
    ("[4,4,3,3,2,2]", "[2,1]_[2,1]_[3,1]_[3,1]_[4,3]_[4,4].g"),
    ("[8,2,2,2,2,2]", "[2,1]_[2,1]_[2,1]_[2,1]_[2,1]_[8,23].g"),
]
STALE_COPY = os.path.join(
    BASE, "[4,4,4,4,2]", "[2,1]_[4,3]_[4,3]_[4,3]_[4,3] - Copy.g"
)


def parse_combo_file_preserving(fp):
    """Return (header_lines, groups) where groups = list of (joined_form, raw_lines)."""
    with open(fp, 'r') as f:
        lines = f.readlines()
    header_lines = []
    groups = []
    current_raw = []
    current_joined = ""
    in_header = True
    for line in lines:
        stripped_nl = line.rstrip('\n')
        # Header comments (only at top, before any group)
        if in_header and stripped_nl.startswith('#'):
            header_lines.append(line)
            continue
        if in_header and stripped_nl == '':
            header_lines.append(line)
            continue
        in_header = False
        if current_raw:
            # Continuation of previous group
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
            # Start of a new group
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
    """Return set of joined group strings from a combo file."""
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


def backup(fp):
    bak = fp + f".backup_{TS}"
    shutil.copy2(fp, bak)
    sz = os.path.getsize(bak)
    print(f"  BACKUP  {os.path.relpath(fp, BASE)}  ->  ...backup_{TS} ({sz:,} bytes)")
    return bak


def cleanup_anomalous(part_dir, fname):
    fp = os.path.join(part_dir, fname)
    if not os.path.exists(fp):
        print(f"  SKIP: {fp} not found")
        return
    print(f"\n--- Cleaning {fname} in {os.path.basename(part_dir)} ---")
    backup(fp)
    # Collect groups in all OTHER combo files of the same partition
    others = set()
    for other in sorted(os.listdir(part_dir)):
        if other == fname or not other.endswith('.g') or 'backup' in other:
            continue
        if 'Copy' in other:
            continue
        others |= joined_groups_in_file(os.path.join(part_dir, other))
    # Parse the anomalous file preserving line format
    header, groups = parse_combo_file_preserving(fp)
    kept = []
    dropped = 0
    for joined, raw in groups:
        if joined in others:
            dropped += 1
        else:
            kept.append(raw)
    # Rewrite header: replace '# deduped: N' with new count
    new_header = []
    for line in header:
        m = re.match(r'(# deduped:\s*)(\d+)', line)
        if m:
            new_header.append(f"# deduped: {len(kept)}\n")
        else:
            new_header.append(line)
    # Write cleaned file
    with open(fp, 'w') as f:
        for line in new_header:
            f.write(line)
        for raw in kept:
            for l in raw:
                f.write(l)
    print(f"  REWROTE {fname}: kept {len(kept)}, dropped {dropped} duplicates")
    sz = os.path.getsize(fp)
    print(f"  Final size: {sz:,} bytes")


print(f"Timestamp: {TS}")
print(f"Backups will have suffix: .backup_{TS}")

# Step 1-3: Clean up 4 anomalous combo files
for part_name, fname in ANOMALOUS:
    cleanup_anomalous(os.path.join(BASE, part_name), fname)

# Step 4: Back up and delete the stale ' - Copy' file
print(f"\n--- Stale Copy file ---")
if os.path.exists(STALE_COPY):
    backup(STALE_COPY)
    os.remove(STALE_COPY)
    print(f"  DELETED {os.path.relpath(STALE_COPY, BASE)}")
else:
    print(f"  SKIP: {STALE_COPY} not found")

print("\nDone.")
