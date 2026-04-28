"""Check two things:
1. Are all S_n-signature combos inside the 12,479 affected_combos manifest?
2. Enumerate ALL TG(d, t) with d <= 18 and |group| in {120, 720, 5040, 40320}
   via GAP, to build a complete iso-S_n lookup table. Then rescan.
"""
import os, re, subprocess
from collections import defaultdict

ROOT = r"C:\Users\jeffr\Downloads\Lifting"
PREBUG = os.path.join(ROOT, "parallel_s18_prebugfix_backup")
MANIFEST = os.path.join(ROOT, "affected_combos.txt")

# Step 1: load manifest
with open(MANIFEST, "r") as f:
    manifest_combos = set(line.strip() for line in f if line.strip())
print(f"Manifest has {len(manifest_combos)} combos")
print()

# Step 1a: cross-check the 30 bug-signature combos against manifest
NATURAL_SN_TAGS = {(5, 5), (6, 16), (7, 7), (8, 50), (9, 34), (10, 45),
                   (11, 8), (12, 301), (13, 9), (14, 63), (15, 104),
                   (16, 1954), (17, 10)}

# Known non-natural iso-S_n from earlier scan
NON_NATURAL_SN_BY_ORDER_SHORT = {
    120: [(6, 11), (10, 12), (10, 13), (12, 75), (15, 10), (15, 11)],
    720: [(10, 32), (10, 34), (12, 268), (15, 14), (15, 18)],
    5040: [(14, 59), (14, 63), (15, 97), (15, 98), (15, 99)],
    40320: [(14, 62), (15, 104)],
}

ALL_NON_NATURAL_SN_BY_DEG = defaultdict(list)
for order, pairs in NON_NATURAL_SN_BY_ORDER_SHORT.items():
    n = {120: 5, 720: 6, 5040: 7, 40320: 8}[order]
    for d, t in pairs:
        ALL_NON_NATURAL_SN_BY_DEG[d].append((d, t, n))

def bug_signature(combo_filename, non_natural_table=ALL_NON_NATURAL_SN_BY_DEG):
    tags_raw = re.findall(r"\[(\d+),(\d+)\]", combo_filename)
    tags = [(int(d), int(t)) for d, t in tags_raw]
    if len(tags) < 3:
        return None
    naturals = [(i, tag) for i, tag in enumerate(tags) if tag in NATURAL_SN_TAGS]
    if not naturals:
        return None
    for i, (nd, nt) in naturals:
        n = nd
        for j, (d, t) in enumerate(tags):
            if j == i:
                continue
            for (cd, ct, cn) in non_natural_table.get(d, []):
                if ct == t and cn == n:
                    return (n, (nd, nt), (d, t))
    return None

# Collect bug-signature combos from prebugfix folder
affected = []
for part_dir in sorted(os.listdir(PREBUG)):
    d = os.path.join(PREBUG, part_dir)
    if not os.path.isdir(d): continue
    for combo_file in os.listdir(d):
        if not combo_file.endswith(".g"): continue
        sig = bug_signature(combo_file)
        if sig:
            affected.append((part_dir, combo_file, sig))

print(f"Bug-signature combos in prebugfix set: {len(affected)}")

# Check how many are in manifest
manifest_hits = 0
outside_manifest = []
for part, combo, _ in affected:
    combo_key = f"{part}/{combo}"
    if combo_key in manifest_combos:
        manifest_hits += 1
    else:
        outside_manifest.append((part, combo))

print(f"  In 12,479 manifest:   {manifest_hits}")
print(f"  Outside manifest:     {len(outside_manifest)}")
for p, c in outside_manifest[:10]:
    print(f"    {p}/{c}")
print()

# Step 2: enumerate ALL TG(d, t) with |group| == some_sn_order via GAP
# Build a complete lookup table.
print("Querying GAP for ALL TG(d, t) with |G| in {120, 720, 5040, 40320}, d <= 18...")
gap_script = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/tg_sn_enum.log");
for d in [5..18] do
    n := NrTransitiveGroups(d);
    for t in [1..n] do
        G := TransitiveGroup(d, t);
        sz := Size(G);
        if sz in [120, 720, 5040, 40320] then
            desc := StructureDescription(G);
            Print(d, "\\t", t, "\\t", sz, "\\t", desc, "\\n");
        fi;
    od;
od;
LogTo();
QUIT;
'''
with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_tg_sn_enum.g", "w") as f:
    f.write(gap_script)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_tg_sn_enum.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
p.wait(timeout=600)

sn_candidates = []  # (degree, t, size, desc)
with open(r"C:\Users\jeffr\Downloads\Lifting\tg_sn_enum.log") as f:
    for line in f:
        parts = line.strip().split("\t")
        if len(parts) == 4:
            try:
                sn_candidates.append((int(parts[0]), int(parts[1]),
                                       int(parts[2]), parts[3]))
            except ValueError:
                pass

# Filter: only those where desc confirms it's "S_n" (or iso)
iso_sn_tg = []  # (degree, t, S_n)
for d, t, sz, desc in sn_candidates:
    if desc == "S5":
        iso_sn_tg.append((d, t, 5))
    elif desc == "S6":
        iso_sn_tg.append((d, t, 6))
    elif desc == "S7":
        iso_sn_tg.append((d, t, 7))
    elif desc == "S8":
        iso_sn_tg.append((d, t, 8))
    # size-120/720/5040/40320 groups that are NOT S_n (e.g., A_5 x C_2, etc.)
    # are not isomorphic to S_n, so they don't trigger this bug.

print(f"Total TG(d,t) with S_n structure (d <= 18): {len(iso_sn_tg)}")
by_n = defaultdict(list)
for d, t, n in iso_sn_tg:
    by_n[n].append((d, t))
for n in sorted(by_n.keys()):
    print(f"  S_{n}: {by_n[n]}")
print()

# Build complete lookup: (degree, t) -> n_iso
EXHAUSTIVE_SN = defaultdict(list)
for d, t, n in iso_sn_tg:
    # Only include non-natural (i.e., (d, t) != (n, t_natural_S_n))
    if (d, t) not in NATURAL_SN_TAGS:
        EXHAUSTIVE_SN[d].append((d, t, n))

# Re-scan with complete table
print("Re-scanning with complete iso-S_n table...")
affected_complete = []
for part_dir in sorted(os.listdir(PREBUG)):
    d_ = os.path.join(PREBUG, part_dir)
    if not os.path.isdir(d_): continue
    for combo_file in os.listdir(d_):
        if not combo_file.endswith(".g"): continue
        sig = bug_signature(combo_file, EXHAUSTIVE_SN)
        if sig:
            affected_complete.append((part_dir, combo_file, sig))

print(f"Bug-signature combos (complete table): {len(affected_complete)}")

old_keys = set((p, c) for p, c, _ in affected)
new_keys = set((p, c) for p, c, _ in affected_complete)
newly_found = new_keys - old_keys
print(f"  New combos found by expanded table: {len(newly_found)}")
for p, c in list(newly_found)[:20]:
    print(f"    {p}/{c}")
if len(newly_found) > 20:
    print(f"    ... and {len(newly_found) - 20} more")
print()

# How many are outside manifest
outside_complete = []
for p, c, _ in affected_complete:
    if f"{p}/{c}" not in manifest_combos:
        outside_complete.append((p, c))
print(f"Bug-signature combos outside 12,479 manifest: {len(outside_complete)}")
for p, c in outside_complete[:20]:
    print(f"    {p}/{c}")
