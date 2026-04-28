"""
Convert s17_subgroups.g from image-list notation to cycle notation.
[[2,1,4,3,...]] -> [ (1,2)(3,4)... ]
"""
import ast

S17_FILE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache\s17_subgroups.g"
OUT_FILE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache\s17_subgroups_cycles.g"


def image_list_to_cycles(img):
    """Convert image list [2,1,4,3,...] to GAP cycle string '(1,2)(3,4)'."""
    n = len(img)
    seen = [False] * (n + 1)
    cycles = []
    for i in range(1, n + 1):
        if seen[i] or img[i - 1] == i:
            continue
        cycle = [i]
        seen[i] = True
        j = img[i - 1]
        while j != i:
            cycle.append(j)
            seen[j] = True
            j = img[j - 1]
        if len(cycle) > 1:
            cycles.append("(" + ",".join(str(x) for x in cycle) + ")")
    if not cycles:
        return "()"
    return "".join(cycles)


def main():
    count = 0
    with open(S17_FILE, "r") as fin, open(OUT_FILE, "w") as fout:
        fout.write("# Conjugacy class representatives for S17 (cycle notation)\n")
        fout.write("# Total: 1466358 classes\n")
        fout.write("# S16 groups (686165) extended to 17 points + S17 FPF groups (780193)\n")
        fout.write("return [\n")

        buf = ""
        in_data = False
        for line in fin:
            stripped = line.strip()
            if not in_data:
                if stripped.startswith("return ["):
                    in_data = True
                continue
            if stripped == "];":
                break
            buf += line.rstrip("\n").rstrip("\r")
            if buf.strip():
                opens = buf.count("[")
                closes = buf.count("]")
                if opens > 0 and opens == closes:
                    entry_str = buf.strip()
                    if entry_str.endswith(","):
                        entry_str = entry_str[:-1]
                    try:
                        gens = ast.literal_eval(entry_str)
                    except:
                        print(f"  WARN: parse error at {count}: {entry_str[:80]}...")
                        buf = ""
                        continue
                    cycle_strs = [image_list_to_cycles(g) for g in gens]
                    if count > 0:
                        fout.write(",\n")
                    fout.write("  [ " + ", ".join(cycle_strs) + " ]")
                    count += 1
                    if count % 200000 == 0:
                        print(f"  {count} groups converted...")
                    buf = ""

        fout.write("\n];\n")

    print(f"Done! {count} groups converted to cycle notation.")
    print(f"Output: {OUT_FILE}")


if __name__ == "__main__":
    main()
