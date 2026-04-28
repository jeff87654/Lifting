"""
Fast comparison: run [6,6,3] twice with per-combo logging.
Run 1: USE_H1_ORBITAL := true (expected: 3246)
Run 2: USE_H1_ORBITAL := false (expected: 3248)
Compare per-combo "new" counts to identify divergent combos.
"""

import subprocess
import os
import time
import re

def run_gap(variant, log_file):
    """Run [6,6,3] with orbital enabled or disabled."""
    if variant == "orbital":
        setting = "USE_H1_ORBITAL := true;"
    else:
        setting = "USE_H1_ORBITAL := false;"

    gap_commands = f'''
LogTo("{log_file}");
{setting}
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Print("\\nORBITAL = ", USE_H1_ORBITAL, "\\n");
Print("Start: ", Runtime(), "\\n");
result := FindFPFClassesForPartition(15, [6,6,3]);
Print("\\nResult: ", Length(result), "\\n");
Print("End: ", Runtime(), "\\n");
LogTo();
QUIT;
'''

    script_file = f"C:/Users/jeffr/Downloads/Lifting/temp_663_{variant}.g"
    with open(script_file.replace("/", os.sep), "w") as f:
        f.write(gap_commands)

    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_663_{variant}.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    print(f"Starting {variant} at {time.strftime('%H:%M:%S')}")
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=env, cwd=gap_runtime
    )
    stdout, stderr = process.communicate(timeout=7200)
    print(f"  {variant} finished at {time.strftime('%H:%M:%S')}, rc={process.returncode}")
    if stderr and len(stderr.strip()) > 0:
        print(f"  STDERR: {stderr[:300]}")

def parse_combos(log_file):
    """Extract per-combo data: combo name and 'new' count."""
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()

    lines = log.split('\n')
    combos = []
    current_combo = None

    for line in lines:
        stripped = line.strip()
        if '>> combo' in stripped:
            current_combo = stripped
        elif 'combo:' in stripped and 'new' in stripped and current_combo is not None:
            # Parse "combo: X candidates -> Y new (Z total)"
            m = re.search(r'(\d+) candidates -> (\d+) new \((\d+) total\)', stripped)
            if m:
                combos.append({
                    'name': current_combo,
                    'candidates': int(m.group(1)),
                    'new': int(m.group(2)),
                    'total': int(m.group(3))
                })
            current_combo = None

    # Extract final result
    result_match = re.search(r'Result:\s*(\d+)', log)
    result = int(result_match.group(1)) if result_match else None

    return combos, result

# Run both variants sequentially
log_orbital = "C:/Users/jeffr/Downloads/Lifting/663_orb.log"
log_no_orbital = "C:/Users/jeffr/Downloads/Lifting/663_no_orb.log"

print("=== [6,6,3] Orbital Comparison ===")
print(f"Start: {time.strftime('%H:%M:%S')}")

run_gap("orbital", log_orbital)
run_gap("no_orbital", log_no_orbital)

# Parse and compare
print("\n=== Parsing results ===")
orb_combos, orb_result = parse_combos(log_orbital)
no_orb_combos, no_orb_result = parse_combos(log_no_orbital)

print(f"Orbital:    {len(orb_combos)} combos, result={orb_result}")
print(f"No-orbital: {len(no_orb_combos)} combos, result={no_orb_result}")

if orb_result is not None and no_orb_result is not None:
    print(f"Difference: {no_orb_result - orb_result}")

# Compare per-combo "new" counts
print("\n=== Per-combo comparison ===")
divergences = []
min_len = min(len(orb_combos), len(no_orb_combos))

for i in range(min_len):
    o = orb_combos[i]
    n = no_orb_combos[i]

    if o['new'] != n['new']:
        divergences.append((i, o, n))

if len(orb_combos) != len(no_orb_combos):
    print(f"WARNING: Different number of combos! {len(orb_combos)} vs {len(no_orb_combos)}")

if divergences:
    print(f"\n{len(divergences)} combos with different 'new' counts:")
    for idx, o, n in divergences:
        diff = n['new'] - o['new']
        print(f"  Combo {idx}: orbital_new={o['new']} no_orbital_new={n['new']} ({diff:+d})")
        print(f"    orbital:    {o['name']}")
        print(f"    no_orbital: {n['name']}")
        print(f"    candidates: {o['candidates']} vs {n['candidates']}")
else:
    print("No divergences in per-combo 'new' counts!")
    print("This means the difference comes from:")
    print("  - Different number of combos processed, OR")
    print("  - The difference is within candidate counts (pre-dedup), not post-dedup")

# Also compare candidate counts
cand_divergences = []
for i in range(min_len):
    o = orb_combos[i]
    n = no_orb_combos[i]
    if o['candidates'] != n['candidates']:
        cand_divergences.append((i, o, n))

if cand_divergences:
    print(f"\n{len(cand_divergences)} combos with different 'candidates' counts:")
    for idx, o, n in cand_divergences[:20]:  # Show first 20
        diff = n['candidates'] - o['candidates']
        print(f"  Combo {idx}: orbital_cand={o['candidates']} no_orbital_cand={n['candidates']} ({diff:+d})")
        print(f"    {o['name']}")

print(f"\nFinished at {time.strftime('%H:%M:%S')}")
