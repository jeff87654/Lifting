"""
Build S17 conjugacy cache by combining:
  - 686,165 S16 groups (extended from 16 to 17 points by appending fixed point 17)
  - 780,193 S17 FPF groups from parallel_s17/gens/*.txt (already on 17 points)
Total: 1,466,358 = OEIS A000638(17)
"""
import os
import re
import glob
import ast

S16_FILE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache\s16_subgroups.g"
GENS_DIR = r"C:\Users\jeffr\Downloads\Lifting\parallel_s17\gens"
OUT_FILE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache\s17_subgroups.g"

def parse_s16_and_write(out):
    """Parse s16_subgroups.g, extend each generator to 17 points, write to out."""
    count = 0
    with open(S16_FILE, "r") as f:
        # Buffer for multi-line entries
        buf = ""
        in_data = False
        for line in f:
            stripped = line.strip()
            # Skip comments and blank lines before data
            if not in_data:
                if stripped.startswith("return ["):
                    in_data = True
                continue
            # End of data
            if stripped == "];":
                break
            # Accumulate lines into buffer
            buf += line.rstrip("\n").rstrip("\r")
            # Check if this completes an entry (balanced brackets)
            # An entry starts with [ and ends with ], or ],
            if buf.strip():
                # Count brackets to see if balanced
                opens = buf.count("[")
                closes = buf.count("]")
                if opens > 0 and opens == closes:
                    # Extract the entry - strip trailing comma
                    entry_str = buf.strip()
                    if entry_str.endswith(","):
                        entry_str = entry_str[:-1]
                    # Parse as Python list of lists
                    try:
                        gens = ast.literal_eval(entry_str)
                    except:
                        print(f"  WARN: Could not parse S16 entry at count={count}: {entry_str[:80]}...")
                        buf = ""
                        continue
                    # Extend each generator from 16 to 17 points
                    extended_gens = []
                    for g in gens:
                        extended_gens.append(g + [17])
                    # Write
                    if count > 0:
                        out.write(",\n")
                    out.write("  " + repr(extended_gens).replace(" ", ""))
                    count += 1
                    if count % 100000 == 0:
                        print(f"  S16: {count} groups written")
                    buf = ""
    print(f"  S16 total: {count} groups (extended to 17 points)")
    return count


def parse_gens_files_and_write(out, s16_count):
    """Parse all gens_*.txt files and append to output."""
    gens_files = sorted(glob.glob(os.path.join(GENS_DIR, "gens_*.txt")))
    # Exclude .bak files
    gens_files = [f for f in gens_files if not f.endswith(".bak")]

    total = 0
    for gf in gens_files:
        fname = os.path.basename(gf)
        count = 0
        with open(gf, "r") as f:
            buf = ""
            for line in f:
                line = line.rstrip("\n").rstrip("\r")
                # Check for backslash continuation
                if line.endswith("\\"):
                    buf += line[:-1]
                else:
                    buf += line
                    if buf.strip() and buf.strip()[0] == "[":
                        try:
                            gens = ast.literal_eval(buf.strip())
                        except:
                            print(f"  WARN: Could not parse in {fname}: {buf[:80]}...")
                            buf = ""
                            continue
                        out.write(",\n")
                        out.write("  " + repr(gens).replace(" ", ""))
                        count += 1
                    buf = ""
        total += count
        print(f"  {fname}: {count} groups")
    print(f"  FPF total: {total} groups")
    return total


def main():
    print(f"Building S17 conjugacy cache...")
    print(f"  S16 source: {S16_FILE}")
    print(f"  FPF source: {GENS_DIR}")
    print(f"  Output: {OUT_FILE}")

    with open(OUT_FILE, "w") as out:
        out.write("# Conjugacy class representatives for S17\n")
        out.write("# Total: 1466358 classes\n")
        out.write("# S16 groups (686165) extended to 17 points + S17 FPF groups (780193)\n")
        out.write("# Sorted: S16 inherited first, then FPF by partition\n")
        out.write("return [\n")

        s16_count = parse_s16_and_write(out)
        fpf_count = parse_gens_files_and_write(out, s16_count)

        out.write("\n];\n")

    grand_total = s16_count + fpf_count
    print(f"\nDone! Total: {grand_total} ({s16_count} S16 + {fpf_count} FPF)")
    if grand_total == 1466358:
        print("VERIFIED: matches OEIS A000638(17) = 1,466,358")
    else:
        print(f"WARNING: expected 1,466,358, got {grand_total}")
        print(f"  S16 expected: 686,165, got: {s16_count}")
        print(f"  FPF expected: 780,193, got: {fpf_count}")


if __name__ == "__main__":
    main()
