# Codex Instructions for Lifting Project

## Project Goal

**The goal of this project is the efficient computation of S14's conjugacy classes of subgroups.**

This requires correctly implementing Holt's algorithm with all optimizations. The naive approach is computationally infeasible for S14.

## Critical Guidance: Fix Bugs, Don't Disable Optimizations

**IMPORTANT:** When encountering bugs in optimization code (cohomology, C2 fiber products, Pcgs methods, etc.):

1. **DO NOT** simply disable the optimization or fall back to slower methods
2. **DO** investigate and fix the root cause of the bug
3. **DO** understand the mathematical algorithm before modifying code

Disabling optimizations is a dead end - we cannot reach S14 without them working correctly. Each optimization exists because:
- **H^1 cohomology method**: Avoids expensive complement enumeration
- **C2 fiber product optimization**: Uses GF(2) linear algebra for partitions with trailing 2s
- **Pcgs-based cocycle computation**: O(r²) relations vs O(2^r) for FP-groups
- **Chief series lifting**: Avoids full subgroup lattice enumeration

If an optimization is buggy, the correct approach is to:
1. Understand what the optimization is trying to do mathematically
2. Trace through the code to find where it diverges from the math
3. Fix the specific bug while preserving the optimization's benefits

## Running GAP on Windows

**IMPORTANT:** Always launch GAP through Python, not directly via Bash.

GAP on this system uses Cygwin and requires specific environment setup. Direct execution fails due to path format issues.

### Correct Approach

Create a Python script to run GAP commands. **Always use `LogTo()` in GAP** to write output to a log file - stdout from Cygwin GAP can be truncated or lost for long-running computations.

```python
import subprocess
import os

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output.log"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
# ... your GAP commands here ...
LogTo();
QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

# Run GAP via Cygwin bash
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=3600)

# Read results from the LogTo file (more reliable than stdout)
with open(r"C:\Users\jeffr\Downloads\Lifting\gap_output.log", "r") as f:
    log = f.read()
print(log)
```

### Key Points

1. **Always use `LogTo()`** in GAP scripts to capture output to a file. Stdout from Cygwin can be truncated for long computations. Call `LogTo();` (no args) before `QUIT;` to flush.
2. **Use Windows paths in GAP code:** `C:/Users/jeffr/...` (forward slashes)
3. **Use Cygwin paths for bash:** `/cygdrive/c/Users/jeffr/...`
4. **Always use `-q -o 0` flags** — `-q` for quiet mode, `-o 0` for unlimited memory. OOM crashes during long computations cause silent data loss and are much worse than high memory usage.
5. **Set appropriate timeout** - S10 takes ~2.5 minutes, S11 takes ~7 minutes. **For S16+ partitions, do not set a timeout** — individual partitions can take many hours.
6. **Clear caches before speed tests** - GAP caches (`FPF_SUBDIRECT_CACHE`, `LIFT_CACHE`, `ClearH1Cache()`) persist across runs. For accurate timing, clear all caches before benchmarking:
   ```gap
   FPF_SUBDIRECT_CACHE := rec();
   LIFT_CACHE := rec();
   if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
   ```
7. **Fast warmup for single-partition tests** - To test a single partition (e.g., `[4,4,4]` of S12) without recomputing S2-S11 (~430s), load the precomputed caches:
   ```gap
   Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
   # Load precomputed S1-S11 counts (skips recursive computation)
   Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
   # FPF subdirect cache is loaded automatically by load_database.g
   # Now test a single partition directly:
   FindFPFClassesForPartition(12, [4,4,4]);
   ```
   The `database/lift_cache.g` file contains verified S1-S11 counts. The FPF subdirect cache (`database/fpf_subdirects/fpf_cache.g`) is loaded automatically on startup and provides cached factor-combination results.

### Speed Testing / A/B Testing

**Always run GAP tests in the background** using `run_in_background=true` so Codex can continue working while waiting. GAP computations often take 5-15+ minutes.

**A/B test structure for comparing optimizations:**

