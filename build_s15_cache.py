"""Build S15 conjugacy class cache by combining S14 subgroups + all FPF partition results."""
import os
import subprocess
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GENS_DIR = os.path.join(LIFTING_DIR, "parallel_s15", "gens")
CACHE_DIR = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache"

# All FPF partitions of 15 (no 1-parts)
FPF_PARTITIONS = [
    [15], [13,2], [12,3], [11,4], [11,2,2], [10,5], [10,3,2],
    [9,6], [9,4,2], [9,3,3], [9,2,2,2],
    [8,7], [8,5,2], [8,4,3], [8,3,2,2],
    [7,6,2], [7,5,3], [7,4,4], [7,4,2,2], [7,3,3,2], [7,2,2,2,2],
    [6,6,3], [6,5,4], [6,5,2,2], [6,4,3,2], [6,3,3,3], [6,3,2,2,2],
    [5,5,5], [5,5,3,2], [5,4,4,2], [5,4,3,3], [5,4,2,2,2], [5,3,3,2,2], [5,2,2,2,2,2],
    [4,4,4,3], [4,4,3,2,2], [4,3,3,3,2], [4,3,2,2,2,2],
    [3,3,3,3,3], [3,3,3,2,2,2], [3,2,2,2,2,2,2],
]

# For these two partitions, use the orbital OFF results
ORBITAL_OFF = {
    "5_4_4_2": "gens_5_4_4_2_orbital_off.txt",
    "6_6_3": "gens_6_6_3_orbital_off.txt",
}

def partition_to_underscore(p):
    return "_".join(str(x) for x in p)

def count_entries(filepath):
    """Count groups in a gens file (entries starting with '[')."""
    if not os.path.exists(filepath):
        return 0
    count = 0
    with open(filepath) as f:
        for line in f:
            if line.strip().startswith('['):
                count += 1
    return count

def preprocess_gens_file(filepath):
    """Read gens file, join continuation lines, return list of entry strings."""
    with open(filepath) as f:
        content = f.read()
    # Remove backslash-newline continuations (GAP line wrapping)
    content = content.replace('\\\n', '')
    lines = content.split('\n')
    entries = []
    current = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                entries.append(current)
                current = ""
            continue
        if stripped.startswith('[') and current:
            entries.append(current)
            current = stripped
        elif stripped.startswith('['):
            current = stripped
        else:
            current += " " + stripped
    if current:
        entries.append(current)
    return entries

# Step 1: Preprocess all FPF gens files into one GAP-readable file
print("Preprocessing FPF gens files...")
all_fpf_file = os.path.join(LIFTING_DIR, "temp_all_fpf_groups.g")
total_fpf = 0

with open(all_fpf_file, "w") as f:
    f.write("_ALL_FPF_GROUPS := [\n")
    first = True
    for partition in FPF_PARTITIONS:
        key = partition_to_underscore(partition)
        # Use orbital OFF version for affected partitions
        if key in ORBITAL_OFF:
            gens_file = os.path.join(GENS_DIR, ORBITAL_OFF[key])
        else:
            gens_file = os.path.join(GENS_DIR, f"gens_{key}.txt")

        if not os.path.exists(gens_file):
            print(f"  WARNING: Missing {gens_file}")
            continue

        entries = preprocess_gens_file(gens_file)
        print(f"  {partition}: {len(entries)} groups (from {os.path.basename(gens_file)})")
        total_fpf += len(entries)

        for entry in entries:
            if not first:
                f.write(",\n")
            first = False
            inner = entry.strip()
            # Detect format: image lists "[ [1,2,...], [3,4,...] ]" vs cycle notation "[ (1,2,3), (4,5) ]"
            if '(' in inner:
                # Cycle notation - strip outer brackets, use directly
                if inner.startswith('['):
                    inner = inner[1:]
                if inner.endswith(']'):
                    inner = inner[:-1]
                inner = inner.strip()
                f.write(f"  Group({inner})")
            else:
                # Image lists - need PermList() on each inner list
                # Entry is like "[ [2,3,...,1], [14,13,...] ]"
                # Write as Group(PermList([2,3,...,1]), PermList([14,13,...]))
                if inner.startswith('['):
                    inner = inner[1:]
                if inner.endswith(']'):
                    inner = inner[:-1]
                inner = inner.strip()
                # Split on "], [" to get individual image lists
                # Rejoin with PermList() wrapping
                import re
                lists = re.split(r'\]\s*,\s*\[', inner)
                perm_args = []
                for lst in lists:
                    lst = lst.strip().strip('[]').strip()
                    if lst:
                        perm_args.append(f"PermList([{lst}])")
                if perm_args:
                    f.write(f"  Group({', '.join(perm_args)})")
                else:
                    f.write(f"  Group(())")

    f.write("\n];\n")

