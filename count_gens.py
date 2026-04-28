import os

gens_dir = r'C:\Users\jeffr\Downloads\Lifting\parallel_s17\gens'
results = []

for fname in sorted(os.listdir(gens_dir)):
    if not fname.endswith('.txt'):
        continue
    fpath = os.path.join(gens_dir, fname)
    with open(fpath, 'r') as f:
        raw_lines = f.readlines()

    # Join continuation lines (lines ending with backslash)
    logical_lines = []
    current = ''
    for line in raw_lines:
        stripped = line.rstrip('\n').rstrip('\r')
        if stripped.endswith('\\'):
            # backslash continuation - remove trailing backslash and append
            current += stripped[:-1]
        else:
            current += stripped
            if current.strip():  # non-empty logical line = one group
                logical_lines.append(current)
            current = ''
    # Handle any remaining content (file doesn't end with newline)
    if current.strip():
        logical_lines.append(current)

    count = len(logical_lines)
    results.append((fname, count))

# Sort by count descending
results.sort(key=lambda x: -x[1])

grand_total = 0
for fname, count in results:
    print(f'{fname}: {count}')
    grand_total += count

print()
print(f'Grand total: {grand_total}')
print(f'Number of files: {len(results)}')
