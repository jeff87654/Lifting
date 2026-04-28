"""
Run [6,6,3] partition of S15 TWICE:
1. With orbital enabled (default)
2. With orbital disabled

Compare the per-combo counts to identify where the difference occurs.
"""

import subprocess
import os
import time

def run_gap_test(variant, log_file):
    """Run GAP with orbital enabled or disabled."""

    if variant == "orbital":
        orbital_setting = "USE_H1_ORBITAL := true;"
    else:
        orbital_setting = "USE_H1_ORBITAL := false;"

    gap_commands = f'''
LogTo("{log_file}");

# Set orbital BEFORE loading code
{orbital_setting}
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\nORBITAL SETTING: USE_H1_ORBITAL = ", USE_H1_ORBITAL, "\\n");
Print("\\n=== Testing [6,6,3] partition of S15 ===\\n");
Print("Start time: ", Runtime(), "\\n");

result := FindFPFClassesForPartition(15, [6,6,3]);
Print("\\n[6,6,3] result: ", Length(result), "\\n");
Print("End time: ", Runtime(), "\\n");

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

    print(f"Starting {variant} run at {time.strftime('%H:%M:%S')}")

    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=gap_runtime
    )

    stdout, stderr = process.communicate(timeout=14400)

    print(f"  {variant} finished at {time.strftime('%H:%M:%S')}, return code: {process.returncode}")
    if stderr:
        print(f"  STDERR: {stderr[:500]}")

    return log_file


# Run both variants sequentially
log_orbital = "C:/Users/jeffr/Downloads/Lifting/663_orbital.log"
log_no_orbital = "C:/Users/jeffr/Downloads/Lifting/663_no_orbital.log"

print("=== Running [6,6,3] comparison ===")

run_gap_test("orbital", log_orbital)
run_gap_test("no_orbital", log_no_orbital)

# Compare results
print("\n=== Comparing results ===")

for variant, log_file in [("orbital", log_orbital), ("no_orbital", log_no_orbital)]:
    try:
        with open(log_file.replace("/", os.sep), "r") as f:
            log = f.read()

        # Extract combo counts
        combo_lines = [line.strip() for line in log.split('\n') if 'combo:' in line and 'total)' in line]
        result_lines = [line.strip() for line in log.split('\n') if 'result:' in line]

        print(f"\n{variant}:")
        print(f"  Total combo lines: {len(combo_lines)}")
        if combo_lines:
            print(f"  Last combo: {combo_lines[-1]}")
        if result_lines:
            for r in result_lines:
                print(f"  {r}")

        # Extract per-combo counts
        combo_totals = []
        for line in combo_lines:
            # Parse "combo: X candidates -> Y new (Z total)"
            parts = line.split('(')
            if len(parts) >= 2:
                total_str = parts[-1].replace('total)', '').strip()
                try:
                    combo_totals.append(int(total_str))
                except ValueError:
                    pass

        if combo_totals:
            print(f"  Final total: {combo_totals[-1]}")
            print(f"  Number of combos: {len(combo_totals)}")

    except FileNotFoundError:
        print(f"\n{variant}: Log file not found!")

# Detailed comparison: extract combo-by-combo totals and find first divergence
print("\n=== Detailed combo comparison ===")
try:
    with open(log_orbital.replace("/", os.sep)) as f:
        orb_log = f.read()
    with open(log_no_orbital.replace("/", os.sep)) as f:
        no_orb_log = f.read()

    # Extract ">> combo" lines with their subsequent "combo: X candidates -> Y new" lines
    def extract_combos(log):
        lines = log.split('\n')
        combos = []
        current_combo = None
        for line in lines:
            if '>> combo' in line:
                current_combo = line.strip()
            elif 'combo:' in line and 'total)' in line and current_combo is not None:
                combos.append((current_combo, line.strip()))
                current_combo = None
        return combos

    orb_combos = extract_combos(orb_log)
    no_orb_combos = extract_combos(no_orb_log)

    print(f"Orbital combos: {len(orb_combos)}")
    print(f"No-orbital combos: {len(no_orb_combos)}")

    # Compare combo-by-combo
    min_len = min(len(orb_combos), len(no_orb_combos))
    divergences = []
    for i in range(min_len):
        orb_name, orb_result = orb_combos[i]
        no_orb_name, no_orb_result = no_orb_combos[i]

        # Extract "new" count from result
        def extract_new(s):
            try:
                parts = s.split('->')
                new_str = parts[1].split('new')[0].strip()
                return int(new_str)
            except:
                return -1

        orb_new = extract_new(orb_result)
        no_orb_new = extract_new(no_orb_result)

        if orb_new != no_orb_new:
            divergences.append((i, orb_name, orb_new, no_orb_new))

    if divergences:
        print(f"\n{len(divergences)} combos with different 'new' counts:")
        for idx, name, orb_n, no_orb_n in divergences:
            print(f"  Combo {idx}: orbital={orb_n} no_orbital={no_orb_n} ({no_orb_n - orb_n:+d})")
            print(f"    {name}")
    else:
        print("\nNo divergences found in per-combo 'new' counts!")
        print("(This would mean the difference comes from the dedup, not complement generation)")

except Exception as e:
    print(f"Error during comparison: {e}")
