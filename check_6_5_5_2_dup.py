import os
import re
import collections

BASE = r"C:\Users\jeffr\Downloads\Lifting\parallel_s18\[6,5,5,2]"

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

group_files = collections.defaultdict(list)
for fname in sorted(os.listdir(BASE)):
    if not fname.endswith('.g') or 'backup' in fname or 'Copy' in fname:
        continue
    for g in read_groups(os.path.join(BASE, fname)):
        group_files[g].append(fname)

dup = {g: fs for g, fs in group_files.items() if len(fs) > 1}
print(f"Duplicate count: {len(dup)}")
for g, fs in dup.items():
    print(f"\nGroup: {g[:200]}...")
    print(f"  Found in: {fs}")

# Also check within-file duplicates
for fname in sorted(os.listdir(BASE)):
    if not fname.endswith('.g') or 'backup' in fname or 'Copy' in fname:
        continue
    gs = read_groups(os.path.join(BASE, fname))
    cnt = collections.Counter(gs)
    within = {g: c for g, c in cnt.items() if c > 1}
    if within:
        print(f"\nWithin-file dup in {fname}: {len(within)} duplicated groups")
        for g, c in list(within.items())[:3]:
            print(f"  {c}x: {g[:200]}...")
