###############################################################################
# run_sn_holt.py - S_n conjugacy class computation via the Holt engine
#
# Parameterized version of run_s18.py. Orchestrates per-partition parallel
# computation for any n (14..18 tested), writing output in the same format
# as parallel_s18/ (per-combo .g files in parallel_s<n>/[partition]/, gens/
# dir, manifest.json, per-worker logs and result files).
#
# Routes through _HoltDispatchLift with USE_HOLT_ENGINE := true and default
# "clean_first" mode, so fast-path cases go to legacy and the rest go
# through the new clean Holt pipeline.
#
# Usage:
#   python run_sn_holt.py 14 --workers 6             # S_14 with 6 workers
#   python run_sn_holt.py 14 --dry-run               # Preview assignment
#   python run_sn_holt.py 15 --workers 6 --resume    # Resume S_15
#   python run_sn_holt.py 18 --combine-only          # Assemble S_18 cache
#
###############################################################################

import subprocess
import os
import sys
import time
import re
import ast
import json
import argparse
import datetime
import shutil
from pathlib import Path
from collections import Counter
from math import comb

# ===========================================================================
# Configuration
# ===========================================================================
LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
CONJUGACY_CACHE = r"C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache"

# OEIS A000638 verified counts. Used to seed INHERITED_FROM_PREV = A000638(n-1).
KNOWN_COUNTS = {
    1: 1, 2: 2, 3: 4, 4: 11, 5: 19, 6: 56, 7: 96, 8: 296,
    9: 554, 10: 1593, 11: 3094, 12: 10723, 13: 20832,
    14: 75154, 15: 159129, 16: 686165, 17: 1466358,
}

# Set by main() from command-line argument.
N = None
INHERITED_FROM_PREV = None
OEIS_TARGET = None
EXPECTED_FPF = None

# NrTransitiveGroups for degrees 1..18
NR_TRANSITIVE = {
    1: 1, 2: 1, 3: 2, 4: 5, 5: 5, 6: 16, 7: 7, 8: 50,
    9: 34, 10: 45, 11: 8, 12: 301, 13: 9, 14: 63, 15: 104,
    16: 1954, 17: 5, 18: 983,
}

# S18 cost estimates (seconds), derived from actual S17 timing data.
# Partitions not listed here use the heuristic fallback in estimate_partition_cost.
S18_COST_ESTIMATE = {
    # === Tier 0: >10h each (one per worker) ===
    # S17's [4,4,4,3,2]=26299s (70 combos). [5,4,4,3,2] has 150 combos.
    (5, 4, 4, 3, 2):     56000,
    # S17's [4,4,4,3,2]=26299s. [4,4,4,4,2] has 70 combos, all deg-4 factors.
    (4, 4, 4, 4, 2):     30000,
    # S17's [8,4,3,2]=19071s (500 combos). [8,4,4,2] has 750 combos.
    (8, 4, 4, 2):        28000,
    # 4000 combos (50*16*5). Large factor counts.
    (8, 6, 4):           25000,
    # S17's [6,4,4,3]=14953s (480 combos). Same combos + trailing 2.
    (6, 4, 4, 3, 2):     20000,
    # S17's [8,4,3,2]=19071s (500 combos). Similar structure.
    (8, 5, 3, 2):        18000,

    # === Tier 1: 3-10h each ===
    # 1954 combos, degree-16 factor (complex 2-groups).
    (16, 2):             15000,
    # 800 combos (16*5*5*2). Rich factor space.
    (6, 5, 4, 3):        15000,
    # 105 combos (C(7,3)*C(3,2)). Dense subdirect products.
    (4, 4, 4, 3, 3):     15000,
    # 750 combos (50*5*3). Degree-8 heavy.
    (8, 4, 3, 3):        12000,
    # 1250 combos (50*5*5). S17's [8,5,4]=9038s, similar with trailing 2.
    (8, 5, 4, 2):        10000,
    # 1600 combos (50*16*2). S17's [8,6,3]=4686s.
    (8, 6, 3, 2):        10000,
    # 340 combos (34*5*2). Degree-9 factor.
    (9, 4, 3, 2):        10000,
    # 240 combos (16*5*3). Many FPF classes per combo.
    (6, 4, 3, 3, 2):     10000,
    # 1505 combos (301*5). Degree-12 factor.
    (12, 4, 2):          8000,
    # 680 combos (C(17,2)*5). Symmetric deg-6 pairs.
    (6, 6, 4, 2):        8000,
    # 560 combos (16*C(6,2)). Many FPF from deg-4 pairs.
    (6, 4, 4, 4):        8000,
    # S17's [6,5,4,2]=2144s (80076 classes, 400 combos). [6,5,3,3,2] is different shape.
    (6, 5, 3, 3, 2):     7000,
    # 675 combos (45*15). S17's [9,4,4]=4634s.
    (10, 4, 4):          7000,
    # 720 combos (45*16). S17's [9,6,2]=4833s.
    (10, 6, 2):          7000,
    # S17's [5,4,4,4]=1096s (25129 classes). [5,4,4,4,2] adds trailing 2.
    (5, 4, 4, 4, 2):     7000,
    # S17's [5,4,2,2,2,2]=2249s. [5,4,4,2,2,2] restructures.
    (5, 4, 4, 2, 2, 2):  7000,
    # 4816 combos (301*16). Goursat, degree-12 heavy.
    (12, 6):             6000,
    # S17's [8,5,2,2]=13977 classes. [8,4,2,2,2] with deg-4.
    (8, 4, 2, 2, 2):     6000,
    # S17's [4,4,3,2,2,2]=55009 classes. [4,4,4,2,2,2] shifts structure.
    (4, 4, 4, 2, 2, 2):  6000,

    # === Tier 2: 1-3h each ===
    (8, 6, 2, 2):        5000,
    (8, 5, 5):           5000,   # 50*C(6,2)=750 combos
    (10, 4, 2, 2):       5000,
    (6, 6, 6):           5000,   # C(18,3)=816 combos
    (8, 8, 2):           5000,   # C(51,2)=1275 combos
    (9, 4, 4, 2):        5000,
    (6, 6, 3, 3):        4500,
    (10, 8):             4000,   # 2250 combos, Goursat
    (9, 6, 3):           4000,   # 34*16*2=1088 combos
    (6, 5, 4, 2, 2):     4000,
    (6, 4, 4, 2, 2):     4000,
    (5, 5, 4, 4):        4000,   # C(6,2)*C(6,2)=225 combos
    (5, 5, 4, 2, 2):     3500,
    (8, 3, 3, 2, 2):     3500,
    (6, 5, 5, 2):        3500,
    (8, 7, 3):           3000,   # 50*7*2=700 combos
    (6, 4, 2, 2, 2, 2):  3000,
    (5, 4, 3, 3, 3):     3000,
    (12, 3, 3):          3000,   # 301*C(3,2)=903 combos
    (9, 5, 4):           3000,
    (9, 5, 2, 2):        2500,
    (9, 3, 3, 3):        2500,
    (8, 3, 2, 2, 2, 2):  2500,
    (10, 5, 3):          2500,
    (10, 4, 2, 2):       2500,
    (6, 6, 2, 2, 2):     2500,
    (7, 4, 4, 3):        2500,   # 7*C(6,2)*2=210 combos
    (7, 6, 3, 2):        2000,
    (7, 5, 4, 2):        2000,
    (7, 4, 3, 2, 2):     2000,
    (7, 6, 5):           2000,
    (5, 5, 4, 2, 2):     2000,
    (5, 5, 3, 3, 2):     2000,
    (5, 4, 3, 2, 2, 2):  2000,
    (4, 4, 3, 3, 2, 2):  2000,
    (9, 4, 2, 2, 2):     1500,
    (8, 2, 2, 2, 2, 2):  1500,
    (7, 4, 3, 3, 2):     1500,
    (10, 3, 3, 2):       1500,
    (6, 3, 3, 2, 2, 2):  1500,

    # === Tier 3: 15min-1h ===
    (14, 4):             1200,
    (14, 2, 2):          1200,
    (12, 2, 2, 2):       1000,
    (10, 3, 2, 2, 2):    1000,
    (10, 2, 2, 2, 2):    1000,
    (9, 3, 2, 2, 2):     1000,
    (9, 7, 2):           1000,
    (7, 7, 4):           1000,
    (7, 7, 2, 2):        800,
    (7, 5, 3, 3):        800,
    (7, 4, 2, 2, 2, 2):  800,
    (7, 3, 3, 3, 2):     800,
    (6, 3, 3, 3, 3):     800,
    (6, 5, 2, 2, 2, 2):  800,
    (5, 5, 2, 2, 2, 2):  700,
    (5, 3, 3, 3, 2, 2):  700,
    (4, 4, 3, 2, 2, 2, 2): 700,
    (5, 4, 3, 2, 2, 2):  600,
    (11, 7):             500,
    (11, 5, 2):          500,
    (11, 4, 3):          500,
    (13, 5):             500,
    (13, 3, 2):          500,
    (7, 5, 2, 2, 2):     500,
    (7, 3, 3, 2, 2, 2):  500,
    (7, 3, 2, 2, 2, 2):  400,
    (9, 2, 2, 2, 2, 2):  400,

    # === Tier 4: <15 min ===
    (7, 5, 3, 2, 2):     300,
    (6, 2, 2, 2, 2, 2, 2): 300,
    (11, 3, 2, 2):       300,
    (11, 2, 2, 2, 2):    200,
    (5, 3, 3, 2, 2, 2, 2): 200,
    (5, 3, 2, 2, 2, 2, 2): 200,
    (4, 3, 3, 3, 2, 2, 2): 200,
    (4, 3, 3, 2, 2, 2, 2): 200,
    (4, 3, 2, 2, 2, 2, 2, 2): 100,
    (3, 3, 3, 3, 3, 3):  100,
    (3, 3, 3, 3, 2, 2, 2): 100,
    (3, 3, 3, 2, 2, 2, 2, 2): 50,
    (15, 3):             50,
    (4, 2, 2, 2, 2, 2, 2, 2): 50,
    (3, 3, 2, 2, 2, 2, 2, 2): 30,
    (3, 2, 2, 2, 2, 2, 2, 2, 2): 20,
    (2, 2, 2, 2, 2, 2, 2, 2, 2): 10,
    (18,):               5,
}

