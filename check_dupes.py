"""Check if duplicate pairs in [6,5,4,2] are identical groups or just conjugate."""
import re

gens_file = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17\gens\gens_6_5_4_2.txt"

# Parse gens file (handles \ line continuations)
groups = []
buf = ""
with open(gens_file, 'r') as f:
    for line in f:
        line = line.rstrip('\n')
        if line.endswith('\\'):
            buf += line[:-1]
        else:
            buf += line
            if buf.strip() and len(buf.strip()) > 2:
                groups.append(buf.strip())
            buf = ""

print(f"Loaded {len(groups)} groups")

# Check specific duplicate pairs from the verification log
# All pairs have offset 26625
offset = 26625
pairs_to_check = [148, 394, 537, 538, 539, 540, 541, 542, 543, 816, 905, 1151, 1427]

identical_count = 0
conjugate_only = 0
for i in pairs_to_check:
    j = i + offset
    if j >= len(groups):
        print(f"  i={i}: j={j} out of range")
        continue
    # GAP 1-indexed, our list is 0-indexed
    g_i = groups[i-1]  # 1-indexed in GAP
    g_j = groups[j-1]
    if g_i == g_j:
        identical_count += 1
        if identical_count <= 3:
            print(f"  i={i}, j={j}: IDENTICAL")
    else:
        conjugate_only += 1
        if conjugate_only <= 3:
            print(f"  i={i}, j={j}: DIFFERENT generators")
            # Show first 100 chars of each
            print(f"    g[{i}]: {g_i[:100]}...")
            print(f"    g[{j}]: {g_j[:100]}...")

print(f"\nIdentical: {identical_count}")
print(f"Different generators: {conjugate_only}")

# Also check: are groups at offset 26625 apart ALWAYS identical?
# Sample more pairs
print("\n--- Broader sampling ---")
identical = 0
different = 0
for i in range(1, min(1000, len(groups) - offset + 1)):
    g_i = groups[i-1]
    g_j = groups[i-1+offset]
    if g_i == g_j:
        identical += 1
    else:
        different += 1

print(f"Sampled first 999 pairs at offset {offset}:")
print(f"  Identical: {identical}")
print(f"  Different: {different}")

# Check total: are ALL first 26625 groups duplicated?
if len(groups) >= 2 * offset:
    identical = 0
    for i in range(offset):
        if groups[i] == groups[i + offset]:
            identical += 1
    print(f"\nChecking all {offset} pairs at offset {offset}:")
    print(f"  Identical: {identical} / {offset}")
    print(f"  Non-identical: {offset - identical}")
