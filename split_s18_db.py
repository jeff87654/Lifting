"""
Split s18_subgroups_cycles.g and s18_origin_combos.g into 8 parts each
(~909K entries per part, similar size to the S17 cycles file that loads OK).
Provide a master loader script.
"""
import os

CACHE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache"
NPARTS = 8
TOTAL = 7274651

CYCLES = os.path.join(CACHE, "s18_subgroups_cycles.g")
ORIGINS = os.path.join(CACHE, "s18_origin_combos.g")

def split_file(src, prefix, total, nparts):
    chunk_size = (total + nparts - 1) // nparts
    print(f"\nSplitting {os.path.basename(src)}")
    print(f"  total entries: {total}")
    print(f"  parts: {nparts}, chunk_size: ~{chunk_size}")

    out_files = [open(os.path.join(CACHE, f"{prefix}_part{i+1}.g"),
                       "w", encoding="utf-8") for i in range(nparts)]
    for i, fh in enumerate(out_files):
        fh.write(f"# {prefix} part {i+1} of {nparts}\n")
        fh.write(f"return [\n")

    written = [0] * nparts
    cur_part = 0

    with open(src) as fin:
        for line in fin:
            if not line.startswith("  ["):
                continue
            # Move to next part if this one is full
            while cur_part < nparts - 1 and written[cur_part] >= chunk_size:
                cur_part += 1
            out_files[cur_part].write(line)
            written[cur_part] += 1

    for i, fh in enumerate(out_files):
        fh.write("];\n")
        fh.close()
        size = os.path.getsize(os.path.join(CACHE, f"{prefix}_part{i+1}.g"))
        print(f"  part {i+1}: {written[i]:,} entries ({size:,} bytes)")
    print(f"  total written: {sum(written):,}  (expected {total})")

split_file(CYCLES, "s18_subgroups_cycles", TOTAL, NPARTS)
split_file(ORIGINS, "s18_origin_combos", TOTAL, NPARTS)

# Master loader for cycles
loader_path = os.path.join(CACHE, "s18_load.g")
with open(loader_path, "w", encoding="utf-8") as f:
    f.write("###############################################################################\n")
    f.write(f"# Loader for the S18 subgroup database (split into {NPARTS} parts).\n")
    f.write("# Reads both s18_subgroups_cycles_partN.g and s18_origin_combos_partN.g\n")
    f.write("# and binds GROUPS / ORIGINS globals.\n")
    f.write("###############################################################################\n")
    f.write('CACHE := "C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache";\n')
    f.write("\nGROUPS := [];\nORIGINS := [];\n")
    f.write(f"for i in [1..{NPARTS}] do\n")
    f.write(f'    Print("  loading cycles part ", i, "/", {NPARTS}, "\\n");\n')
    f.write('    Append(GROUPS, ReadAsFunction(Concatenation(CACHE,\n')
    f.write('        "/s18_subgroups_cycles_part", String(i), ".g"))());\n')
    f.write(f'    Print("  loading origins part ", i, "/", {NPARTS}, "\\n");\n')
    f.write('    Append(ORIGINS, ReadAsFunction(Concatenation(CACHE,\n')
    f.write('        "/s18_origin_combos_part", String(i), ".g"))());\n')
    f.write("od;\n")
    f.write('Print("Loaded ", Length(GROUPS), " groups, ",\n')
    f.write('      Length(ORIGINS), " origins\\n");\n')

print(f"\nLoader: {loader_path}")