print(f"\nTotal FPF groups: {total_fpf}")
print(f"Wrote {all_fpf_file}")

# Step 2: GAP script to combine S14 + FPF and save
log_file = "C:/Users/jeffr/Downloads/Lifting/gap_build_s15_cache.log"
output_file = "C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache/s15_subgroups.g"

gap_commands = f'''
LogTo("{log_file}");

# Load S14 subgroups
Print("Loading S14 subgroups...\\n");
s14_gens_list := ReadAsFunction("C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache/s14_subgroups.g")();
Print("S14 subgroups: ", Length(s14_gens_list), "\\n");

# Extend S14 generators to degree 15 (each fixes point 15)
Print("Extending S14 generators to degree 15...\\n");
s14_groups := [];
for gens_images in s14_gens_list do
    extended_gens := [];
    for img in gens_images do
        # img is an image list of length 14, append 15
        Add(extended_gens, PermList(Concatenation(img, [15])));
    od;
    if Length(extended_gens) > 0 then
        Add(s14_groups, Group(extended_gens));
    else
        Add(s14_groups, Group(()));
    fi;
od;
Print("S14 groups extended: ", Length(s14_groups), "\\n");

# Load FPF groups
Print("Loading FPF groups...\\n");
Read("C:/Users/jeffr/Downloads/Lifting/temp_all_fpf_groups.g");
fpf_groups := _ALL_FPF_GROUPS;
Print("FPF groups: ", Length(fpf_groups), "\\n");

# Combine
all_groups := Concatenation(s14_groups, fpf_groups);
Print("Total S15 groups: ", Length(all_groups), "\\n");
Print("Expected: 159129\\n");

if Length(all_groups) <> 159129 then
    Print("WARNING: Count mismatch! Got ", Length(all_groups), " expected 159129\\n");
fi;

# Save as image lists (same format as S14 cache)
Print("Writing S15 cache...\\n");
fname := "{output_file}";
PrintTo(fname, "# Conjugacy class representatives for S15\\n");
AppendTo(fname, "# Total: ", Length(all_groups), " classes\\n");
AppendTo(fname, "# Computed: {time.strftime('%Y-%m-%d %H:%M:%S')}\\n");
AppendTo(fname, "# S14 subgroups (fixing point 15): ", Length(s14_groups), "\\n");
AppendTo(fname, "# FPF subgroups (no fixed points): ", Length(fpf_groups), "\\n");
AppendTo(fname, "return [\\n");
for i in [1..Length(all_groups)] do
    G := all_groups[i];
    gens := GeneratorsOfGroup(G);
    gen_images := List(gens, g -> ListPerm(g, 15));
    AppendTo(fname, "  ", gen_images);
    if i < Length(all_groups) then
        AppendTo(fname, ",\\n");
    else
        AppendTo(fname, "\\n");
    fi;
    if i mod 10000 = 0 then
        Print("  written ", i, "/", Length(all_groups), "\\n");
    fi;
od;
AppendTo(fname, "];\\n");
Print("Done. Saved to ", fname, "\\n");

LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_build_s15_cache.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_build_s15_cache.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"\nStarting GAP at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=14400)
print(f"GAP finished at {time.strftime('%H:%M:%S')}")

if stderr.strip():
    err_lines = [l for l in stderr.split('\n') if 'Error' in l]
    if err_lines:
        print(f"ERRORS:\n" + "\n".join(err_lines[:10]))

with open(log_file.replace("/", os.sep), "r") as f:
    log = f.read()
print(log[-3000:] if len(log) > 3000 else log)
