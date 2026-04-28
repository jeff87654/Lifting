#!/usr/bin/env python3
"""
build_s16_master.py - Build a single master file of all S16 conjugacy class representatives.

Produces s16_subgroups.g in the same format as s15_subgroups.g:
  return [
    [ [img1, ..., img16], [img1, ..., img16] ],   # group 1
    ...
  ];

Sources:
  - S15 subgroups (fixing point 16): 159,129 groups from s15_subgroups.g
  - FPF subgroups (no fixed points): 527,036 groups from gen files
    - Fresh run for 52 partitions
    - Old run for [4,4,4,4] (cycle notation), [16], [2,2,2,2,2,2,2,2] (image-list)

Total expected: 686,165
"""

import os
import re
import ast
import sys
import time

BASE_DIR = r"C:\Users\jeffr\Downloads\Lifting"
S15_FILE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache\s15_subgroups.g"
FRESH_GENS = os.path.join(BASE_DIR, "parallel_s16_fresh", "gens")
OLD_GENS = os.path.join(BASE_DIR, "parallel_s16", "gens")
OUTPUT_FILE = os.path.join(BASE_DIR, "s16_subgroups.g")

USE_OLD = {"4_4_4_4", "16", "2_2_2_2_2_2_2_2"}

DEGREE = 16

# All 55 FPF partitions with expected counts
EXPECTED = {
    "16": 1954, "14_2": 142, "13_3": 26, "12_4": 8167, "12_2_2": 3414,
    "11_5": 51, "11_3_2": 39, "10_6": 2547, "10_4_2": 4329, "10_3_3": 681,
    "10_2_2_2": 1072, "9_7": 392, "9_5_2": 847, "9_4_3": 3146,
    "9_3_2_2": 1262, "8_8": 20082, "8_6_2": 29440, "8_5_3": 3594,
    "8_4_4": 80189, "8_4_2_2": 62751, "8_3_3_2": 6341, "8_2_2_2_2": 8019,
    "7_7_2": 94, "7_6_3": 955, "7_5_4": 633, "7_5_2_2": 277,
    "7_4_3_2": 1117, "7_3_3_3": 216, "7_3_2_2_2": 287, "6_6_4": 21109,
    "6_6_2_2": 9107, "6_5_5": 1276, "6_5_3_2": 3311, "6_4_4_2": 60967,
    "6_4_3_3": 9885, "6_4_2_2_2": 22922, "6_3_3_2_2": 4174,
    "6_2_2_2_2_2": 2456, "5_5_4_2": 1864, "5_5_3_3": 356,
    "5_5_2_2_2": 482, "5_4_4_3": 5731, "5_4_3_2_2": 4390,
    "5_3_3_3_2": 494, "5_3_2_2_2_2": 694, "4_4_4_4": 38339,
    "4_4_4_2_2": 57226, "4_4_3_3_2": 12296, "4_4_2_2_2_2": 18376,
    "4_3_3_3_3": 1046, "4_3_3_2_2_2": 4734, "4_2_2_2_2_2_2": 2571,
    "3_3_3_3_2_2": 419, "3_3_2_2_2_2_2": 553, "2_2_2_2_2_2_2_2": 194,
}

EXPECTED_S15 = 159129
EXPECTED_FPF = sum(EXPECTED.values())  # 527036
EXPECTED_TOTAL = EXPECTED_S15 + EXPECTED_FPF  # 686165


def format_gen(img_list):
    """Format a single generator as GAP list string."""
    return "[ " + ", ".join(str(x) for x in img_list) + " ]"


def format_group(gens):
    """Format a group (list of generators) as GAP list-of-lists string."""
    gen_strs = [format_gen(g) for g in gens]
    if len(gen_strs) == 1:
        return "  [ " + gen_strs[0] + " ]"
    # Multi-gen: first on same line as [, rest indented
    lines = ["  [ " + gen_strs[0] + ", "]
    for i, gs in enumerate(gen_strs[1:], 1):
        if i < len(gen_strs) - 1:
            lines.append("  " + gs + ", ")
        else:
            lines.append("  " + gs + " ]")
    return "\n".join(lines)


