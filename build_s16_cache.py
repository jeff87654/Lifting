###############################################################################
# build_s16_cache.py - Assemble S16 conjugacy class cache
#
# Combines:
#   1. S15 subgroups from s15_subgroups.g (extended to degree 16)
#   2. FPF subgroups from parallel_s16/gens/ directory
# into s16_subgroups.g in the conjugacy_cache directory.
#
# Also optionally merges new FPF_SUBDIRECT_CACHE entries from workers.
#
# Usage:
#   python build_s16_cache.py                          # Build cache via GAP
#   python build_s16_cache.py --verify                 # Verify counts only
#   python build_s16_cache.py --python-only            # Pure Python (no GAP)
#
###############################################################################

import os
import sys
import re
import ast
import time
import subprocess
import datetime
import argparse
from pathlib import Path

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
CACHE_DIR = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16")
GENS_DIR = os.path.join(OUTPUT_DIR, "gens")

GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

N = 16
INHERITED_FROM_S15 = 159129

# All FPF partitions of 16 (no 1-parts)
FPF_PARTITIONS = None  # Will be computed


def partitions_min_part(n, min_part=2):
    """Generate all partitions of n with all parts >= min_part."""
    result = []
    def helper(remaining, max_part, current):
        if remaining == 0:
            result.append(list(current))
            return
        for i in range(min(remaining, max_part), min_part - 1, -1):
            current.append(i)
            helper(remaining - i, i, current)
            current.pop()
    helper(n, n, [])
    return result


def partition_to_underscore(p):
    return "_".join(str(x) for x in p)


def count_entries(filepath):
    """Count groups in a gens file (entries starting with '[')."""
    if not os.path.exists(filepath):
        return 0
    count = 0
    with open(filepath) as f:
        for line in f:
            if line.strip().startswith("["):
                count += 1
    return count


def preprocess_gens_file(filepath):
    """Read gens file, join continuation lines, return list of entry strings."""
    with open(filepath) as f:
        content = f.read()
    # Remove backslash-newline continuations (GAP line wrapping)
    content = content.replace("\\\n", "")
    lines = content.split("\n")
    entries = []
    current = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                entries.append(current)
                current = ""
            continue
        if stripped.startswith("[") and current:
            entries.append(current)
            current = stripped
        elif stripped.startswith("["):
            current = stripped
        else:
            current += " " + stripped
    if current:
        entries.append(current)
    return entries


def verify_counts():
    """Verify that all partition gens files exist and count subgroups."""
    partitions = partitions_min_part(N)
    print(f"Verifying {len(partitions)} FPF partitions of {N}...\n")

    total_fpf = 0
    missing = []

    for partition in partitions:
        key = partition_to_underscore(partition)
        gens_file = os.path.join(GENS_DIR, f"gens_{key}.txt")

        if not os.path.exists(gens_file):
            missing.append(partition)
            print(f"  MISSING: {partition}")
            continue

        entries = preprocess_gens_file(gens_file)
        total_fpf += len(entries)
        print(f"  {str(partition):30s}: {len(entries):6d} groups")

    print(f"\n{'='*50}")
    print(f"Total FPF: {total_fpf}")
    print(f"Inherited: {INHERITED_FROM_S15}")
    print(f"Grand total: {INHERITED_FROM_S15 + total_fpf}")

    if missing:
        print(f"\nWARNING: {len(missing)} partitions missing!")
        for p in missing:
            print(f"  {p}")
    else:
        print(f"\nAll {len(partitions)} partition files present.")

    return total_fpf, missing


