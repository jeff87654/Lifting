"""Scan every partition directory in parallel_s18 for bogus FPF groups.
For each group, verify that its projection to each block of the partition
is transitive. A group with non-transitive projection to any block is
not a valid FPF subdirect product (fails the subdirect surjectivity)."""
import os
import re
import sys
import time

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18"
OUTPUT = r"C:\Users\jeffr\Downloads\Lifting\scan_all_partitions_bogus.log"


def parse_partition_name(dname):
    inner = dname[1:-1]
    return [int(x) for x in inner.split(',')]


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


def log(msg, fh):
    print(msg)
    fh.write(msg + "\n")
    fh.flush()


with open(OUTPUT, 'w') as fh:
    log(f"=== Scanning all partitions for bogus FPF groups ===", fh)
    log(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}", fh)
    log("", fh)

    partitions = []
    for name in sorted(os.listdir(BASE)):
        if not (name.startswith('[') and name.endswith(']')):
            continue
        if os.path.isdir(os.path.join(BASE, name)):
            partitions.append(name)

    log(f"{'Partition':<22} {'Total':>10} {'Bogus':>8} {'Pct':>6}", fh)
    log("-" * 60, fh)
    grand_total = 0
    grand_bogus = 0
    parts_with_bogus = 0
    per_part = {}
    start = time.time()

    for p in partitions:
        partition = parse_partition_name(p)
        blocks = blocks_for_partition(partition)
        p_dir = os.path.join(BASE, p)
        p_total = 0
        p_bogus = 0
        for fname in sorted(os.listdir(p_dir)):
            if not fname.endswith('.g') or 'backup' in fname or 'Copy' in fname:
                continue
            for gs in read_groups(os.path.join(p_dir, fname)):
                p_total += 1
                gens = parse_group_generators(gs)
                if not all(is_projection_transitive(gens, b) for b in blocks):
                    p_bogus += 1
        grand_total += p_total
        grand_bogus += p_bogus
        per_part[p] = (p_total, p_bogus)
        if p_bogus > 0:
            parts_with_bogus += 1
            pct = 100.0 * p_bogus / p_total if p_total > 0 else 0.0
            log(f"{p:<22} {p_total:>10,} {p_bogus:>8,} {pct:>5.1f}%", fh)

    log("-" * 60, fh)
    log(f"{'TOTAL':<22} {grand_total:>10,} {grand_bogus:>8,} "
        f"{100*grand_bogus/max(grand_total,1):>5.1f}%", fh)
    log("", fh)
    log(f"Partitions with bogus groups: {parts_with_bogus} / {len(partitions)}", fh)
    log(f"Total scan time: {time.time() - start:.1f}s", fh)
    log(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}", fh)
