"""Watchdog for [6,5,5] partition - auto-skips hung combos.

The [6,5,5] partition has combos involving TransitiveGroup(6,14) (S_5 on 6 pts)
whose complement computation hangs indefinitely. This script:
1. Resumes from W31's checkpoint (195 combos, 1115 groups)
2. Monitors heartbeat; if unchanged for COMBO_TIMEOUT_MIN, kills GAP
3. Parses the log to find which combo is stuck
4. Adds stuck combo's key to checkpoint as "completed" (skip it)
5. Relaunches GAP to continue

Also pre-skips combo "[ [ 5, 2 ], [ 5, 2 ], [ 6, 14 ] ]" which is known to hang.
"""

import subprocess
import os
import sys
import time
import re
import shutil

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16")
N = 16
WORKER_ID = 36
PARTITION = (6, 5, 5)

# Kill GAP if heartbeat unchanged for this many minutes
COMBO_TIMEOUT_MIN = 20

# Known-hung combos to pre-skip (add more as discovered)
KNOWN_HUNG_COMBOS = [
    '[ [ 5, 2 ], [ 5, 2 ], [ 6, 14 ] ]',
]

# Checkpoint source
SOURCE_CKPT = os.path.join(OUTPUT_DIR, "checkpoints", "worker_31", "ckpt_16_6_5_5.g")


def get_ckpt_path():
    return os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{WORKER_ID}", "ckpt_16_6_5_5.g")


def add_skip_combos_to_checkpoint(combo_keys):
    """Add combo keys to the checkpoint's completed list so they get skipped."""
    ckpt_path = get_ckpt_path()
    with open(ckpt_path, "r") as f:
        content = f.read()

    for key in combo_keys:
        # Check if already in the checkpoint
        if f'"{key}"' in content:
            print(f"  Key already in checkpoint: {key}")
            continue

        # Find the last entry in _CKPT_COMPLETED_KEYS list (before the closing ])
        # The format is: "key1",\n"key2",\n...\n"keyN"\n];
        # Add after the last key
        # Find the pattern: last quoted key before "];"
        pattern = r'("[ \[\]0-9, ]+")(\n\];)'
        match = re.search(pattern, content)
        if match:
            content = content[:match.end(1)] + ',\n' + f'"{key}"' + content[match.start(2):]
            print(f"  Added skip key: {key}")
        else:
            print(f"  WARNING: Could not add key to checkpoint: {key}")

    # Update the comment line
    # Count keys
    key_count = content.count('"[ [')
    content = re.sub(r'# \d+ combos', f'# {key_count} combos', content)

    with open(ckpt_path, "w") as f:
        f.write(content)


def parse_stuck_combo_from_log(log_path):
    """Parse the GAP log to find the combo that was being processed when it got stuck."""
    with open(log_path, "r") as f:
        lines = f.readlines()

    # Look backwards for the last ">> combo [[ ... ]]" line
    for line in reversed(lines):
        m = re.search(r'>> combo (\[\[ .+? \]\])', line)
        if m:
            # Convert from [[ [5,2], [5,2], [6,14] ]] format to checkpoint key format
            raw = m.group(1)
            # The combo as printed has the factor IDs sorted by degree in the key
            # The checkpoint key format is the same as the combo output
            # Just clean it up
            return raw.strip()

    return None


def create_gap_script():
    log_file = os.path.join(OUTPUT_DIR, f"worker_{WORKER_ID}.log").replace("\\", "/")
    result_file = os.path.join(OUTPUT_DIR, f"worker_{WORKER_ID}_results.txt").replace("\\", "/")
    gens_dir = os.path.join(OUTPUT_DIR, "gens").replace("\\", "/")
    ckpt_dir = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{WORKER_ID}").replace("\\", "/")
    heartbeat_file = os.path.join(OUTPUT_DIR, f"worker_{WORKER_ID}_heartbeat.txt").replace("\\", "/")

    part_str = "[6,5,5]"

    gap_code = f'''
LogTo("{log_file}");
Print("Worker {WORKER_ID} (watchdog) starting at ", StringTime(Runtime()), "\\n");
Print("Processing partition {part_str} for S_{N}\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

CHECKPOINT_DIR := "{ckpt_dir}";
_HEARTBEAT_FILE := "{heartbeat_file}";

if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

part := {part_str};

Print("\\n========================================\\n");
Print("Partition ", part, ":\\n");
partStart := Runtime();

PrintTo("{heartbeat_file}", "starting partition ", part, "\\n");

fpf_classes := FindFPFClassesForPartition({N}, part);
partTime := (Runtime() - partStart) / 1000.0;
Print("  => ", Length(fpf_classes), " classes (", partTime, "s)\\n");

partStr := JoinStringsWithSeparator(List(part, String), "_");
genFile := Concatenation("{gens_dir}", "/gens_", partStr, ".txt");
PrintTo(genFile, "");
for _h_idx in [1..Length(fpf_classes)] do
    _gens := List(GeneratorsOfGroup(fpf_classes[_h_idx]),
                  g -> ListPerm(g, {N}));
    AppendTo(genFile, String(_gens), "\\n");
od;
Print("  Generators saved to ", genFile, "\\n");

AppendTo("{result_file}",
    String(part), " ", String(Length(fpf_classes)), "\\n");

PrintTo("{heartbeat_file}",
    "completed partition ", part, " = ", Length(fpf_classes), " classes\\n");

Print("\\nWorker {WORKER_ID} complete\\n");

LogTo();
QUIT;
'''
    script_file = os.path.join(OUTPUT_DIR, f"worker_{WORKER_ID}.g")
    with open(script_file, "w") as f:
        f.write(gap_code)
    return script_file