# Spot checks: partitions with known exact values
SPOT_CHECK = {
    (18,): 983,   # NrTransitiveGroups(18)
}

# Default timeout per worker: 7 days (effectively no timeout)
DEFAULT_TIMEOUT = 604800
# Default number of workers
DEFAULT_WORKERS = 6
# Heartbeat staleness threshold (seconds)
HEARTBEAT_STALE_THRESHOLD = 600

# Set by _init_paths_for_n() from main() once N is known.
OUTPUT_DIR = None
MANIFEST_FILE = None
GENS_DIR = None
MASTER_LOG = None


def _init_config_for_n(n, suffix=""):
    """Populate module-level config globals once n is known from argparse.

    Args:
        n: degree (e.g. 14..18)
        suffix: appended to parallel_s<n>, e.g. "_holt" → parallel_s14_holt
    """
    global N, INHERITED_FROM_PREV, OEIS_TARGET, EXPECTED_FPF
    global OUTPUT_DIR, MANIFEST_FILE, GENS_DIR, MASTER_LOG
    N = n
    if (n - 1) in KNOWN_COUNTS:
        INHERITED_FROM_PREV = KNOWN_COUNTS[n - 1]
    else:
        raise SystemExit(
            f"run_sn_holt.py: no known S_{n-1} count. "
            f"Add it to KNOWN_COUNTS."
        )
    OEIS_TARGET = KNOWN_COUNTS.get(n)  # None if unknown
    if OEIS_TARGET is not None:
        EXPECTED_FPF = OEIS_TARGET - INHERITED_FROM_PREV
    dir_name = f"parallel_s{n}{suffix}"
    OUTPUT_DIR = os.path.join(LIFTING_DIR, dir_name)
    MANIFEST_FILE = os.path.join(OUTPUT_DIR, "manifest.json")
    GENS_DIR = os.path.join(OUTPUT_DIR, "gens")
    MASTER_LOG = os.path.join(OUTPUT_DIR, f"run_s{n}{suffix}.log")


# ===========================================================================
# Utility: partition generation
# ===========================================================================
def partitions_min_part(n, min_part=2):
    """Generate all partitions of n with all parts >= min_part, sorted descending."""
    result = []

    def helper(remaining, max_part, current):
        if remaining == 0:
            result.append(tuple(current))
            return
        for i in range(min(remaining, max_part), min_part - 1, -1):
            current.append(i)
            helper(remaining - i, i, current)
            current.pop()

    helper(n, n, [])
    return result


def partition_key(partition):
    """Convert partition tuple/list to a string key like '8_4_4'."""
    return "_".join(str(x) for x in partition)


def partition_from_key(key):
    """Convert string key '8_4_4' back to a tuple."""
    return tuple(int(x) for x in key.split("_"))


def partition_gap_str(partition):
    """Format partition as GAP list string like '[8,4,4]'."""
    return "[" + ",".join(str(x) for x in partition) + "]"


def partition_dir_name(partition):
    """Convert partition to directory name like '[8,6,4]'."""
    return "[" + ",".join(str(x) for x in partition) + "]"


# ===========================================================================
# Cost estimation
# ===========================================================================
def _estimate_total_combos(partition):
    """Estimate total combos for a partition.

    For repeated parts of degree d with t = NrTransitiveGroups(d), the iteration
    picks indices i1 <= i2 <= ... <= ik, giving C(t+k-1, k) combinations.
    For distinct parts, it's just the product of NrTransitiveGroups.
    """
    combo = 1
    counts = Counter(partition)
    for d, k in counts.items():
        t = NR_TRANSITIVE.get(d, max(1, d))
        if k == 1:
            combo *= t
        else:
            combo *= comb(t + k - 1, k)
    return max(1, combo)


def estimate_partition_cost(partition):
    """Estimate cost of a partition based on S17 timing data.

    Uses S18_COST_ESTIMATE when available, otherwise falls back to
    combo-count heuristic.
    """
    pt = tuple(partition)

    if pt in S18_COST_ESTIMATE:
        return S18_COST_ESTIMATE[pt]

    # Single-part partitions are near-instant
    if len(partition) == 1:
        nr = NR_TRANSITIVE.get(partition[0], 100)
        return max(0.1, nr * 0.01)

    # Fallback: combo-count heuristic
    max_part = max(partition)
    num_2s = sum(1 for p in partition if p == 2)
    k = len(partition)

    combo_count = _estimate_total_combos(partition)

    # Base cost per combo depends on max degree
    if max_part >= 12:
        base_cost_per_combo = max_part * 1.5
    elif max_part >= 8:
        base_cost_per_combo = max_part * 0.8
    else:
        base_cost_per_combo = max_part * 0.3

    # C2 optimization discount for trailing 2s
    if num_2s >= 2:
        base_cost_per_combo *= 0.3

    # Goursat discount for 2-part partitions
    if k == 2 and max_part >= 5:
        base_cost_per_combo *= 0.3

    cost = combo_count * base_cost_per_combo

    return max(0.1, cost)


