"""Rebuild missing gens files by parsing checkpoint .g files directly in Python.

Parses GAP cycle notation permutations from _CKPT_ALL_FPF_GENS and converts
to ListPerm(g, 17) format for the gens files.

NOTE: This extracts generators from the .g file ONLY (no .log).
The count may differ from expected because the .g stores pre-dedup candidates.
"""
import re
import os

N = 17
GENS_DIR = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17\gens"

# Partitions to rebuild with their checkpoint paths and expected counts
MISSING = [
    ([17], r"parallel_s17\checkpoints\worker_47\ckpt_17_17.g", 10),
    ([15,2], r"parallel_s17\checkpoints\worker_48\ckpt_17_15_2.g", 232),
    ([14,3], r"parallel_s17\checkpoints\worker_49\ckpt_17_14_3.g", 231),
    ([11,2,2,2], r"parallel_s17\checkpoints\worker_50\ckpt_17_11_2_2_2.g", 56),
    ([9,5,3], r"parallel_s17\checkpoints\worker_158\ckpt_17_9_5_3.g", 1449),
    ([7,5,5], r"parallel_s17\checkpoints\worker_55\ckpt_17_7_5_5.g", 298),
    ([7,4,4,2], r"parallel_s17\checkpoints\worker_104\ckpt_17_7_4_4_2.g", 5092),
    ([7,2,2,2,2,2], r"parallel_s17\checkpoints\worker_57\ckpt_17_7_2_2_2_2_2.g", 289),
    ([6,6,5], r"parallel_s17\checkpoints\worker_146\ckpt_17_6_6_5.g", 7251),
    ([6,5,2,2,2], r"parallel_s17\checkpoints\worker_96\ckpt_17_6_5_2_2_2.g", 5959),
    ([6,3,2,2,2,2], r"parallel_s17\checkpoints\worker_95\ckpt_17_6_3_2_2_2_2.g", 8070),
    ([5,4,4,4], r"parallel_s17\checkpoints\worker_142\ckpt_17_5_4_4_4.g", 25129),
    ([5,4,4,2,2], r"parallel_s17\checkpoints\worker_140\ckpt_17_5_4_4_2_2.g", 28310),
    ([5,4,3,3,2], r"parallel_s17\checkpoints\worker_103\ckpt_17_5_4_3_3_2.g", 5607),
    ([5,4,2,2,2,2], r"parallel_s17\checkpoints\worker_92\ckpt_17_5_4_2_2_2_2.g", 6956),
    ([5,3,3,3,3], r"parallel_s17\checkpoints\worker_68\ckpt_17_5_3_3_3_3.g", 481),
    ([5,2,2,2,2,2,2], r"parallel_s17\checkpoints\worker_90\ckpt_17_5_2_2_2_2_2_2.g", 681),
    ([4,3,2,2,2,2,2], r"parallel_s17\checkpoints\worker_136\ckpt_17_4_3_2_2_2_2_2.g", 9086),
    ([3,3,3,3,3,2], r"parallel_s17\checkpoints\worker_79\ckpt_17_3_3_3_3_3_2.g", 424),
    ([3,2,2,2,2,2,2,2], r"parallel_s17\checkpoints\worker_137\ckpt_17_3_2_2_2_2_2_2_2.g", 653),
]


def parse_gap_perm(s, degree=17):
    """Parse a GAP cycle notation permutation into ListPerm format.

    E.g., "(1,2,3)(4,5)" -> [2,3,1,5,4,6,7,...,17]
    """
    perm = list(range(1, degree + 1))  # identity
    # Find all cycles
    for cycle_match in re.finditer(r'\(([^)]+)\)', s):
        cycle_str = cycle_match.group(1)
        elements = [int(x.strip()) for x in cycle_str.split(',')]
        # Apply cycle: each element maps to the next
        for i in range(len(elements)):
            perm[elements[i] - 1] = elements[(i + 1) % len(elements)]
    return perm


