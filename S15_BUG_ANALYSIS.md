# S15 Orbital Undercounting Bug Analysis

## Summary

S15 computation yields **159,116** instead of the expected **159,129** (OEIS A000638).
The FPF partition total is **83,962** vs expected **83,975** — a deficit of exactly **13**.
S2–S14 are all verified correct.

The sole culprit is the **H^1 orbital reduction** optimization (`USE_H1_ORBITAL`).
Disabling it produces the correct count for every partition.

## Affected Partitions

| Partition   | Orbital ON (buggy) | Orbital OFF (correct) | Deficit |
|-------------|--------------------|-----------------------|---------|
| `[5,4,4,2]` | 4,742             | 4,753                 | +11     |
| `[6,6,3]`   | 3,246             | 3,248                 | +2      |
| **Total**    |                    |                       | **+13** |

All other 39 FPF partitions of S15 are unaffected.

## What the Orbital Optimization Does

The H^1 orbital reduction (implemented in `h1_action.g`) speeds up complement enumeration
during chief series lifting. At each layer M → L of the chief series:

1. Compute the complement classes of M/L in S/L via H^1 cohomology
2. Compute the **outer normalizer** action on H^1 (elements of P that normalize S and M but are not in S)
3. Merge H^1 elements that lie in the same orbit — their complements are **P-conjugate**
4. Return only orbit representatives instead of all complements

This reduces the number of complements passed to later layers, providing 30–60% speedup
on partitions with repeated block sizes.

## What We Verified (Correct)

### Every individual orbital merge is mathematically correct
For the combo T(6,5) × T(6,8) × T(3,2) (the source of the [6,6,3] deficit),
we verified at every layer that merged complements are truly P-conjugate via
`RepresentativeAction(P, C1_lift, C2_lift)`. **Zero false merges found.**

Files: `run_verify_layer8.py`, `run_debug_layer4.py`

### At the combo level, orbital produces the same N-classes
The combo T(6,5) × T(6,8) × T(3,2) produces:
- **26 raw** results with orbital OFF → **14 N-classes** after full N-dedup
- **14 raw** results with orbital ON → **14 N-classes** after full N-dedup

Cross-comparison confirms these are the **same 14 N-classes**.

File: `run_combo_ndedup.py`

### H_missing IS present in the combo's orbital ON output
The specific missing subgroup (|H| = 216, structure "C3 × ((C3 × A4) : C2)")
is N-conjugate to ON result #11 within the combo. It is not lost at the combo level.

File: `run_check_in_combo.py`

### The action formula is mathematically correct
The outer action formula `(f^n)(g_j) = ρ(n)(f(α_n^{-1}(g_j)))` was verified
against GAP's conjugation convention (`x^y = y^{-1}·x·y`). The implementation
in `ComputeOuterActionOnH1` correctly computes:
- `actionMatM`: conjugation action of n on M_bar (ρ(n))
- Generator permutation: `gi_S^nInv = n · gi_S · n^{-1}` gives α_n^{-1}(g_j)

### Descendants of P-conjugate parents are P-conjugate
If S1 = S2^p for p ∈ P, then since p normalizes every term of the chief series,
the lifting of S1 and S2 through any subsequent layer produces P-conjugate children.
Dropping a P-conjugate parent at an intermediate layer should not lose any P-class
of final FPF results.

## Where the Bug Manifests

### The partition-level dedup loses the class
At the **partition level**, `FindFPFClassesForPartition` iterates over all factor
combinations (combos) and uses `incrementalDedup` to merge results:

```gap
incrementalDedup := function(newResults)
    local H, localByInvariant, before;
    localByInvariant := rec();       # <-- FRESH per combo call
    ...
    for H in newResults do
        if AddIfNotConjugate(N, H, all_fpf, localByInvariant, invFunc) then
            addedCount := addedCount + 1;
        fi;
    od;
end;
```

**Critical observation:** `localByInvariant` is reset to empty for each combo.
`AddIfNotConjugate` only checks the `localByInvariant` buckets — it does **not**
check `all_fpf` (the global accumulator) directly. This means:

- **Within-combo dedup works** (via `localByInvariant`)
- **Cross-combo dedup does NOT happen** — results from different combos are never
  compared for N-conjugacy

### How this interacts with orbital

Although each combo produces the same N-classes regardless of orbital ON/OFF,
the **specific group representatives** differ. With orbital ON:
- Fewer raw results (14 vs 26) enter the within-combo dedup
- Different specific subgroups become the surviving representatives
- These different representatives have different invariant keys

When a later combo contributes a group that is N-conjugate to a representative
from an earlier combo, no cross-combo dedup catches this. The invariant-keyed
representatives from orbital ON may cause subtle differences in how the
within-combo dedup of **other** combos plays out, ultimately losing 1–2 classes
that would have survived with the original (orbital OFF) representatives.

## Possible Fixes

### Fix 1: Use global `byInvariant` (simplest)
Replace `localByInvariant` with the outer-scope `byInvariant` in `incrementalDedup`.
This enables cross-combo dedup and should make the result independent of which
specific representatives orbital chooses.

**Risk:** May change counts for S2–S14 if cross-combo duplicates exist there
(though empirically they appear not to, since counts are already correct).

### Fix 2: Disable orbital for affected partitions only
Set `USE_H1_ORBITAL := false` for partitions `[5,4,4,2]` and `[6,6,3]`.
This is a targeted workaround but doesn't address the root cause.

### Fix 3: Full cross-combo N-dedup pass
After all combos complete, do a final pairwise N-dedup over `all_fpf`.
This is O(k²) but with invariant bucketing would be fast in practice.

## Current Workaround

For the S15 generator files, we recompute only the two affected partitions
with `USE_H1_ORBITAL := false` and merge with the 39 unaffected originals.
This produces the correct 83,975 FPF classes (and 159,129 total).

## Key Files

| File | Purpose |
|------|---------|
| `h1_action.g` | H^1 orbital implementation (`GetH1OrbitRepresentatives`, `ComputeOuterActionOnH1`) |
| `lifting_algorithm.g` | Core lifting (`LiftThroughLayer`), outer normalizer computation |
| `lifting_method_fast_v2.g` | Partition driver (`FindFPFClassesForPartition`, `incrementalDedup`) |
| `cohomology.g` | H^1 computation and caching (`CachedComputeH1`, `ComputeModuleFingerprint`) |
| `modules.g` | Module construction (`ChiefFactorAsModule`) |

## Diagnostic Scripts (in project root)

| Script | What it does |
|--------|-------------|
| `run_find_missing_classes.py` | Identifies the specific missing N-classes in [6,6,3] |
| `run_trace_missing2.py` | Traces missing class to combo T(6,5)×T(6,8)×T(3,2) and layer 4 |
| `run_debug_layer4.py` | Detailed layer 4 analysis (all merges verified P-conjugate) |
| `run_per_layer_orbital.py` | Per-layer orbital ON/OFF comparison |
| `run_verify_layer8.py` | Verifies all layer 8 orbital merges |
| `run_check_in_combo.py` | Confirms H_missing is N-conjugate to combo ON result #11 |
| `run_combo_ndedup.py` | Proves combo ON and OFF produce same 14 N-classes |
| `run_trace_partition_dedup.py` | Traces partition-level dedup (ON=3246, H_missing NOT found) |
| `run_recompute_affected.py` | Recomputes [5,4,4,2] and [6,6,3] with orbital OFF |
| `merge_s15_gens.py` | Merges fixed gens with originals for full S15 output |
