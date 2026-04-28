"""Back up and delete every combo file that contains at least one bogus
FPF group (non-transitive projection to some partition block). One tar.gz
archive per partition for easy restoration."""
import os
import re
import tarfile
import datetime
import sys

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"
TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def parse_partition_name(dname):
    return [int(x) for x in dname[1:-1].split(',')]


def blocks_for_partition(partition):
    blocks = []
    off = 0
    for size in partition:
        blocks.append(list(range(off + 1, off + size + 1)))
        off += size
    return blocks


def parse_cycle(s):
    s = s.strip()
    if s == '()' or not s.startswith('('):
        return ()
    return tuple(int(x) for x in s[1:-1].split(','))


def parse_perm(s):
    cycles = []
    depth = 0
    cur = ''
    for ch in s:
        cur += ch
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                cyc = parse_cycle(cur)
                if cyc:
                    cycles.append(cyc)
                cur = ''
    return cycles


def perm_to_dict(cycles):
    d = {}
    for cyc in cycles:
        for i, p in enumerate(cyc):
            d[p] = cyc[(i + 1) % len(cyc)]
    return d


def parse_group_generators(group_str):
    inner = group_str.strip()
    if inner.startswith('['):
        inner = inner[1:]
    if inner.endswith(']'):
        inner = inner[:-1]
    gens = []
    depth = 0
    cur = ''
    for ch in inner:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            if cur.strip():
                gens.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        gens.append(cur.strip())
    return [perm_to_dict(parse_perm(g)) for g in gens]


def is_projection_transitive(gens, block):
    block_set = set(block)
    start = block[0]
    orbit = {start}
    stack = [start]
    while stack:
        x = stack.pop()
        for g in gens:
            y = g.get(x, x)
            if y in block_set and y not in orbit:
                orbit.add(y)
                stack.append(y)
    return orbit == block_set


def read_groups(fp):
    with open(fp, 'r') as f:
        content = f.read()
    content = re.sub(r'\\\n', '', content)
    out = []
    for line in content.split('\n'):
        s = line.strip()
        if s and not s.startswith('#') and s.startswith('['):
            out.append(s)
    return out


def file_has_bogus(fp, blocks):
    for gs in read_groups(fp):
        gens = parse_group_generators(gs)
        if not all(is_projection_transitive(gens, b) for b in blocks):
            return True
    return False


# Enumerate partitions
partitions = []
for name in sorted(os.listdir(BASE)):
    if not (name.startswith('[') and name.endswith(']')):
        continue
    if os.path.isdir(os.path.join(BASE, name)):
        partitions.append(name)

# Skip [6,5,5,2] since we already handled it
SKIP = {'[6,5,5,2]'}

print(f"Scanning {len(partitions)} partitions for files with bogus groups...")
print(f"Timestamp: {TS}")
print()

total_files_affected = 0
total_partitions_affected = 0
total_bytes_backed_up = 0
for p in partitions:
    if p in SKIP:
        print(f"{p}: already handled, skipping")
        continue
    partition = parse_partition_name(p)
    blocks = blocks_for_partition(partition)
    p_dir = os.path.join(BASE, p)
    affected = []
    for fname in sorted(os.listdir(p_dir)):
        if not fname.endswith('.g') or 'backup' in fname or 'Copy' in fname:
            continue
        if file_has_bogus(os.path.join(p_dir, fname), blocks):
            affected.append(fname)
    if not affected:
        continue
    total_partitions_affected += 1
    total_files_affected += len(affected)
    sys.stdout.write(f"{p}: {len(affected)} bogus files ... ")
    sys.stdout.flush()
    # Create backup tar
    tar_path = os.path.join(BASE, f"{p}_bogus_backup_{TS}.tar.gz")
    orig_bytes = 0
    with tarfile.open(tar_path, "w:gz") as tar:
        for name in affected:
            fp = os.path.join(p_dir, name)
            orig_bytes += os.path.getsize(fp)
            tar.add(fp, arcname=name)
    tar_size = os.path.getsize(tar_path)
    total_bytes_backed_up += orig_bytes
    # Delete originals
    for name in affected:
        os.remove(os.path.join(p_dir, name))
    print(f"backup {tar_size:,} B (orig {orig_bytes:,} B) -> deleted")

print()
print(f"=== Summary ===")
print(f"Partitions affected: {total_partitions_affected}")
print(f"Files backed up and deleted: {total_files_affected}")
print(f"Total original bytes: {total_bytes_backed_up:,}")
