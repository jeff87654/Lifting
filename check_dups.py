import collections

fp = 'parallel_s18/[4,4,4,4,2]/[2,1]_[4,3]_[4,3]_[4,3]_[4,3].g.backup_20260415_105206'
groups_full = []
current = ''
with open(fp) as f:
    for line in f:
        line = line.rstrip('\n')
        if line.startswith('#'):
            continue
        if not line:
            continue
        if line.endswith('\\'):
            current += line[:-1]
        else:
            current += line
            if current:
                groups_full.append(current)
            current = ''

counts = collections.Counter(groups_full)
print(f'Total full group representations: {len(groups_full)}')
print(f'Distinct full group strings: {len(counts)}')
dups = sum(c-1 for c in counts.values() if c > 1)
print(f'Exact duplicates: {dups}')
print()
print('Top 5 most-duplicated full group strings (first 100 chars):')
for s, c in counts.most_common(5):
    print(f'  {c}x  {s[:100]}...')