def cycle_notation_to_image_list(cycle_str, degree):
    """Convert '(1,2,3)(4,5)' to [2, 3, 1, 5, 4, 6, ..., degree]."""
    perm = list(range(1, degree + 1))  # identity
    for match in re.finditer(r'\(([^)]+)\)', cycle_str):
        cycle = [int(x.strip()) for x in match.group(1).split(',')]
        for i in range(len(cycle)):
            perm[cycle[i] - 1] = cycle[(i + 1) % len(cycle)]
    return perm


def parse_old_cycle_file(path, degree):
    """Parse old-format gen file with # Group headers and cycle notation.
    Returns list of groups, each a list of image-list generators."""
    with open(path, "r") as f:
        raw = f.read()

    # Split into groups by "# Group N" markers
    groups = []
    current_lines = []
    for line in raw.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# Group"):
            if current_lines:
                groups.append(" ".join(current_lines))
            current_lines = []
        elif stripped:
            current_lines.append(stripped)
    if current_lines:
        groups.append(" ".join(current_lines))

    result = []
    for group_text in groups:
        # Strip outer [ ]
        group_text = group_text.strip()
        if group_text.startswith("["):
            group_text = group_text[1:]
        if group_text.endswith("]"):
            group_text = group_text[:-1]
        group_text = group_text.strip()

        # Split by commas at depth 0 (generator separators)
        generators = []
        current = []
        depth = 0
        for ch in group_text:
            if ch == '(':
                depth += 1
                current.append(ch)
            elif ch == ')':
                depth -= 1
                current.append(ch)
            elif ch == ',' and depth == 0:
                gen_str = "".join(current).strip()
                if gen_str:
                    generators.append(gen_str)
                current = []
            else:
                current.append(ch)
        gen_str = "".join(current).strip()
        if gen_str:
            generators.append(gen_str)

        # Convert each generator from cycle notation to image list
        gens = []
        for gen in generators:
            gen = gen.strip()
            if gen:
                gens.append(cycle_notation_to_image_list(gen, degree))
        if gens:
            result.append(gens)

    return result


def read_image_list_gen_file(path):
    """Read a gen file in image-list format (GAP ListPerm).
    Returns list of groups, each a list of image-list generators."""
    with open(path, "r") as f:
        raw = f.read()

    # Join continuation lines (backslash at end)
    raw = raw.replace("\\\n", "")

    result = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            gens = ast.literal_eval(line)
        except (ValueError, SyntaxError):
            continue

        # Handle single generator (not wrapped in outer list)
        if gens and isinstance(gens[0], int):
            gens = [gens]

        result.append(gens)

    return result


def process_s15_file(s15_path, out_f):
    """Read S15 subgroups, extend to degree 16, write to output.
    Returns count of groups written."""
    # Regex: find each inner generator list's closing bracket
    # Matches "number ]" and inserts ", 16" before the ]
    extend_re = re.compile(r'(\d+)\s*\]')

    count = 0
    in_body = False
    lines_buf = []

    with open(s15_path, "r") as f:
        for line in f:
            stripped = line.rstrip('\n')

            # Skip header comments
            if stripped.lstrip().startswith('#'):
                continue

            # Detect start of list
            if not in_body:
                if stripped.strip() == 'return [':
                    in_body = True
                continue

            # Detect end of list
            if stripped.strip() == '];':
                break

            # Apply extension: replace "N ]" with "N, 16 ]"
            extended = extend_re.sub(r'\1, 16 ]', stripped)

            # Count groups by looking for group-closing patterns "] ]" or "] ],"
            # A group is closed when we see "] ]" at depth 2->1
            if '] ]' in extended:
                count += 1

            lines_buf.append(extended)

    # Write all S15 lines, ensuring trailing comma for continuation
    text = "\n".join(lines_buf)
    # The last group won't have a trailing comma; add one
    # Find the last "] ]" and ensure it's followed by ","
    last_close = text.rfind('] ]')
    if last_close >= 0:
        after = text[last_close + 3:]
        if not after.strip().startswith(','):
            text = text[:last_close + 3] + ',' + text[last_close + 3:]

    out_f.write(text)
    out_f.write('\n')
    return count


