###############################################################################
# run_s17_v2.py - S17 computation with per-combo output logging
#
# Same computation as run_s17.py but with:
#   - Per-combo output files in parallel_s17_v2/[partition]/ for traceability
#   - 6 workers (default) instead of 8
#   - -o 0 for unlimited GAP memory
#   - 7-day timeout (effectively no timeout)
#
# Usage:
#   python run_s17_v2.py --dry-run            # Preview assignment
#   python run_s17_v2.py                       # Launch computation
#   python run_s17_v2.py --workers 4           # Use 4 workers
#   python run_s17_v2.py --resume              # Resume incomplete
#   python run_s17_v2.py --combine-only        # Assemble final cache
#
###############################################################################

import os
import sys
import subprocess
import time
import datetime
import argparse
from pathlib import Path

# Import shared infrastructure from run_s17
import run_s17

# ===========================================================================
# Override configuration
# ===========================================================================
LIFTING_DIR = run_s17.LIFTING_DIR
GAP_RUNTIME = run_s17.GAP_RUNTIME
BASH_EXE = run_s17.BASH_EXE
N = run_s17.N
INHERITED_FROM_S16 = run_s17.INHERITED_FROM_S16
OEIS_S17 = run_s17.OEIS_S17
EXPECTED_FPF = run_s17.EXPECTED_FPF

OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s17_v2")
MANIFEST_FILE = os.path.join(OUTPUT_DIR, "manifest.json")
GENS_DIR = os.path.join(OUTPUT_DIR, "gens")
MASTER_LOG = os.path.join(OUTPUT_DIR, "run_s17_v2.log")

DEFAULT_TIMEOUT = 604800  # 7 days (effectively no timeout)
DEFAULT_WORKERS = 6

# Patch run_s17 module constants so its functions use our paths
run_s17.OUTPUT_DIR = OUTPUT_DIR
run_s17.MANIFEST_FILE = MANIFEST_FILE
run_s17.GENS_DIR = GENS_DIR
run_s17.MASTER_LOG = MASTER_LOG
run_s17.DEFAULT_TIMEOUT = DEFAULT_TIMEOUT


# ===========================================================================
# Helpers
# ===========================================================================
def partition_dir_name(partition):
    """Convert partition to directory name like '[8,6,3]'."""
    return "[" + ",".join(str(x) for x in partition) + "]"