# ===========================================================================
# Manifest management
# ===========================================================================
def create_manifest(partitions, assignments):
    """Create initial manifest tracking per-partition status."""
    n_fpf_partitions = len(partitions)
    manifest = {
        "n": N,
        "inherited": INHERITED_FROM_PREV,
        "expected_fpf": None,
        "expected_total": None,
        "fpf_partitions": n_fpf_partitions,
        "created": datetime.datetime.now().isoformat(),
        "partitions": {},
    }
    for worker_id, worker_parts in enumerate(assignments):
        for p in worker_parts:
            key = partition_key(p)
            manifest["partitions"][key] = {
                "partition": list(p),
                "status": "pending",
                "worker_id": worker_id,
                "fpf_count": None,
                "elapsed_s": None,
                "started_at": None,
                "completed_at": None,
            }
    return manifest


def load_manifest():
    """Load manifest from disk, or return None if not found."""
    if not os.path.exists(MANIFEST_FILE):
        return None
    with open(MANIFEST_FILE, "r") as f:
        return json.load(f)


def save_manifest(manifest):
    """Save manifest atomically (write to temp, then rename)."""
    tmp = MANIFEST_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(manifest, f, indent=2)
    if os.path.exists(MANIFEST_FILE):
        os.replace(tmp, MANIFEST_FILE)
    else:
        os.rename(tmp, MANIFEST_FILE)


def update_manifest_partition(manifest, partition_key_str, **kwargs):
    """Update fields for a single partition in the manifest."""
    if partition_key_str in manifest["partitions"]:
        manifest["partitions"][partition_key_str].update(kwargs)
        save_manifest(manifest)


# ===========================================================================
# Worker assignment (LPT scheduling)
# ===========================================================================
def assign_partitions_to_workers(partitions, num_workers, ckpt_progress=None):
    """Assign partitions to workers using LPT scheduling."""
    costs = []
    for p in partitions:
        est = estimate_partition_cost(p)
        pt = tuple(p)
        if ckpt_progress and pt in ckpt_progress:
            done_combos, _, total_combos = ckpt_progress[pt]
            frac = max(0.01, 1.0 - done_combos / total_combos) if total_combos > 0 else 1.0
            est *= frac
        costs.append((est, p))
    costs.sort(reverse=True)

    workers = [[] for _ in range(num_workers)]
    worker_loads = [0.0] * num_workers

    for cost, partition in costs:
        min_idx = worker_loads.index(min(worker_loads))
        workers[min_idx].append(partition)
        worker_loads[min_idx] += cost

    return workers, worker_loads


def print_assignment(workers, worker_loads, partitions):
    """Print partition assignment table."""
    print(f"\nPartition assignment ({len(partitions)} partitions -> "
          f"{len(workers)} workers):")
    print("-" * 80)
    for i, (parts, load) in enumerate(zip(workers, worker_loads)):
        if not parts:
            continue
        print(f"  Worker {i}: {len(parts)} partitions, "
              f"est. {load:.0f}s ({load/3600:.1f}h)")
        for ps in parts[:8]:
            est = estimate_partition_cost(ps)
            print(f"    {str(list(ps)):30s}  est. {est:.0f}s ({est/3600:.1f}h)")
        if len(parts) > 8:
            rest_cost = sum(estimate_partition_cost(ps) for ps in parts[8:])
            print(f"    ... and {len(parts)-8} more (est. {rest_cost:.0f}s)")
    print("-" * 80)
    total_est = sum(estimate_partition_cost(p) for p in partitions)
    max_load = max(worker_loads) if worker_loads else 0
    print(f"  Total CPU est:   {total_est:.0f}s ({total_est/3600:.1f}h)")
    print(f"  Max worker est:  {max_load:.0f}s ({max_load/3600:.1f}h)")
    print(f"  Inherited (S{N-1}): {INHERITED_FROM_PREV}")