def main():
    t0 = time.time()
    print(f"Building S16 master file: {OUTPUT_FILE}")
    print(f"S15 source: {S15_FILE}")
    print(f"FPF sources: {FRESH_GENS} (fresh), {OLD_GENS} (old)")
    print()

    with open(OUTPUT_FILE, "w") as out_f:
        # Header
        out_f.write(f"# Conjugacy class representatives for S16\n")
        out_f.write(f"# Total: {EXPECTED_TOTAL} classes\n")
        out_f.write(f"# Computed: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        out_f.write(f"# S15 subgroups (fixing point 16): {EXPECTED_S15}\n")
        out_f.write(f"# FPF subgroups (no fixed points): {EXPECTED_FPF}\n")
        out_f.write("return [\n")

        # Part 1: S15 inherited groups (extended to degree 16)
        print("Processing S15 inherited groups...")
        s15_count = process_s15_file(S15_FILE, out_f)
        print(f"  S15 groups written: {s15_count:,}")
        if s15_count != EXPECTED_S15:
            print(f"  WARNING: expected {EXPECTED_S15:,}, got {s15_count:,}")

        # Part 2: FPF groups from gen files
        print("\nProcessing FPF partition gen files...")
        fpf_total = 0
        all_parts = sorted(EXPECTED.keys(),
                          key=lambda k: tuple(int(x) for x in k.split("_")),
                          reverse=True)

        for pi, part_key in enumerate(all_parts):
            # Choose source
            if part_key in USE_OLD:
                source_dir = OLD_GENS
                source_label = "old"
            else:
                source_dir = FRESH_GENS
                source_label = "fresh"

            src_file = os.path.join(source_dir, f"gens_{part_key}.txt")
            expected = EXPECTED[part_key]

            # Detect format and parse
            is_cycle_format = False
            with open(src_file, "r") as f:
                first_line = ""
                for line in f:
                    first_line = line.strip()
                    if first_line:
                        break
                is_cycle_format = first_line.startswith("# Group")

            if is_cycle_format:
                groups = parse_old_cycle_file(src_file, DEGREE)
            else:
                groups = read_image_list_gen_file(src_file)

            n = len(groups)
            part_str = "[" + part_key.replace("_", ",") + "]"
            status = "OK" if n == expected else f"MISMATCH (got {n})"
            print(f"  {part_str:>22s}  {source_label:>5s}  {n:>7,d} / {expected:>7,d}  {status}")

            if n != expected:
                print(f"    WARNING: count mismatch!")

            # Write groups
            is_last_partition = (pi == len(all_parts) - 1)
            for gi, gens in enumerate(groups):
                is_last_group = is_last_partition and (gi == n - 1)
                group_str = format_group(gens)
                if is_last_group:
                    out_f.write(group_str + "\n")
                else:
                    out_f.write(group_str + ",\n")

            fpf_total += n

        out_f.write("];\n")

    elapsed = time.time() - t0
    total = s15_count + fpf_total

    print(f"\n{'='*60}")
    print(f"S15 inherited:  {s15_count:>10,d}  (expected {EXPECTED_S15:,})")
    print(f"FPF groups:     {fpf_total:>10,d}  (expected {EXPECTED_FPF:,})")
    print(f"Total:          {total:>10,d}  (expected {EXPECTED_TOTAL:,})")
    print(f"Time:           {elapsed:.1f}s")

    # File size
    size = os.path.getsize(OUTPUT_FILE)
    if size > 1024*1024:
        print(f"File size:      {size/1024/1024:.1f} MB")
    else:
        print(f"File size:      {size/1024:.1f} KB")

    if total == EXPECTED_TOTAL:
        print(f"\nSUCCESS: {OUTPUT_FILE}")
    else:
        print(f"\nERROR: total mismatch!")
        sys.exit(1)


if __name__ == "__main__":
    main()
