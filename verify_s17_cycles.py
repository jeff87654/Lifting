"""
Verify s17_subgroups_cycles.g:
1. Orbit types match the image-list version's orbit type counts
2. S16 large invariants generators match the corresponding index in the cycles file
"""
import ast
import re
from collections import defaultdict

CYCLES_FILE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache\s17_subgroups_cycles.g"
COUNTS_FILE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache\s17_orbit_type_counts.txt"
INVARIANTS_FILE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache\s16_large_invariants.g"

N = 17


def parse_cycle_string(s):
    """Parse GAP cycle notation string like '(1,2)(3,4,5)' into list of cycles."""
    cycles = []
    for m in re.finditer(r'\(([^)]+)\)', s):
        cycle = [int(x) for x in m.group(1).split(',')]
        if len(cycle) > 1:
            cycles.append(cycle)
    return cycles


def orbit_type_from_cycles(gen_cycle_lists, n=17):
    """Compute orbit type from list of generators (each a list of cycles)."""
    parent = list(range(n + 1))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    for cycles in gen_cycle_lists:
        for cycle in cycles:
            for k in range(len(cycle) - 1):
                union(cycle[k], cycle[k + 1])

    sizes = defaultdict(int)
    for i in range(1, n + 1):
        sizes[find(i)] += 1
    return tuple(sorted(sizes.values(), reverse=True))


def parse_entry_cycles(entry_str):
    """Parse a cycles file entry like '[ (1,2)(3,4), (5,6) ]' into list of cycle-notation strings."""
    entry_str = entry_str.strip()
    if entry_str.startswith("["):
        entry_str = entry_str[1:]
    if entry_str.endswith("]"):
        entry_str = entry_str[:-1]
    entry_str = entry_str.strip()
    if not entry_str:
        return []
    # Split generators by commas NOT inside parentheses
    gens = []
    depth = 0
    current = []
    for ch in entry_str:
        if ch == '(':
            depth += 1
            current.append(ch)
        elif ch == ')':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            g = ''.join(current).strip()
            if g:
                gens.append(g)
            current = []
        else:
            current.append(ch)
    g = ''.join(current).strip()
    if g:
        gens.append(g)
    return gens


def check_orbit_types():
    """Check 1: orbit types from cycles file match expected counts."""
    print("=== Check 1: Orbit types from cycle notation ===")

    # Load expected counts
    expected = {}
    with open(COUNTS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("["):
                bracket_end = line.index("]")
                label = line[:bracket_end + 1]
                count = int(line[bracket_end + 1:].strip())
                parts = tuple(int(x) for x in label[1:-1].split(","))
                expected[parts] = count

    # Count orbit types from cycles file
    actual = defaultdict(int)
    total = 0
    with open(CYCLES_FILE, "r") as f:
        in_data = False
        for line in f:
            stripped = line.strip()
            if not in_data:
                if stripped.startswith("return ["):
                    in_data = True
                continue
            if stripped == "];":
                break
            # Each entry is on one line: [ (1,2)(3,4), (5,6) ]  or with trailing comma
            entry = stripped
            if entry.endswith(","):
                entry = entry[:-1]
            if not entry.startswith("["):
                continue
            gen_strs = parse_entry_cycles(entry)
            gen_cycle_lists = [parse_cycle_string(g) for g in gen_strs]
            ot = orbit_type_from_cycles(gen_cycle_lists, N)
            actual[ot] += 1
            total += 1
            if total % 200000 == 0:
                print(f"  {total} checked...")

    print(f"  Total: {total} groups, {len(actual)} orbit types")

    # Compare
    all_ok = True
    for ot in sorted(set(list(expected.keys()) + list(actual.keys()))):
        e = expected.get(ot, 0)
        a = actual.get(ot, 0)
        if e != a:
            print(f"  MISMATCH {list(ot)}: expected={e}, got={a}")
            all_ok = False

    if all_ok:
        print("  ALL ORBIT TYPES MATCH")
    return all_ok


def check_large_invariants():
    """Check 2: generators in s16_large_invariants.g match s17_subgroups_cycles.g."""
    print("\n=== Check 2: Large invariants generator cross-check ===")

    # First pass: collect all (index, generators) from invariants file
    print("  Parsing large invariants file...")
    inv_entries = {}  # index -> list of generator strings
    current_index = None
    current_gens = None
    with open(INVARIANTS_FILE, "r") as f:
        buf = ""
        for line in f:
            stripped = line.rstrip("\n").rstrip("\r")
            # Handle continuation lines
            if stripped.endswith("\\"):
                buf += stripped[:-1]
                continue
            buf += stripped
            stripped = buf.strip()
            buf = ""

            m = re.match(r'index\s*:=\s*(\d+)', stripped)
            if m:
                current_index = int(m.group(1))

            m = re.match(r'generators\s*:=\s*\[(.+)\]', stripped)
            if m:
                # Parse generator strings
                gen_text = m.group(1)
                # Split by ", " respecting quotes
                gens = []
                for gm in re.finditer(r'"([^"]*)"', gen_text):
                    gens.append(gm.group(1))
                if current_index is not None:
                    inv_entries[current_index] = gens
                current_index = None

    print(f"  Found {len(inv_entries)} entries with generators")
    min_idx = min(inv_entries.keys())
    max_idx = max(inv_entries.keys())
    print(f"  Index range: {min_idx} to {max_idx}")

    # Second pass: read cycles file, collect entries at needed indices
    print("  Reading cycles file for matching indices...")
    needed = set(inv_entries.keys())
    cycles_at_index = {}
    idx = 0
    with open(CYCLES_FILE, "r") as f:
        in_data = False
        for line in f:
            stripped = line.strip()
            if not in_data:
                if stripped.startswith("return ["):
                    in_data = True
                continue
            if stripped == "];":
                break
            entry = stripped
            if entry.endswith(","):
                entry = entry[:-1]
            if not entry.startswith("["):
                continue
            idx += 1
            if idx in needed:
                gen_strs = parse_entry_cycles(entry)
                cycles_at_index[idx] = gen_strs
            if idx > max_idx:
                break
            if idx % 200000 == 0:
                print(f"    scanned {idx} entries...")

    print(f"  Collected {len(cycles_at_index)} matching entries")

    # Compare
    matches = 0
    mismatches = 0
    missing = 0
    for index in sorted(inv_entries.keys()):
        inv_gens = inv_entries[index]
        if index not in cycles_at_index:
            missing += 1
            if missing <= 5:
                print(f"  MISSING: index {index} not found in cycles file")
            continue

        cyc_gens = cycles_at_index[index]

        # Normalize both: remove spaces, sort generators for comparison
        inv_normalized = sorted(g.replace(" ", "") for g in inv_gens)
        cyc_normalized = sorted(g.replace(" ", "") for g in cyc_gens)

        if inv_normalized == cyc_normalized:
            matches += 1
        else:
            mismatches += 1
            if mismatches <= 5:
                print(f"  MISMATCH at index {index}:")
                print(f"    invariants: {inv_gens}")
                print(f"    cycles:     {cyc_gens}")

    print(f"  Matches: {matches}, Mismatches: {mismatches}, Missing: {missing}")
    if mismatches == 0 and missing == 0:
        print("  ALL GENERATORS MATCH")
    return mismatches == 0 and missing == 0


def main():
    ok1 = check_orbit_types()
    ok2 = check_large_invariants()
    print(f"\n{'='*50}")
    if ok1 and ok2:
        print("ALL CHECKS PASSED")
    else:
        print("SOME CHECKS FAILED")


if __name__ == "__main__":
    main()