# ===========================================================================
# GAP script generation (with per-combo output built in)
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
Print("Processing {len(partitions)} partitions for S_{N} (per-combo output)\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load the Holt engine (defines _HoltDispatchLift with clean_first mode
# that routes fast-path cases to legacy and the rest through the clean
# pipeline). USE_HOLT_ENGINE gates the 4 swapped call sites.
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;

# Load precomputed caches (S1-S17)
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

    # Check for clean restart request (memory management).
    if _FORCE_RESTART then
        Print("\\n*** CLEAN RESTART requested after ", partTime, "s ***\\n");
        Print("*** Checkpoint saved. Exiting for fresh process. ***\\n");
        PrintTo("{heartbeat_file}",
            "RESTART after partition ", part, " (partial)\\n");
        LogTo();
        # QuitGap works from anywhere (unlike QUIT which can't be in blocks)
        QuitGap(0);
    fi;

    # Write summary.txt to partition combo output directory.
    # Count classes by reading all per-combo .g files in the partition dir
    # (fpf_classes only contains the CURRENT session's groups, not the total
    # accumulated across all worker restarts via combo files).
    _totalClasses := 0;
    _comboFiles := DirectoryContents(COMBO_OUTPUT_DIR);
    for _cfName in _comboFiles do
        if Length(_cfName) > 2 and _cfName{{[Length(_cfName)-1..Length(_cfName)]}} = ".g" then
            _cfContent := StringFile(Concatenation(COMBO_OUTPUT_DIR, "/", _cfName));
            if _cfContent <> fail then
                for _cfLine in SplitString(_cfContent, "\\n") do
                    if Length(_cfLine) > 0 and _cfLine[1] = '[' then
                        _totalClasses := _totalClasses + 1;
                    fi;
                od;
            fi;
        fi;
    od;
    PrintTo(Concatenation(COMBO_OUTPUT_DIR, "/summary.txt"),
            "partition: [", _partStr, "]\\n",
            "total_classes: ", _totalClasses, "\\n",
            "session_added: ", Length(fpf_classes), "\\n",
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
# Worker process management
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
        f'exec ./gap.exe -q -o 0 "{script_cygwin}"'
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


def read_heartbeat(worker_id, output_dir):
    """Read heartbeat file for a worker. Returns (content, mtime) or (None, None)."""
    hb_file = os.path.join(output_dir, f"worker_{worker_id}_heartbeat.txt")
    try:
        if os.path.exists(hb_file):
            mtime = os.path.getmtime(hb_file)
            with open(hb_file, "r") as f:
                content = f.read().strip()
            return content, mtime
    except (OSError, IOError):
        pass
    return None, None


def parse_worker_results(worker_id, output_dir):
    """Parse results from a worker's result file."""
    result_file = os.path.join(output_dir, f"worker_{worker_id}_results.txt")
    partition_counts = {}
    total = 0
    worker_time = 0

    if not os.path.exists(result_file):
        return partition_counts, total, worker_time

    with open(result_file, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("TOTAL"):
                pass  # Use partition counts instead
            elif line.startswith("TIME"):
                worker_time = float(line.split()[1])
            elif line:
                parts = line.rsplit(" ", 1)
                if len(parts) == 2:
                    part_str = parts[0].strip()
                    count = int(parts[1])
                    partition_counts[part_str] = count
                    total += count

    return partition_counts, total, worker_time


def get_completed_partitions_from_results(output_dir, max_workers):
    """Scan worker result files and gens files for completed partitions."""
    completed = {}

    import glob as _glob
    result_files = _glob.glob(os.path.join(output_dir, "worker_*_results.txt"))
    for result_file in result_files:
        with open(result_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("TOTAL") or line.startswith("TIME") or not line:
                    continue
                parts = line.rsplit(" ", 1)
                if len(parts) == 2:
                    part_str = parts[0].strip()
                    try:
                        count = int(parts[1])
                        p = ast.literal_eval(part_str.replace(" ", ""))
                        key = partition_key(p)
                        completed[key] = count
                    except (ValueError, SyntaxError):
                        pass

    # Also scan gens/ directory
    gens_dir = os.path.join(output_dir, "gens")
    if os.path.isdir(gens_dir):
        for fname in os.listdir(gens_dir):
            if fname.startswith("gens_") and fname.endswith(".txt"):
                part_str = fname[5:-4]
                parts = part_str.split("_")
                try:
                    p = tuple(int(x) for x in parts)
                    key = partition_key(p)
                    if key not in completed:
                        gens_path = os.path.join(gens_dir, fname)
                        with open(gens_path, "r") as f:
                            count = sum(1 for line in f
                                        if line.strip().startswith("["))
                        completed[key] = count
                except (ValueError, IndexError):
                    pass

    return completed


# ===========================================================================
# Logging
# ===========================================================================
def log_msg(msg, also_print=True):
    """Log a message to master log and optionally print."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    if also_print:
        print(line)
    try:
        with open(MASTER_LOG, "a") as f:
            f.write(line + "\n")
    except (OSError, IOError):
        pass


# ===========================================================================
# Main runner with poll loop
# ===========================================================================
def _next_worker_id(output_dir):
    """Find the next available worker ID from checkpoint directories."""
    ckpt_base = os.path.join(output_dir, "checkpoints")
    existing = set()
    if os.path.isdir(ckpt_base):
        for entry in os.listdir(ckpt_base):
            if entry.startswith("worker_"):
                try:
                    existing.add(int(entry.replace("worker_", "")))
                except ValueError:
                    pass
    return max(existing) + 1 if existing else 0


def _get_incomplete_for_worker(assignment_dict, worker_id, output_dir):
    """Return list of partitions assigned to worker_id that lack summary.txt."""
    incomplete = []
    for p in assignment_dict[worker_id]:
        part_dir = os.path.join(output_dir, partition_dir_name(p))
        if not os.path.exists(os.path.join(part_dir, "summary.txt")):
            incomplete.append(p)
    return incomplete


def run_workers(manifest, active_assignments, timeout):
    """Launch workers and monitor with poll loop.
    Respawns individual workers immediately when they exit with
    incomplete partitions (crash, clean restart, etc.)."""
    processes = {}
    start_times = {}
    assignment_dict = {}

    for worker_id, parts in active_assignments:
        script = create_worker_gap_script(parts, worker_id, OUTPUT_DIR)
        proc = launch_gap_worker(script, worker_id)
        processes[worker_id] = proc
        start_times[worker_id] = time.time()
        assignment_dict[worker_id] = parts

        for p in parts:
            key = partition_key(p)
            update_manifest_partition(
                manifest, key,
                status="running",
                worker_id=worker_id,
                started_at=datetime.datetime.now().isoformat()
            )

        log_msg(f"Worker {worker_id} launched (PID {proc.pid}), "
                f"{len(parts)} partitions: "
                f"{', '.join(str(list(p)) for p in parts[:3])}"
                f"{'...' if len(parts) > 3 else ''}")

    overall_start = time.time()
    completed_workers = set()
    last_progress_time = time.time()

    while len(completed_workers) < len(processes):
        time.sleep(30)
        now = time.time()

        for worker_id in list(processes.keys()):
            if worker_id in completed_workers:
                continue

            proc = processes[worker_id]
            rc = proc.poll()
            elapsed = now - start_times[worker_id]

            if rc is not None:
                completed_workers.add(worker_id)
                if rc == 0:
                    log_msg(f"Worker {worker_id} completed (rc=0) in "
                            f"{elapsed:.0f}s ({elapsed/3600:.1f}h)")
                else:
                    log_msg(f"Worker {worker_id} FAILED (rc={rc}) "
                            f"after {elapsed:.0f}s")
                    log_file = os.path.join(OUTPUT_DIR,
                                            f"worker_{worker_id}.log")
                    if os.path.exists(log_file):
                        with open(log_file, "r", errors="replace") as lf:
                            log_tail = lf.readlines()[-5:]
                        log_msg(f"  Log tail: {''.join(log_tail)[:500]}")

                pc, total, wtime = parse_worker_results(worker_id, OUTPUT_DIR)
                for p in assignment_dict[worker_id]:
                    key = partition_key(p)
                    for rkey, count in pc.items():
                        try:
                            rp = ast.literal_eval(rkey.replace(" ", ""))
                            if tuple(rp) == tuple(p):
                                update_manifest_partition(
                                    manifest, key,
                                    status=("completed" if rc == 0
                                            else "failed"),
                                    fpf_count=count,
                                    completed_at=(
                                        datetime.datetime.now().isoformat())
                                )
                                break
                        except (ValueError, SyntaxError):
                            pass
                    else:
                        if rc != 0:
                            update_manifest_partition(
                                manifest, key, status="failed")

                # Immediate respawn: if this worker has incomplete
                # partitions, spawn a fresh worker for them right away.
                # Guard: skip respawn if worker ran < 120s (crash loop).
                still_todo = _get_incomplete_for_worker(
                    assignment_dict, worker_id, OUTPUT_DIR)
                if still_todo and elapsed < 120:
                    log_msg(f"  Worker {worker_id} exited too quickly "
                            f"({elapsed:.0f}s), NOT respawning "
                            f"{len(still_todo)} partitions (crash loop?)")
                    still_todo = []
                if still_todo:
                    new_wid = _next_worker_id(OUTPUT_DIR)
                    log_msg(f"  Respawning {len(still_todo)} incomplete "
                            f"partitions as Worker {new_wid}")
                    ckpt_dir = os.path.join(
                        OUTPUT_DIR, "checkpoints", f"worker_{new_wid}")
                    os.makedirs(ckpt_dir, exist_ok=True)
                    # Copy checkpoint files from old worker to new
                    old_ckpt = os.path.join(
                        OUTPUT_DIR, "checkpoints", f"worker_{worker_id}")
                    if os.path.isdir(old_ckpt):
                        for fname in os.listdir(old_ckpt):
                            src = os.path.join(old_ckpt, fname)
                            dst = os.path.join(ckpt_dir, fname)
                            if not os.path.exists(dst):
                                shutil.copy2(src, dst)
                    script = create_worker_gap_script(
                        still_todo, new_wid, OUTPUT_DIR)
                    new_proc = launch_gap_worker(script, new_wid)
                    processes[new_wid] = new_proc
                    start_times[new_wid] = time.time()
                    assignment_dict[new_wid] = still_todo
                    for p in still_todo:
                        key = partition_key(p)
                        update_manifest_partition(
                            manifest, key,
                            status="running",
                            worker_id=new_wid,
                            started_at=datetime.datetime.now().isoformat()
                        )
                    log_msg(f"Worker {new_wid} launched (PID {new_proc.pid})")

            elif elapsed > timeout:
                log_msg(f"Worker {worker_id} TIMEOUT after "
                        f"{elapsed:.0f}s, killing")
                proc.kill()
                completed_workers.add(worker_id)
                for p in assignment_dict[worker_id]:
                    key = partition_key(p)
                    update_manifest_partition(
                        manifest, key, status="failed")

            else:
                hb_content, hb_mtime = read_heartbeat(worker_id, OUTPUT_DIR)
                if hb_mtime is not None:
                    staleness = now - hb_mtime
                    if staleness > HEARTBEAT_STALE_THRESHOLD:
                        log_msg(f"  WARNING: Worker {worker_id} heartbeat "
                                f"stale ({staleness:.0f}s ago): {hb_content}")

        # Progress line every 30s
        if now - last_progress_time >= 30:
            last_progress_time = now
            wall = now - overall_start
            n_done = len(completed_workers)
            n_total = len(processes)
            running_ids = [wid for wid in processes
                          if wid not in completed_workers]

            done_parts = 0
            fpf_so_far = 0
            for wid in range(max(processes.keys()) + 1):
                pc, total, _ = parse_worker_results(wid, OUTPUT_DIR)
                done_parts += len(pc)
                fpf_so_far += total

            total_parts = len(manifest["partitions"])

            status_parts = []
            for wid in running_ids[:4]:
                hb, _ = read_heartbeat(wid, OUTPUT_DIR)
                if hb:
                    status_parts.append(f"W{wid}:{hb[:40]}")
                else:
                    status_parts.append(f"W{wid}:running")

            print(f"  [{datetime.datetime.now().strftime('%H:%M:%S')}] "
                  f"Workers: {n_done}/{n_total} done | "
                  f"Partitions: {done_parts}/{total_parts} | "
                  f"FPF: {fpf_so_far} | "
                  f"Wall: {wall/3600:.1f}h | "
                  f"{' | '.join(status_parts)}")

    overall_elapsed = time.time() - overall_start
    log_msg(f"All workers finished in {overall_elapsed:.0f}s "
            f"({overall_elapsed/3600:.1f}h)")
    return overall_elapsed


# ===========================================================================
# Result collection and printing
# ===========================================================================
def collect_partition_totals_from_summaries(output_dir):
    """Return {partition_str: total_classes} by reading each partition's
    summary.txt. This is AUTHORITATIVE — summary.txt records the final
    post-dedup count across all worker restarts for a partition, while
    worker_<i>_results.txt only records the session-local Length(fpf_classes)
    from the last GAP session (which can be a partial post-restart session)."""
    counts = {}
    if not os.path.exists(output_dir):
        return counts
    for entry in os.listdir(output_dir):
        if not (entry.startswith("[") and entry.endswith("]")):
            continue
        summary = os.path.join(output_dir, entry, "summary.txt")
        if not os.path.exists(summary):
            continue
        try:
            with open(summary) as f:
                for line in f:
                    m = re.match(r"\s*total_classes:\s*(\d+)", line)
                    if m:
                        counts[entry] = int(m.group(1))
                        break
        except IOError:
            continue
    return counts


def collect_all_results(max_worker_id):
    """Collect summary.txt totals per partition; fall back to worker
    result files for partitions missing a summary.txt."""
    summary_counts = collect_partition_totals_from_summaries(OUTPUT_DIR)

    partition_counts = {}
    worker_times = []

    # Start with worker result files (parse_worker_results format uses
    # '[ a, b, c ]' keys; normalize to '[a,b,c]' matching dir names).
    for wid in range(max_worker_id + 1):
        pc, _, wtime = parse_worker_results(wid, OUTPUT_DIR)
        for key, count in pc.items():
            # Normalize '[ 8, 4, 2 ]' -> '[8,4,2]' to match dir name form.
            norm = key.replace(" ", "")
            partition_counts[norm] = count
        if wtime > 0:
            worker_times.append((wid, wtime))

    # Override with summary.txt values where available (authoritative
    # post-restart total).
    for key, count in summary_counts.items():
        partition_counts[key] = count

    total_fpf = sum(partition_counts.values())
    return total_fpf, partition_counts, worker_times


def print_final_results(max_worker_id):
    """Collect and print final results with spot-check validation."""
    total_fpf, partition_counts, worker_times = collect_all_results(
        max_worker_id)

    total = INHERITED_FROM_PREV + total_fpf
    n_fpf_partitions = len(partitions_min_part(N))

    print(f"\n{'='*70}")
    print(f"Results for S_{N}:")
    print(f"  Inherited from S_{N-1}: {INHERITED_FROM_PREV}")
    print(f"  FPF partition classes:  {total_fpf}")
    print(f"  TOTAL:                  {total}")

    if len(partition_counts) == n_fpf_partitions:
        print(f"  All {n_fpf_partitions} FPF partitions completed!")
        print(f"\n  *** OEIS A000638({N}) = {total} ***")
    else:
        print(f"  ({len(partition_counts)}/{n_fpf_partitions} "
              f"partitions completed)")

    # Bounds check
    if total_fpf > 0:
        ratio = total_fpf / 780193  # FPF(S17)
        print(f"\n  FPF growth ratio vs S17: {ratio:.2f}x")
        if ratio < 0.5 or ratio > 10:
            print(f"  WARNING: Growth ratio outside expected range (1-5x)")

    # Spot checks
    print(f"\nSpot checks:")
    for pt, expected in sorted(SPOT_CHECK.items()):
        found = None
        for rkey, count in partition_counts.items():
            try:
                rp = ast.literal_eval(rkey.replace(" ", ""))
                if tuple(rp) == pt:
                    found = count
                    break
            except (ValueError, SyntaxError):
                pass

        if found is not None:
            status = ("OK" if found == expected
                      else f"FAIL (expected {expected})")
            print(f"  {str(list(pt)):20s}: {found:>6d}  {status}")
        else:
            print(f"  {str(list(pt)):20s}: not yet computed")

    if worker_times:
        times_only = [t for _, t in worker_times]
        print(f"\nTiming:")
        print(f"  Max worker CPU:   {max(times_only):.0f}s "
              f"({max(times_only)/3600:.1f}h)")
        print(f"  Sum worker CPU:   {sum(times_only):.0f}s "
              f"({sum(times_only)/3600:.1f}h)")

    if partition_counts:
        print(f"\nPer-partition counts ({len(partition_counts)} partitions):")
        sorted_parts = []
        for part_str, count in partition_counts.items():
            try:
                rp = ast.literal_eval(part_str.replace(" ", ""))
                sorted_parts.append((tuple(rp), count))
            except (ValueError, SyntaxError):
                sorted_parts.append((part_str, count))
        sorted_parts.sort(
            key=lambda x: x[0] if isinstance(x[0], tuple) else (0,))
        for pt, count in sorted_parts:
            if isinstance(pt, tuple):
                print(f"  {str(list(pt)):30s}: {count}")
            else:
                print(f"  {pt:30s}: {count}")

    return total_fpf, partition_counts


# ===========================================================================
# Combine results into s18_subgroups.g
# ===========================================================================
def join_gap_continuation_lines(filepath):
    """Read a file and join GAP's backslash-continuation lines."""
    with open(filepath, "r") as f:
        raw_lines = f.readlines()

    joined = []
    current = ""
    for raw_line in raw_lines:
        line = raw_line.rstrip("\n").rstrip("\r")
        if line.endswith("\\"):
            current += line[:-1]
        else:
            current += line
            if current.strip():
                joined.append(current)
            current = ""
    if current.strip():
        joined.append(current)
    return joined


def count_groups_in_combo_file(filepath):
    """Count generator lines (lines starting with '[') in a combo .g file."""
    count = 0
    try:
        lines = join_gap_continuation_lines(filepath)
        for line in lines:
            if line.strip().startswith("["):
                count += 1
    except (OSError, IOError):
        pass
    return count


def count_groups_in_gens_file(filepath):
    """Count generator lines in a gens_*.txt file."""
    if not os.path.exists(filepath):
        return 0
    try:
        lines = join_gap_continuation_lines(filepath)
        return sum(1 for line in lines if line.strip().startswith("["))
    except (OSError, IOError):
        return 0


def reconstruct_gens_from_combos(combo_dir, gens_file):
    """Rebuild a gens file from per-combo .g output files.

    This is the OOM safety net: if GAP crashed before finishing the gens
    file, the per-combo files are intact and we can reconstruct.
    """
    all_lines = []
    combo_files = sorted(f for f in os.listdir(combo_dir) if f.endswith(".g"))
    for fname in combo_files:
        fpath = os.path.join(combo_dir, fname)
        lines = join_gap_continuation_lines(fpath)
        for line in lines:
            if line.strip().startswith("["):
                all_lines.append(line.strip())

    with open(gens_file, "w") as f:
        for line in all_lines:
            f.write(line + "\n")

    return len(all_lines)


def reconstruct_gens_if_needed(part_name, combo_dir, gens_file):
    """Check gens file against combo files; reconstruct if truncated."""
    if not os.path.isdir(combo_dir):
        return False

    combo_files = [f for f in os.listdir(combo_dir) if f.endswith(".g")]
    if not combo_files:
        return False

    combo_count = 0
    for fname in combo_files:
        combo_count += count_groups_in_combo_file(
            os.path.join(combo_dir, fname))

    gens_count = count_groups_in_gens_file(gens_file)

    if gens_count < combo_count:
        print(f"  RECONSTRUCTING {part_name}: gens has {gens_count}, "
              f"combos have {combo_count}")
        n_rebuilt = reconstruct_gens_from_combos(combo_dir, gens_file)
        print(f"  Rebuilt {n_rebuilt} generators from combo files")
        return True

    return False


def parse_partition_gens(gens_dir):
    """Parse all per-partition generator files. Returns list of gen lists."""
    all_subgroups = []
    gens_path = Path(gens_dir)

    if not gens_path.exists():
        print(f"WARNING: gens directory {gens_dir} does not exist")
        return []

    for gen_file in sorted(gens_path.glob("gens_*.txt")):
        count = 0
        lines = join_gap_continuation_lines(gen_file)
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                gens = ast.literal_eval(line)
                all_subgroups.append(gens)
                count += 1
            except (ValueError, SyntaxError) as e:
                print(f"  WARNING: Failed to parse line in "
                      f"{gen_file.name}: {e}")
                print(f"    Line preview: {line[:100]}...")
        print(f"  {gen_file.name}: {count} subgroups")

    return all_subgroups


def parse_inherited_chunked(filepath):
    """Parse s17_subgroups.g into list of generator image lists."""
    print(f"  Parsing {filepath} (chunked)...")
    subgroups = []

    with open(filepath, "r") as f:
        content = f.read()

    content = content.replace("\\\n", "")

    lines = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#") or stripped == "":
            continue
        lines.append(line)
    text = "\n".join(lines)

    text = text.strip()
    if text.startswith("return"):
        text = text[6:].strip()
    if text.endswith(";"):
        text = text[:-1].strip()

    depth = 0
    current = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "[":
            if depth == 0:
                current = ch
            else:
                current += ch
            depth += 1
        elif ch == "]":
            depth -= 1
            current += ch
            if depth == 0:
                try:
                    sg = ast.literal_eval(current.strip())
                    subgroups.append(sg)
                except (ValueError, SyntaxError):
                    pass
                current = ""
                if len(subgroups) % 50000 == 0:
                    print(f"    ...parsed {len(subgroups)} subgroups")
        elif depth > 0:
            current += ch
        i += 1

    return subgroups


def write_subgroups_file(filepath, all_subgroups, n):
    """Write subgroups in the standard cache format."""
    now = datetime.datetime.now()
    with open(filepath, "w") as f:
        f.write(f"# Conjugacy class representatives for S{n}\n")
        f.write(f"# Computed via Holt's algorithm with chief series lifting\n")
        f.write(f"# Computed: {now}\n")
        f.write(f"# Total: {len(all_subgroups)} conjugacy classes\n")
        f.write("return [\n")
        for i, gens in enumerate(all_subgroups):
            gen_strs = []
            for gen in gens:
                gen_str = "[ " + ", ".join(str(x) for x in gen) + " ]"
                gen_strs.append(gen_str)

            if len(gen_strs) == 1:
                entry = "  [ " + gen_strs[0] + " ]"
            else:
                entry = "  [ " + gen_strs[0] + ", \n"
                for j in range(1, len(gen_strs)):
                    if j < len(gen_strs) - 1:
                        entry += "  " + gen_strs[j] + ", \n"
                    else:
                        entry += "  " + gen_strs[j] + " ]"

            if i < len(all_subgroups) - 1:
                entry += ","
            f.write(entry + "\n")

            if (i + 1) % 100000 == 0:
                print(f"    ...written {i + 1}/{len(all_subgroups)}")

        f.write("];\n")


def combine_results():
    """Combine inherited S17 classes + FPF partition classes into s18_subgroups.g."""
    s17_file = os.path.join(CONJUGACY_CACHE, "s17_subgroups.g")
    s18_file = os.path.join(CONJUGACY_CACHE, "s18_subgroups.g")

    print(f"\nCombining results into {s18_file}...")

    # Step 0: Reconstruct any truncated gens files from combo output
    print(f"  Step 0: Checking gens files against combo output...")
    n_reconstructed = 0
    partitions = partitions_min_part(N)
    for p in partitions:
        pkey = partition_key(p)
        pname = partition_dir_name(p)
        gens_file = os.path.join(GENS_DIR, f"gens_{pkey}.txt")
        combo_dir = os.path.join(OUTPUT_DIR, pname)
        if reconstruct_gens_if_needed(pname, combo_dir, gens_file):
            n_reconstructed += 1
    if n_reconstructed:
        print(f"  Reconstructed {n_reconstructed} gens files from combo output")
    else:
        print(f"  All gens files intact")

    # Step 1: Parse inherited S17 classes
    print(f"  Step 1: Parsing inherited S17 classes from {s17_file}...")
    inherited = parse_inherited_chunked(s17_file)
    print(f"  Loaded {len(inherited)} inherited classes")

    if len(inherited) != INHERITED_FROM_PREV:
        print(f"  WARNING: Expected {INHERITED_FROM_PREV} inherited classes, "
              f"got {len(inherited)}")

    # Step 2: Extend inherited generators to degree 18
    print(f"  Step 2: Extending inherited generators to degree {N}...")
    for sg in inherited:
        for gen in sg:
            gen.append(N)

    # Step 3: Parse FPF partition generators
    print(f"  Step 3: Parsing FPF partition generators from {GENS_DIR}...")
    fpf_subgroups = parse_partition_gens(GENS_DIR)
    print(f"  Loaded {len(fpf_subgroups)} FPF classes")

    # Step 4: Combine
    all_subgroups = inherited + fpf_subgroups
    total = len(all_subgroups)
    print(f"  Step 4: Total = {len(inherited)} inherited + "
          f"{len(fpf_subgroups)} FPF = {total}")
    print(f"\n  *** OEIS A000638({N}) = {total} ***")

    # Bounds check
    ratio = len(fpf_subgroups) / 780193 if len(fpf_subgroups) > 0 else 0
    print(f"  FPF growth ratio vs S17: {ratio:.2f}x")

    # Step 5: Write output
    print(f"  Step 5: Writing {s18_file}...")
    write_subgroups_file(s18_file, all_subgroups, N)
    print(f"  Done! Output: {s18_file}")
    print(f"  File size: {os.path.getsize(s18_file) / 1024 / 1024:.1f} MB")

    return total


# ===========================================================================
# Resume logic
# ===========================================================================
def get_incomplete_partitions(manifest):
    """Get list of partitions that are not completed."""
    incomplete = []
    for key, info in manifest["partitions"].items():
        if info["status"] != "completed":
            incomplete.append(tuple(info["partition"]))
    return incomplete


def _scan_checkpoint_progress(incomplete_partitions):
    """Scan checkpoint dirs for existing .log files to estimate progress."""
    ckpt_base = os.path.join(OUTPUT_DIR, "checkpoints")
    if not os.path.exists(ckpt_base):
        return {}

    progress = {}
    for p in incomplete_partitions:
        pt = tuple(p)
        partStr = "_".join(str(x) for x in pt)
        log_name = f"ckpt_{N}_{partStr}.log"

        best_combos = 0
        best_fpf = 0
        for entry in os.listdir(ckpt_base):
            candidate = os.path.join(ckpt_base, entry, log_name)
            if not os.path.exists(candidate):
                continue
            try:
                combos = 0
                fpf = 0
                with open(candidate, "r", errors="replace") as f:
                    for line in f:
                        if line.startswith("# end combo"):
                            combos += 1
                            m = re.search(r'\((\d+) total fpf\)', line)
                            if m:
                                fpf = int(m.group(1))
                if combos > best_combos:
                    best_combos = combos
                    best_fpf = fpf
            except (OSError, IOError):
                continue

        if best_combos > 0:
            total_combos = _estimate_total_combos(pt)
            progress[pt] = (best_combos, best_fpf, total_combos)

    return progress


def _recover_checkpoint_logs(incomplete_partitions, active_assignments,
                              next_worker_id):
    """Copy best existing checkpoint .g and .log files to new worker dirs."""
    ckpt_base = os.path.join(OUTPUT_DIR, "checkpoints")

    part_to_new_dir = {}
    for wid, parts in active_assignments:
        for p in parts:
            part_to_new_dir[tuple(p)] = os.path.join(
                ckpt_base, f"worker_{wid}")

    recovered_log = 0
    recovered_g = 0
    for p in incomplete_partitions:
        pt = tuple(p)
        if pt not in part_to_new_dir:
            continue
        partStr = "_".join(str(x) for x in pt)
        log_name = f"ckpt_{N}_{partStr}.log"
        g_name = f"ckpt_{N}_{partStr}.g"
        new_dir = part_to_new_dir[pt]
        new_log = os.path.join(new_dir, log_name)
        new_g = os.path.join(new_dir, g_name)

        old_dirs = []
        for entry in os.listdir(ckpt_base):
            old_dir = os.path.join(ckpt_base, entry)
            if not os.path.isdir(old_dir):
                continue
            try:
                old_wid = int(entry.replace("worker_", ""))
                if old_wid >= next_worker_id:
                    continue
            except ValueError:
                continue
            old_dirs.append(old_dir)

        # Find best .g file (largest)
        if not (os.path.exists(new_g) and os.path.getsize(new_g) > 0):
            best_g = None
            best_g_size = 0
            for old_dir in old_dirs:
                candidate = os.path.join(old_dir, g_name)
                if not os.path.exists(candidate):
                    continue
                sz = os.path.getsize(candidate)
                if sz > best_g_size:
                    best_g_size = sz
                    best_g = candidate

            if best_g and best_g_size > 0:
                shutil.copy2(best_g, new_g)
                print(f"  RECOVER .g: {list(pt)} - {best_g_size//1024}KB "
                      f"from {os.path.basename(os.path.dirname(best_g))}")
                recovered_g += 1

        # Find best .log file (most combos)
        if not (os.path.exists(new_log) and os.path.getsize(new_log) > 0):
            best_log = None
            best_combos = 0
            for old_dir in old_dirs:
                candidate = os.path.join(old_dir, log_name)
                if not os.path.exists(candidate):
                    continue
                try:
                    with open(candidate, "r", errors="replace") as f:
                        combo_count = sum(
                            1 for line in f
                            if line.startswith("# end combo"))
                    if combo_count > best_combos:
                        best_combos = combo_count
                        best_log = candidate
                except (OSError, IOError):
                    continue

            if best_log and best_combos > 0:
                shutil.copy2(best_log, new_log)
                print(f"  RECOVER .log: {list(pt)} - {best_combos} combos "
                      f"from {os.path.basename(os.path.dirname(best_log))}")
                recovered_log += 1

    if recovered_g > 0 or recovered_log > 0:
        print(f"  Recovered: {recovered_g} .g files, "
              f"{recovered_log} .log files")


def resume_computation(args):
    """Resume computation from manifest."""
    manifest = load_manifest()
    if manifest is None:
        print("ERROR: No manifest found. Run without --resume first.")
        sys.exit(1)

    completed = get_completed_partitions_from_results(OUTPUT_DIR, 200)

    for key, count in completed.items():
        if key in manifest["partitions"]:
            manifest["partitions"][key]["status"] = "completed"
            manifest["partitions"][key]["fpf_count"] = count
    save_manifest(manifest)

    incomplete = get_incomplete_partitions(manifest)
    fpf_so_far = sum(v for v in completed.values())
    print(f"\nResume: {len(completed)} completed ({fpf_so_far} FPF), "
          f"{len(incomplete)} incomplete")

    if not incomplete:
        print("All partitions completed! Use --combine-only to assemble.")
        return

    if args.resume_partitions:
        requested = set()
        for p_str in args.resume_partitions:
            try:
                p = tuple(ast.literal_eval(p_str))
                requested.add(p)
            except (ValueError, SyntaxError):
                print(f"ERROR: Cannot parse partition '{p_str}'")
                sys.exit(1)
        incomplete = [p for p in incomplete if p in requested]
        if not incomplete:
            print("No matching incomplete partitions found.")
            return

    ckpt_progress = _scan_checkpoint_progress(incomplete)

    print(f"Resuming {len(incomplete)} partitions with {args.workers} workers")
    for p in incomplete:
        pt = tuple(p)
        est = estimate_partition_cost(p)
        if pt in ckpt_progress:
            done_combos, total_fpf, total_combos = ckpt_progress[pt]
            frac = max(0.01, 1.0 - done_combos / total_combos) \
                if total_combos > 0 else 1.0
            adj_est = est * frac
            print(f"  {str(list(p)):30s}  est. {adj_est:.0f}s ({adj_est/3600:.1f}h)"
                  f"  [ckpt: {done_combos}/{total_combos} combos, "
                  f"{total_fpf} fpf]")
        else:
            print(f"  {str(list(p)):30s}  est. {est:.0f}s ({est/3600:.1f}h)")

    # Find next worker ID
    existing_workers = set()
    for info in manifest["partitions"].values():
        if info.get("worker_id") is not None:
            existing_workers.add(info["worker_id"])
    ckpt_base = os.path.join(OUTPUT_DIR, "checkpoints")
    if os.path.isdir(ckpt_base):
        for entry in os.listdir(ckpt_base):
            if entry.startswith("worker_"):
                try:
                    wid = int(entry.replace("worker_", ""))
                    existing_workers.add(wid)
                except ValueError:
                    pass
    next_worker_id = max(existing_workers) + 1 if existing_workers else 0

    assignments, loads = assign_partitions_to_workers(
        incomplete, args.workers, ckpt_progress=ckpt_progress)
    print_assignment(assignments, loads, incomplete)

    if args.dry_run:
        print("\n[DRY RUN] Would resume with the above assignment.")
        return

    # Remap worker IDs
    active_assignments = []
    for i, parts in enumerate(assignments):
        if parts:
            wid = next_worker_id + i
            active_assignments.append((wid, parts))
            os.makedirs(
                os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{wid}"),
                exist_ok=True)

    _recover_checkpoint_logs(incomplete, active_assignments, next_worker_id)

    # Create combo output directories for incomplete partitions
    for p in incomplete:
        part_dir = os.path.join(OUTPUT_DIR, partition_dir_name(p))
        os.makedirs(part_dir, exist_ok=True)

    run_workers(manifest, active_assignments, args.timeout)
    print_final_results(next_worker_id + args.workers)

    # Auto-resume loop: if workers exited cleanly (RESTART_AFTER_SECONDS)
    # but partitions are still incomplete, restart automatically.
    # Guard: wait 30s before restarting to avoid rapid-fire respawning
    # when workers fail immediately (e.g., syntax errors).
    while True:
        time.sleep(30)  # cooldown to prevent rapid respawn
        # Reload manifest and check completion
        manifest = load_manifest()
        completed = get_completed_partitions_from_results(OUTPUT_DIR, 200)
        for key, count in completed.items():
            if key in manifest["partitions"]:
                manifest["partitions"][key]["status"] = "completed"
                manifest["partitions"][key]["fpf_count"] = count
        save_manifest(manifest)

        still_incomplete = get_incomplete_partitions(manifest)
        if args.resume_partitions:
            requested = set()
            for p_str in args.resume_partitions:
                try:
                    requested.add(tuple(ast.literal_eval(p_str)))
                except (ValueError, SyntaxError):
                    pass
            still_incomplete = [p for p in still_incomplete
                                if p in requested]


        if not still_incomplete:
            log_msg("All requested partitions completed!")
            break

        log_msg(f"AUTO-RESUME: {len(still_incomplete)} partitions still "
                f"incomplete, restarting with fresh process...")

        # Find next worker ID
        existing_workers = set()
        ckpt_base = os.path.join(OUTPUT_DIR, "checkpoints")
        if os.path.isdir(ckpt_base):
            for entry in os.listdir(ckpt_base):
                if entry.startswith("worker_"):
                    try:
                        existing_workers.add(
                            int(entry.replace("worker_", "")))
                    except ValueError:
                        pass
        next_wid = max(existing_workers) + 1 if existing_workers else 0

        ckpt_progress = _scan_checkpoint_progress(still_incomplete)
        assignments, loads = assign_partitions_to_workers(
            still_incomplete, args.workers, ckpt_progress=ckpt_progress)

        active_assignments = []
        for i, parts in enumerate(assignments):
            if parts:
                wid = next_wid + i
                active_assignments.append((wid, parts))
                os.makedirs(os.path.join(OUTPUT_DIR, "checkpoints",
                                         f"worker_{wid}"), exist_ok=True)

        _recover_checkpoint_logs(still_incomplete, active_assignments,
                                  next_wid)

        for p in still_incomplete:
            part_dir = os.path.join(OUTPUT_DIR, partition_dir_name(p))
            os.makedirs(part_dir, exist_ok=True)

        run_workers(manifest, active_assignments, args.timeout)
        print_final_results(next_wid + args.workers)


# ===========================================================================
# Main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description="S_n conjugacy class computation via the Holt engine "
                    "(per-combo output, -o 0)")
    parser.add_argument("n", type=int,
                       help="Degree n (14..18 supported)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                       help=f"Number of parallel workers "
                            f"(default: {DEFAULT_WORKERS})")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show assignment without running")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                       help=f"Per-worker timeout in seconds "
                            f"(default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--combine-only", action="store_true",
                       help="Skip computation, just combine results")
    parser.add_argument("--resume", action="store_true",
                       help="Resume from manifest")
    parser.add_argument("--resume-partitions", nargs="*", default=None,
                       help='Resume specific partitions only')
    parser.add_argument("--no-confirm", action="store_true",
                       help="Don't prompt for confirmation on overwrite")
    parser.add_argument("--suffix", default="_holt",
                       help="Output dir suffix: parallel_s<n><suffix>. "
                            "Default '_holt' keeps legacy runs separate.")
    args = parser.parse_args()

    _init_config_for_n(args.n, suffix=args.suffix)

    print(f"S{N} Conjugacy Class Computation (per-combo output, -o 0)")
    print("=" * 70)
    print(f"Inherited from S{N-1}: {INHERITED_FROM_PREV}")
    if OEIS_TARGET:
        print(f"OEIS target:  {OEIS_TARGET} "
              f"(FPF = {OEIS_TARGET - INHERITED_FROM_PREV})")
    else:
        print(f"OEIS target:  UNKNOWN (new computation)")
    print(f"Workers:      {args.workers}")
    print(f"Timeout:      {args.timeout}s ({args.timeout/3600:.1f}h) per worker")
    print(f"Output:       {OUTPUT_DIR}")

    if args.combine_only:
        total = combine_results()
        print(f"\nTo update database/lift_cache.g, add:")
        print(f'  LIFT_CACHE.("{N}") := {total};')
        return

    if args.resume or args.resume_partitions:
        resume_computation(args)
        return

    # Check for existing output dir
    if os.path.exists(OUTPUT_DIR):
        existing = get_completed_partitions_from_results(OUTPUT_DIR, 200)
        if existing:
            print(f"\nWARNING: {OUTPUT_DIR} already exists with "
                  f"{len(existing)} completed partitions.")
            print(f"Use --resume to continue, or delete the directory "
                  f"for a fresh start.")
            if args.no_confirm:
                print("(--no-confirm: proceeding with overwrite)")
            else:
                resp = input("Continue anyway and overwrite? [y/N] ")
                if resp.lower() != 'y':
                    sys.exit(0)

    # Generate FPF partitions
    partitions = partitions_min_part(N)
    print(f"\nFPF partitions of {N}: {len(partitions)}")

    # Assign to workers
    assignments, loads = assign_partitions_to_workers(
        partitions, args.workers)
    print_assignment(assignments, loads, partitions)

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
        os.makedirs(
            os.path.join(OUTPUT_DIR, "checkpoints", f"worker_{worker_id}"),
            exist_ok=True)

    # Pre-create per-partition combo output directories
    for p in partitions:
        part_dir = os.path.join(OUTPUT_DIR, partition_dir_name(p))
        os.makedirs(part_dir, exist_ok=True)
    print(f"Created {len(partitions)} partition directories for combo output")

    # Initialize master log
    with open(MASTER_LOG, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"S{N} computation started at "
                f"{datetime.datetime.now().isoformat()}\n")
        f.write(f"Workers: {num_active}, Timeout: {args.timeout}s\n")
        f.write(f"OEIS target: UNKNOWN (new computation)\n")
        f.write(f"Per-combo output: {OUTPUT_DIR}/[partition]/\n")
        f.write(f"{'='*70}\n")

    # Clear previous result files for active workers
    for worker_id, parts in active_assignments:
        result_file = os.path.join(
            OUTPUT_DIR, f"worker_{worker_id}_results.txt")
        if os.path.exists(result_file):
            os.remove(result_file)
        for p in parts:
            gen_file = os.path.join(
                GENS_DIR, f"gens_{partition_key(p)}.txt")
            if os.path.exists(gen_file):
                os.remove(gen_file)

    # Create manifest
    manifest = create_manifest(partitions, assignments)
    save_manifest(manifest)
    log_msg(f"Manifest created with {len(partitions)} partitions")

    # Launch and monitor
    log_msg(f"Launching {num_active} workers...")
    overall_elapsed = run_workers(
        manifest, active_assignments, args.timeout)

    # Final results
    total_fpf, partition_counts = print_final_results(args.workers)

    total = INHERITED_FROM_PREV + total_fpf
    log_msg(f"FINAL: S_{N} = {total} "
            f"({INHERITED_FROM_PREV} inherited + {total_fpf} FPF)")
    log_msg(f"Wall-clock: {overall_elapsed:.0f}s "
            f"({overall_elapsed/3600:.1f}h)")

    n_fpf_partitions = len(partitions)
    n_completed = sum(1 for p in manifest["partitions"].values()
                     if p["status"] == "completed")
    if n_completed < len(manifest["partitions"]):
        log_msg(f"WARNING: Only {n_completed}/{len(manifest['partitions'])} "
                f"partitions completed. Use --resume to retry.")
    else:
        log_msg(f"All {len(manifest['partitions'])} partitions completed!")
        print(f"\nRun 'python verify_s18.py' to verify per-combo output.")
        print(f"Run 'python run_s18.py --combine-only' to assemble "
              f"the final cache.")


if __name__ == "__main__":
    main()