# ===========================================================================
# Modified GAP script generation with per-combo output
# ===========================================================================
def create_worker_gap_script(partitions, worker_id, output_dir):
    """Create a GAP script that processes partitions with per-combo output."""
    log_file = os.path.join(output_dir, f"worker_{worker_id}.log").replace("\\", "/")
    result_file = os.path.join(output_dir, f"worker_{worker_id}_results.txt").replace("\\", "/")
    gens_dir = os.path.join(output_dir, "gens").replace("\\", "/")
    ckpt_dir = os.path.join(output_dir, "checkpoints", f"worker_{worker_id}").replace("\\", "/")
    heartbeat_file = os.path.join(output_dir, f"worker_{worker_id}_heartbeat.txt").replace("\\", "/")
    combo_base = output_dir.replace("\\", "/")

    partition_strs = []
    for p in partitions:
        partition_strs.append("[" + ",".join(str(x) for x in p) + "]")
    partitions_gap = "[" + ",\n    ".join(partition_strs) + "]"

    gap_code = f'''
LogTo("{log_file}");
Print("Worker {worker_id} starting at ", StringTime(Runtime()), "\\n");
Print("Processing {len(partitions)} partitions for S_{N} (v2 per-combo output)\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed caches (S1-S16)
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Enable checkpointing
CHECKPOINT_DIR := "{ckpt_dir}";

# Enable heartbeat
_HEARTBEAT_FILE := "{heartbeat_file}";

# Clear H1 cache initially
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

myPartitions := {partitions_gap};

totalCount := 0;
workerStart := Runtime();

for part in myPartitions do
    Print("\\n========================================\\n");
    Print("Partition ", part, ":\\n");
    partStart := Runtime();

    # Set per-combo output directory for this partition
    _partStr := JoinStringsWithSeparator(List(part, String), ",");
    COMBO_OUTPUT_DIR := Concatenation("{combo_base}/[", _partStr, "]");
    Print("  COMBO_OUTPUT_DIR = ", COMBO_OUTPUT_DIR, "\\n");

    # Clear caches per partition to free memory and ensure independence
    FPF_SUBDIRECT_CACHE := rec();
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

    # Write heartbeat before starting partition
    PrintTo("{heartbeat_file}",
        "starting partition ", part, "\\n");

    fpf_classes := FindFPFClassesForPartition({N}, part);
    partTime := (Runtime() - partStart) / 1000.0;
    Print("  => ", Length(fpf_classes), " classes (", partTime, "s)\\n");
    totalCount := totalCount + Length(fpf_classes);

    # Write summary.txt to partition combo output directory
    PrintTo(Concatenation(COMBO_OUTPUT_DIR, "/summary.txt"),
            "partition: [", _partStr, "]\\n",
            "total_classes: ", Length(fpf_classes), "\\n",
            "elapsed_seconds: ", partTime, "\\n");

    # Save generators to per-partition gens file
    partStr := JoinStringsWithSeparator(List(part, String), "_");
    genFile := Concatenation("{gens_dir}", "/gens_", partStr, ".txt");
    PrintTo(genFile, "");  # Clear any previous content
    for _h_idx in [1..Length(fpf_classes)] do
        _gens := List(GeneratorsOfGroup(fpf_classes[_h_idx]),
                      g -> ListPerm(g, {N}));
        AppendTo(genFile, String(_gens), "\\n");
    od;
    Print("  Generators saved to ", genFile, "\\n");

    # Write count to results file
    AppendTo("{result_file}",
        String(part), " ", String(Length(fpf_classes)), "\\n");

    # Memory stats
    if IsBound(GasmanStatistics) then
        Print("  Memory: ", GasmanStatistics(), "\\n");
    fi;

    # Write heartbeat after completing partition
    PrintTo("{heartbeat_file}",
        "completed partition ", part, " = ", Length(fpf_classes), " classes\\n");
od;

workerTime := (Runtime() - workerStart) / 1000.0;
Print("\\nWorker {worker_id} complete: ", totalCount, " total classes in ",
      workerTime, "s\\n");

# Write final summary
AppendTo("{result_file}", "TOTAL ", String(totalCount), "\\n");
AppendTo("{result_file}", "TIME ", String(workerTime), "\\n");

# Save FPF cache for future use
if IsBound(SaveFPFSubdirectCache) then
    SaveFPFSubdirectCache();
fi;

LogTo();
QUIT;
'''

    script_file = os.path.join(output_dir, f"worker_{worker_id}.g")
    with open(script_file, "w") as f:
        f.write(gap_code)

    return script_file


# ===========================================================================
# Modified worker launch with -o 0 for unlimited memory
# ===========================================================================
def launch_gap_worker(script_file, worker_id):
    """Launch a GAP worker process with unlimited memory (-o 0)."""
    script_cygwin = script_file.replace("C:\\", "/cygdrive/c/").replace("\\", "/")

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    cmd = [
        BASH_EXE, "--login", "-c",
        f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
        f'./gap.exe -q -o 0 "{script_cygwin}"'
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        cwd=GAP_RUNTIME,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )
    return process


# Monkey-patch run_s17 to use our overrides for functions called internally
run_s17.create_worker_gap_script = create_worker_gap_script
run_s17.launch_gap_worker = launch_gap_worker


