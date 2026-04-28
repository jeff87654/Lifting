import collections

fp = 'parallel_s18/[4,4,4,4,2]/[2,1]_[4,3]_[4,3]_[4,3]_[4,3].g'
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
if dups > 0:
    print()
    print('Most-duplicated:')
    for s, c in counts.most_common(3):
        if c > 1:
            print(f'  {c}x  {s[:100]}...')

# Also check: are the recovered 113K (last 113381 lines) overlapping with the original 137K?
recovered_set = set(groups_full[-113381:])
original_set = set(groups_full[:-113381])
overlap = recovered_set & original_set
print()
print(f'Original groups (first 137584): {len(original_set)} distinct')
print(f'Recovered groups (last 113381): {len(recovered_set)} distinct')
print(f'Overlap (same generator string in both): {len(overlap)}')
