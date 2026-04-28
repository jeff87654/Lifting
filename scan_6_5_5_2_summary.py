"""Compact summary of bogus groups in [6,5,5,2] — per-file counts."""
import os
import re

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18\[6,5,5,2]"
BLOCKS = [list(range(1, 7)), list(range(7, 12)),
          list(range(12, 17)), list(range(17, 19))]


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
    idx = 0
    for line in content.split('\n'):
        s = line.strip()
        if s and not s.startswith('#') and s.startswith('['):
            idx += 1
            out.append((idx, s))
    return out


print(f"{'File':<55} {'Total':>7} {'Bogus':>7}")
print("-" * 72)
grand_total = 0
grand_bogus = 0
files_with_bogus = 0
for fname in sorted(os.listdir(BASE)):
    if not fname.endswith('.g') or 'backup' in fname or 'Copy' in fname:
        continue
    groups = read_groups(os.path.join(BASE, fname))
    bogus = 0
    for idx, gs in groups:
        gens = parse_group_generators(gs)
        if not all(is_projection_transitive(gens, b) for b in BLOCKS):
            bogus += 1
    grand_total += len(groups)
    if bogus > 0:
        grand_bogus += bogus
        files_with_bogus += 1
        print(f"{fname:<55} {len(groups):>7} {bogus:>7}")

print("-" * 72)
print(f"Files with bogus: {files_with_bogus}")
print(f"Total groups in [6,5,5,2]: {grand_total:,}")
print(f"Total bogus: {grand_bogus}  ({100*grand_bogus/grand_total:.1f}%)")
print(f"After removing: {grand_total - grand_bogus:,} valid groups")