# ===========================================================================
# Main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description="S17 conjugacy class computation (v2 with per-combo output)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                       help=f"Number of parallel workers (default: {DEFAULT_WORKERS})")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show assignment without running")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                       help=f"Per-worker timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--combine-only", action="store_true",
                       help="Skip computation, just combine results")
    parser.add_argument("--resume", action="store_true",
                       help="Resume from manifest")
    parser.add_argument("--resume-partitions", nargs="*", default=None,
                       help='Resume specific partitions only')
    args = parser.parse_args()

    print(f"S{N} Conjugacy Class Computation (v2 - per-combo output)")
    print("=" * 70)
    print(f"Inherited from S{N-1}: {INHERITED_FROM_S16}")
    print(f"OEIS target:  {OEIS_S17} (FPF = {EXPECTED_FPF})")
    print(f"Workers:      {args.workers}")
    print(f"Timeout:      {args.timeout}s ({args.timeout/3600:.1f}h) per worker")
    print(f"Output:       {OUTPUT_DIR}")

    if args.combine_only:
        total = run_s17.combine_results()
        print(f"\nTo update database/lift_cache.g, add:")
        print(f'  LIFT_CACHE.("17") := {total};')
        return

    if args.resume or args.resume_partitions:
        run_s17.resume_computation(args)
        return

    # Check for existing output dir
    if os.path.exists(OUTPUT_DIR):
        existing = run_s17.get_completed_partitions_from_results(OUTPUT_DIR, 32)
        if existing:
            print(f"\nWARNING: {OUTPUT_DIR} already exists with "
                  f"{len(existing)} completed partitions.")
            print(f"Use --resume to continue, or delete the directory for a fresh start.")
            resp = input("Continue anyway and overwrite? [y/N] ")
            if resp.lower() != 'y':
                sys.exit(0)

    # Generate FPF partitions
    partitions = run_s17.partitions_min_part(N)
    print(f"\nFPF partitions of {N}: {len(partitions)}")

    # Assign to workers
    assignments, loads = run_s17.assign_partitions_to_workers(
        partitions, args.workers)
    run_s17.print_assignment(assignments, loads, partitions)

    # Filter out empty workers
    active_assignments = [
        (i, parts) for i, parts in enumerate(assignments) if parts]
    num_active = len(active_assignments)
    print(f"\nActive workers: {num_active}")

    if args.dry_run:
        print("\n[DRY RUN] Would run with the above assignment.")
        return

    # Create output directories
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(GENS_DIR, exist_ok=True)
    for worker_id, _ in active_assignments:
        os.makedirs(os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{worker_id}"),
                   exist_ok=True)

    # Pre-create per-partition combo output directories
    for p in partitions:
        part_dir = os.path.join(OUTPUT_DIR, partition_dir_name(p))
        os.makedirs(part_dir, exist_ok=True)
    print(f"Created {len(partitions)} partition directories for combo output")

    # Initialize master log
    with open(MASTER_LOG, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"S{N} v2 computation started at "
                f"{datetime.datetime.now().isoformat()}\n")
        f.write(f"Workers: {num_active}, Timeout: {args.timeout}s\n")
        f.write(f"Target: {OEIS_S17} (FPF = {EXPECTED_FPF})\n")
        f.write(f"Per-combo output: {OUTPUT_DIR}/[partition]/\n")
        f.write(f"{'='*70}\n")

    # Clear previous result files and gens files for active workers
    for worker_id, parts in active_assignments:
        result_file = os.path.join(OUTPUT_DIR, f"worker_{worker_id}_results.txt")
        if os.path.exists(result_file):
            os.remove(result_file)
        for p in parts:
            gen_file = os.path.join(GENS_DIR,
                                    f"gens_{run_s17.partition_key(p)}.txt")
            if os.path.exists(gen_file):
                os.remove(gen_file)

    # Create manifest
    manifest = run_s17.create_manifest(partitions, assignments)
    run_s17.save_manifest(manifest)
    run_s17.log_msg(f"Manifest created with {len(partitions)} partitions")

    # Launch and monitor
    run_s17.log_msg(f"Launching {num_active} workers...")
    overall_elapsed = run_s17.run_workers(
        manifest, active_assignments, args.timeout)

    # Final results
    total_fpf, partition_counts = run_s17.print_final_results(args.workers)

    total = INHERITED_FROM_S16 + total_fpf
    run_s17.log_msg(f"FINAL: S_{N} = {total} "
                    f"({INHERITED_FROM_S16} inherited + {total_fpf} FPF)")
    run_s17.log_msg(
        f"Wall-clock: {overall_elapsed:.0f}s ({overall_elapsed/3600:.1f}h)")

    if total == OEIS_S17:
        run_s17.log_msg(f"SUCCESS: Matches OEIS A000638(17) = {OEIS_S17}")
    elif len(partition_counts) == 66:
        run_s17.log_msg(
            f"MISMATCH: {total} != OEIS A000638(17) = {OEIS_S17}")

    n_completed = sum(1 for p in manifest["partitions"].values()
                     if p["status"] == "completed")
    n_total = len(manifest["partitions"])
    if n_completed < n_total:
        run_s17.log_msg(
            f"WARNING: Only {n_completed}/{n_total} partitions completed. "
            f"Use --resume to retry failed partitions.")
    else:
        run_s17.log_msg(
            f"All {n_total} partitions completed successfully!")
        print(f"\nRun 'python verify_s17_v2.py' to verify per-combo output.")
        print(f"Run 'python run_s17_v2.py --combine-only' to assemble "
              f"the final cache.")


if __name__ == "__main__":
    main()