def parse_checkpoint_gens(filepath):
    """Parse _CKPT_ALL_FPF_GENS from a checkpoint .g file.

    Returns list of generator lists, where each generator list is
    [[perm1_as_list, perm2_as_list, ...], ...]
    """
    with open(filepath, 'r', errors='replace') as f:
        content = f.read()

    # Remove GAP line continuations (backslash + newline)
    content = content.replace('\\\n', '')

    # Find the _CKPT_ALL_FPF_GENS section
    start = content.find('_CKPT_ALL_FPF_GENS := [')
    if start == -1:
        print(f"  ERROR: No _CKPT_ALL_FPF_GENS found in {filepath}")
        return []

    # Find the matching closing bracket
    # The structure is: _CKPT_ALL_FPF_GENS := [ [gens1], [gens2], ... ];
    start += len('_CKPT_ALL_FPF_GENS := [')

    # Parse each generator set: each is a [...] block
    gen_sets = []
    pos = start
    depth = 0
    current_set_start = None

    while pos < len(content):
        ch = content[pos]
        if ch == '[':
            if depth == 0:
                current_set_start = pos
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0 and current_set_start is not None:
                gen_text = content[current_set_start:pos+1]
                # Parse individual permutations from this gen set
                perms = []
                # Each permutation is a sequence of cycles or just "()" for identity
                # Generator sets look like: [(1,2,3),(4,5), (1,3)(2,4)]
                # where commas at depth 0 separate generators
                inner = gen_text[1:-1]  # strip outer []

                # Split by commas that are not inside parentheses
                perm_strs = []
                current = ""
                pdepth = 0
                for c in inner:
                    if c == '(':
                        pdepth += 1
                        current += c
                    elif c == ')':
                        pdepth -= 1
                        current += c
                        if pdepth == 0:
                            # End of a cycle, but might be more cycles for same perm
                            pass
                    elif c == ',' and pdepth == 0:
                        # Separator between permutations
                        if current.strip():
                            perm_strs.append(current.strip())
                        current = ""
                    else:
                        current += c
                if current.strip():
                    perm_strs.append(current.strip())

                # Convert each permutation string to ListPerm format
                for ps in perm_strs:
                    perm = parse_gap_perm(ps, N)
                    perms.append(perm)

                if perms:
                    gen_sets.append(perms)
                current_set_start = None
            elif depth < 0:
                # We've gone past the end of _CKPT_ALL_FPF_GENS
                break
        pos += 1

    return gen_sets


def write_gens_file(gen_sets, filepath):
    """Write generator sets in the gens file format."""
    with open(filepath, 'w') as f:
        for gens in gen_sets:
            f.write(str(gens) + '\n')


if __name__ == "__main__":
    base_dir = r"C:\Users\jeffr\Downloads\Lifting"

    print(f"Rebuilding {len(MISSING)} missing gens files from checkpoints (Python parser)")

    total_ok = 0
    total_mismatch = 0

    for partition, ckpt_rel, expected in MISSING:
        part_str = "_".join(str(x) for x in partition)
        ckpt_path = os.path.join(base_dir, ckpt_rel)
        gens_path = os.path.join(GENS_DIR, f"gens_{part_str}.txt")

        print(f"\n  [{part_str}] (expected {expected}):")

        if not os.path.exists(ckpt_path):
            print(f"    ERROR: Checkpoint not found: {ckpt_path}")
            continue

        gen_sets = parse_checkpoint_gens(ckpt_path)
        print(f"    Parsed {len(gen_sets)} generator sets from .g file")

        if len(gen_sets) == expected:
            status = "EXACT MATCH"
            total_ok += 1
        elif len(gen_sets) > expected:
            status = f"PRE-DEDUP ({len(gen_sets) - expected} extra)"
            total_mismatch += 1
        else:
            status = f"MISSING {expected - len(gen_sets)} groups!"
            total_mismatch += 1

        print(f"    {status}")

        # Write the gens file regardless
        write_gens_file(gen_sets, gens_path)
        print(f"    Wrote to {gens_path}")

    print(f"\n=== Summary ===")
    print(f"  Exact match: {total_ok}")
    print(f"  Mismatch: {total_mismatch}")
    print(f"\nNOTE: Partitions with 'PRE-DEDUP' have extra duplicate groups.")
    print(f"These will need GAP-based dedup later for exact counts.")