def launch_gap(script_file):
    script_cygwin = script_file.replace("C:\\", "/cygdrive/c/").replace("\\", "/")
    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'
    cmd = [
        BASH_EXE, "--login", "-c",
        f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
    ]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        cwd=GAP_RUNTIME
    )
    return process


def main():
    ckpt_dir = os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{WORKER_ID}")
    os.makedirs(ckpt_dir, exist_ok=True)
    log_file = os.path.join(OUTPUT_DIR, f"worker_{WORKER_ID}.log")
    hb_file = os.path.join(OUTPUT_DIR, f"worker_{WORKER_ID}_heartbeat.txt")
    result_file = os.path.join(OUTPUT_DIR, f"worker_{WORKER_ID}_results.txt")

    # Copy source checkpoint
    ckpt_dest = get_ckpt_path()
    if os.path.exists(SOURCE_CKPT):
        shutil.copy2(SOURCE_CKPT, ckpt_dest)
        print(f"Copied checkpoint from W31: {os.path.getsize(ckpt_dest)} bytes")
    else:
        print("WARNING: No source checkpoint found, starting fresh")

    # Pre-add known hung combos
    if os.path.exists(ckpt_dest):
        print("Pre-skipping known hung combos:")
        add_skip_combos_to_checkpoint(KNOWN_HUNG_COMBOS)

    skipped_combos = list(KNOWN_HUNG_COMBOS)
    max_restarts = 20  # Safety limit
    restart_count = 0

    while restart_count < max_restarts:
        # Clean log for this run (append mode - GAP will overwrite via LogTo)
        # Remove old log so we can track this run's output
        if os.path.exists(log_file):
            os.remove(log_file)

        script = create_gap_script()
        proc = launch_gap(script)
        print(f"\n[Restart #{restart_count}] Launched GAP (PID {proc.pid})")
        print(f"  Timeout: {COMBO_TIMEOUT_MIN} min per combo")

        last_hb_content = ""
        last_hb_change = time.time()
        check_interval = 30  # seconds

        while True:
            time.sleep(check_interval)

            # Check if process exited
            rc = proc.poll()
            if rc is not None:
                print(f"\n  GAP exited with code {rc}")
                if rc == 0:
                    # Check if partition completed
                    if os.path.exists(result_file):
                        with open(result_file) as f:
                            results = f.read().strip()
                        if results:
                            print(f"  COMPLETED! Results: {results}")
                            print(f"\n=== Summary ===")
                            print(f"Skipped combos: {len(skipped_combos)}")
                            for c in skipped_combos:
                                print(f"  {c}")
                            return 0
                    print("  GAP exited cleanly but no results found")
                else:
                    print(f"  GAP crashed (exit code {rc})")
                break  # Will restart

            # Check heartbeat
            if os.path.exists(hb_file):
                with open(hb_file) as f:
                    hb = f.read().strip()

                if hb != last_hb_content:
                    last_hb_content = hb
                    last_hb_change = time.time()

                    # Parse progress
                    m = re.search(r'combo #(\d+) fpf=(\d+)', hb)
                    if m:
                        combo_num = int(m.group(1))
                        fpf = int(m.group(2))
                        elapsed = time.time() - last_hb_change
                        print(f"  [{time.strftime('%H:%M:%S')}] combo #{combo_num} fpf={fpf}")
                    elif "completed" in hb:
                        print(f"  [{time.strftime('%H:%M:%S')}] {hb}")
                    elif "starting" in hb:
                        print(f"  [{time.strftime('%H:%M:%S')}] {hb}")

                stale_min = (time.time() - last_hb_change) / 60.0
                if stale_min > COMBO_TIMEOUT_MIN:
                    print(f"\n  TIMEOUT: heartbeat stale for {stale_min:.0f} min")

                    # Parse stuck combo from log
                    stuck_combo = None
                    if os.path.exists(log_file):
                        stuck_combo = parse_stuck_combo_from_log(log_file)

                    if stuck_combo:
                        print(f"  Stuck on combo: {stuck_combo}")

                        # Kill the GAP process
                        proc.kill()
                        proc.wait(timeout=30)
                        print(f"  Killed GAP process")

                        # Add to skip list
                        # Convert combo format: [[ [5,2], [5,2], [6,14] ]] -> [ [ 5, 2 ], [ 5, 2 ], [ 6, 14 ] ]
                        # The checkpoint key format uses spaces around numbers
                        # Let's extract factor pairs from the combo and rebuild the key
                        # The log format is: [[ [ 5, 2 ], [ 5, 2 ], [ 6, 14 ] ]]
                        # The checkpoint key format is: [ [ 5, 2 ], [ 5, 2 ], [ 6, 14 ] ]
                        # Remove outer brackets
                        key = stuck_combo.strip()
                        if key.startswith("[["):
                            key = key[1:-1].strip()  # Remove outer [ ]

                        skipped_combos.append(key)
                        print(f"  Adding to skip list: {key}")

                        # Update checkpoint
                        add_skip_combos_to_checkpoint([key])
                        break  # Restart
                    else:
                        print("  Could not determine stuck combo from log")
                        proc.kill()
                        proc.wait(timeout=30)
                        break
            else:
                stale_min = (time.time() - last_hb_change) / 60.0
                if stale_min > COMBO_TIMEOUT_MIN + 5:
                    print(f"  No heartbeat file after {stale_min:.0f} min, killing")
                    proc.kill()
                    proc.wait(timeout=30)
                    break

        restart_count += 1
        if restart_count < max_restarts:
            print(f"\n  Restarting (attempt {restart_count + 1}/{max_restarts})...")
            time.sleep(5)

    print(f"\nExhausted {max_restarts} restarts")
    return 1


if __name__ == "__main__":
    sys.exit(main())