def build_via_gap():
    """Build s16_subgroups.g using GAP for reliable parsing and combination."""
    partitions = partitions_min_part(N)

    # Step 1: Preprocess all FPF gens files into one GAP-readable file
    print("Step 1: Preprocessing FPF gens files...")
    all_fpf_file = os.path.join(LIFTING_DIR, "temp_all_fpf_groups_s16.g")
    total_fpf = 0

    with open(all_fpf_file, "w") as f:
        f.write("_ALL_FPF_GROUPS := [\n")
        first = True
        for partition in partitions:
            key = partition_to_underscore(partition)
            gens_file = os.path.join(GENS_DIR, f"gens_{key}.txt")

            if not os.path.exists(gens_file):
                print(f"  WARNING: Missing {gens_file}")
                continue

            entries = preprocess_gens_file(gens_file)
            print(f"  {partition}: {len(entries)} groups")
            total_fpf += len(entries)

            for entry in entries:
                if not first:
                    f.write(",\n")
                first = False
                inner = entry.strip()
                # Image lists format: "[ [1,2,...], [3,4,...] ]"
                if "(" in inner:
                    # Cycle notation
                    if inner.startswith("["):
                        inner = inner[1:]
                    if inner.endswith("]"):
                        inner = inner[:-1]
                    inner = inner.strip()
                    f.write(f"  Group({inner})")
                else:
                    # Image lists
                    if inner.startswith("["):
                        inner = inner[1:]
                    if inner.endswith("]"):
                        inner = inner[:-1]
                    inner = inner.strip()
                    lists = re.split(r"\]\s*,\s*\[", inner)
                    perm_args = []
                    for lst in lists:
                        lst = lst.strip().strip("[]").strip()
                        if lst:
                            perm_args.append(f"PermList([{lst}])")
                    if perm_args:
                        f.write(f"  Group({', '.join(perm_args)})")
                    else:
                        f.write(f"  Group(())")

        f.write("\n];\n")

    print(f"\nTotal FPF groups: {total_fpf}")
    print(f"Wrote {all_fpf_file}")

    # Step 2: GAP script to combine S15 + FPF and save
    log_file = "C:/Users/jeffr/Downloads/Lifting/gap_build_s16_cache.log"
    output_file = "C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache/s16_subgroups.g"

    gap_commands = f'''
LogTo("{log_file}");

# Load S15 subgroups
Print("Loading S15 subgroups...\\n");
s15_gens_list := ReadAsFunction("C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache/s15_subgroups.g")();
Print("S15 subgroups: ", Length(s15_gens_list), "\\n");

# Extend S15 generators to degree 16 (each fixes point 16)
Print("Extending S15 generators to degree 16...\\n");
s15_groups := [];
for gens_images in s15_gens_list do
    extended_gens := [];
    for img in gens_images do
        # img is an image list of length 15, append 16
        Add(extended_gens, PermList(Concatenation(img, [{N}])));
    od;
    if Length(extended_gens) > 0 then
        Add(s15_groups, Group(extended_gens));
    else
        Add(s15_groups, Group(()));
    fi;
od;
Print("S15 groups extended: ", Length(s15_groups), "\\n");

# Load FPF groups
Print("Loading FPF groups...\\n");
Read("C:/Users/jeffr/Downloads/Lifting/temp_all_fpf_groups_s16.g");
fpf_groups := _ALL_FPF_GROUPS;
Print("FPF groups: ", Length(fpf_groups), "\\n");

# Combine
all_groups := Concatenation(s15_groups, fpf_groups);
Print("Total S{N} groups: ", Length(all_groups), "\\n");

# Save as image lists
Print("Writing S{N} cache...\\n");
fname := "{output_file}";
PrintTo(fname, "# Conjugacy class representatives for S{N}\\n");
AppendTo(fname, "# Total: ", Length(all_groups), " classes\\n");
AppendTo(fname, "# Computed: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n");
AppendTo(fname, "# S15 subgroups (fixing point {N}): ", Length(s15_groups), "\\n");
AppendTo(fname, "# FPF subgroups (no fixed points): ", Length(fpf_groups), "\\n");
AppendTo(fname, "return [\\n");
for i in [1..Length(all_groups)] do
    G := all_groups[i];
    gens := GeneratorsOfGroup(G);
    gen_images := List(gens, g -> ListPerm(g, {N}));
    AppendTo(fname, "  ", gen_images);
    if i < Length(all_groups) then
        AppendTo(fname, ",\\n");
    else
        AppendTo(fname, "\\n");
    fi;
    if i mod 20000 = 0 then
        Print("  written ", i, "/", Length(all_groups), "\\n");
    fi;
od;
AppendTo(fname, "];\\n");
Print("Done. Saved to ", fname, "\\n");

LogTo();
QUIT;
'''

    temp_gap = os.path.join(LIFTING_DIR, "temp_build_s16_cache.g")
    with open(temp_gap, "w") as f:
        f.write(gap_commands)

    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_build_s16_cache.g"

    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"

    print(f"\nStep 2: Starting GAP at {time.strftime('%H:%M:%S')}")
    print("  This may take a while for large files...")
    process = subprocess.Popen(
        [BASH_EXE, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
         f'./gap.exe -q "{script_path}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=env, cwd=GAP_RUNTIME,
    )
    stdout, stderr = process.communicate(timeout=21600)  # 6 hour timeout
    print(f"GAP finished at {time.strftime('%H:%M:%S')}")

    if stderr.strip():
        err_lines = [l for l in stderr.split("\n") if "Error" in l]
        if err_lines:
            print(f"ERRORS:\n" + "\n".join(err_lines[:10]))

    log_path = log_file.replace("/", os.sep)
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            log = f.read()
        print(log[-3000:] if len(log) > 3000 else log)
    else:
        print("WARNING: Log file not found")

    output_path = output_file.replace("/", os.sep)
    if os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / 1024 / 1024
        print(f"\nOutput file: {output_path}")
        print(f"  Size: {size_mb:.1f} MB")
    else:
        print("WARNING: Output file not created!")


def build_python_only():
    """Build s16_subgroups.g using pure Python (no GAP dependency).

    Writes generators as image lists directly. This is faster for assembly
    but less robust than GAP parsing for edge cases.
    """
    from run_s16 import parse_inherited_chunked, parse_partition_gens, write_subgroups_file

    s15_file = os.path.join(CACHE_DIR, "s15_subgroups.g")
    s16_file = os.path.join(CACHE_DIR, "s16_subgroups.g")

    print(f"Building {s16_file} (Python-only mode)...")

    # Parse inherited S15 classes
    print(f"\n  Parsing S15 subgroups from {s15_file}...")
    inherited = parse_inherited_chunked(s15_file, 15)
    print(f"  Loaded {len(inherited)} inherited classes")

    if len(inherited) != INHERITED_FROM_S15:
        print(f"  WARNING: Expected {INHERITED_FROM_S15}, got {len(inherited)}")

    # Extend to degree 16
    print(f"  Extending to degree {N}...")
    for sg in inherited:
        for gen in sg:
            gen.append(N)

    # Parse FPF generators
    print(f"\n  Parsing FPF generators from {GENS_DIR}...")
    fpf = parse_partition_gens(GENS_DIR)
    print(f"  Loaded {len(fpf)} FPF classes")

    # Combine
    all_subgroups = inherited + fpf
    total = len(all_subgroups)
    print(f"\n  Total: {len(inherited)} + {len(fpf)} = {total}")

    # Write
    print(f"\n  Writing {s16_file}...")
    write_subgroups_file(s16_file, all_subgroups, N)

    size_mb = os.path.getsize(s16_file) / 1024 / 1024
    print(f"  Done! {s16_file} ({size_mb:.1f} MB)")

    return total


def update_lift_cache(total):
    """Print instructions for updating database/lift_cache.g."""
    cache_file = os.path.join(LIFTING_DIR, "database", "lift_cache.g")
    print(f"\nTo update {cache_file}, add the following line:")
    print(f'  LIFT_CACHE.("16") := {total};')
    print(f"\nOr run this command:")
    print(f'  echo \'LIFT_CACHE.("16") := {total};\' >> "{cache_file}"')


def main():
    parser = argparse.ArgumentParser(description="Build S16 conjugacy class cache")
    parser.add_argument("--verify", action="store_true",
                       help="Verify partition counts only (no building)")
    parser.add_argument("--python-only", action="store_true",
                       help="Build using pure Python (no GAP)")
    args = parser.parse_args()

    print(f"S{N} Cache Builder")
    print("=" * 60)

    if args.verify:
        total_fpf, missing = verify_counts()
        if not missing:
            update_lift_cache(INHERITED_FROM_S15 + total_fpf)
        return

    if args.python_only:
        total = build_python_only()
        update_lift_cache(total)
        return

    # Default: use GAP for reliable parsing
    # First verify all files exist
    total_fpf, missing = verify_counts()
    if missing:
        print(f"\nERROR: {len(missing)} partition files missing. Cannot build cache.")
        print("Run computation first or check for failed partitions.")
        sys.exit(1)

    build_via_gap()
    update_lift_cache(INHERITED_FROM_S15 + total_fpf)


if __name__ == "__main__":
    main()