1. **Run sequentially, not in parallel.** Although GAP is single-threaded and two processes would use separate cores, OS-level cache interactions (disk cache, filesystem buffers) give the second process a warm-cache advantage. Memory pressure from two GAP sessions can also cause swapping on large computations. Sequential runs produce more reliable comparisons.
2. Use a single Python script that runs variant A, swaps the code, runs variant B, then restores the original.
3. To isolate a single partition (e.g., `[4,4,4]`), call `FindFPFClassesForPartition(n, partition)` directly instead of `CountAllConjugacyClassesFast(n)`. Lower-degree data must be loaded first via `CountAllConjugacyClassesFast` on the previous degree.
4. Always clear caches before the partition under test.
5. Use separate log files per variant (e.g., `gap_output_a.log`, `gap_output_b.log`).

**Example: sequential A/B test on a single partition:**

```python
# Run variant A with current code, log to gap_output_a.log
# ... run GAP, wait for completion ...

# Swap source file to variant B
# Run variant B, log to gap_output_b.log
# ... run GAP, wait for completion ...

# Restore original source file
# Compare timing from both log files
```

See `run_ab_test.py` for a working example.

### Existing Test Scripts

- `run_test.py` - Runs S2-S10 tests with output logging
- `run_s7_test.py` - Quick S7 verification
- `run_ab_test.py` - A/B test template for comparing optimizations on a single partition
- `test_s8.g` - S8 test commands

### Project Files

- `lifting_algorithm.g` - Core lifting algorithm with chief series
- `lifting_method_fast_v2.g` - Main driver with optimizations
- `OPTIMIZATION_PROGRESS.md` - Current status and benchmarks

### Reference Partition Counts

Ground-truth per-partition conjugacy class counts (computed by brute-force `ConjugacyClassesSubgroups(S_n)`):

- **S12**: `C:\Users\jeffr\Downloads\Symmetric Groups\Partition\s12_partition_classes_output.txt`
- **S13**: `C:\Users\jeffr\Downloads\Symmetric Groups\Partition\s13_partition_classes_output.txt`
- **S17**: `C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache\s17_orbit_type_counts.txt` — 297 orbit types (partitions), total 1,466,358 classes, FPF sum (no 1-parts) = 780,193. Format: `[partition]  count` lines after header.

Use these to verify per-partition correctness when debugging. The partitions without 1-parts are the FPF (fix-point-free) classes computed by `FindFPFClassesForPartition`.

Full-enumeration subgroup caches (every conjugacy class of S_n, for deep audits): `C:\Users\jeffr\Downloads\Symmetric Groups\conjugacy_cache\s13_subgroups.g`, `s14_subgroups.g`, `s15_subgroups.g`, `s16_subgroups.g`, `s17_subgroups.g.bak`.

### Current Benchmarks (2026-02-08)

All values S1-S15 verified against OEIS A000638:

| n | Count | Time (fresh) | Time (cached S1-(n-1)) |
|---|-------|-------------|----------------------|
| S2-S10 | 1593 | 48s | — |
| S11 | 3094 | — | 38s |
| S12 | 10723 | — | 662s |
| S13 | 20832 | — | 1258s |
| S14 | 75154 | — | ~4h parallel (8 workers) |
| S15 | 159129 | — | parallel (8 workers) |

Holt's reference timings (Magma, 2008 hardware): S13=105s, S14=653s, S15=1190s

### Known Issues (Need Fixing, Not Disabling)

- **Cohomology bugs (FIXED)**: Two bugs were fixed:
  1. `ComputeCocycleSpaceViaPcgs` safety check now requires `ngens = Length(pcgs)` exactly (was only checking `ngens > Length(pcgs)`). When `ngens < Length(pcgs)`, RHS words referenced out-of-range generators that were silently skipped.
  2. `ComputeModuleFingerprint` for H^1 caching now includes Pcgs relative orders and power/commutator relation exponents. Previously, isomorphic quotient groups with different Pcgs orderings (e.g., D12 with relOrders [2,2,3] vs [2,3,2]) could produce identical fingerprints, causing cached H^1 representatives from one presentation to be incorrectly applied to another.

- **C2 optimization**: Now re-enabled with `HasSmallAbelianization()` guard. Works for groups with r ≤ 1 (S_n, A_n, C_n). Falls back to lifting for groups with r > 1 (V4, D8).

- **[8,2] partition (FIXED)**: Was the main bottleneck (~70s) due to `AllSubgroups` being called on non-abelian simple chief factors (e.g., A8). Fixed by adding `IsSimpleGroup` fast path in `NormalSubgroupsBetween` — now ~12s.
