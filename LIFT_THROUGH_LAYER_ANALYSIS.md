# LiftThroughLayer: Function Analysis and Deduplication

## What LiftThroughLayer Does

`LiftThroughLayer(P, M, N, subgroups_containing_M, shifted_factors, offsets)` is the core step of Holt's chief-series lifting algorithm. It takes a list of subgroups that contain a chief factor M and produces subgroups that contain the next factor N (but not necessarily M).

### Parameters

- **P**: The full direct product (e.g., S4 x S4 x S4 for partition [4,4,4])
- **M, N**: Adjacent terms in the chief series, with N < M. The "layer" is M/N.
- **subgroups_containing_M**: Input from previous layer (or [P] for the first layer)
- **shifted_factors, offsets**: Describes the factor structure for FPF checking

### Algorithm

For each input subgroup S containing M:

1. **S itself** is checked: if `IsFPFSubdirect(S)`, it's added to the output
2. **Normal subgroups** L between N and M (with L normal in S) are found via `NormalSubgroupsBetween(S, M, N)`
3. For each such L (skipping L = M):
   - Form the quotient `Q = S/L`
   - Find complements to `M/L` in `Q` (subgroups C_bar with `C_bar * M/L = Q` and `C_bar ∩ M/L = 1`)
   - Lift complements back to S via `PreImages(hom, C_bar)`
   - Filter for FPF subdirect condition
4. All candidates from all (S, L) pairs are collected into a flat list `lifted`
5. **Deduplicate** `lifted` under P-conjugacy via `RemoveConjugatesUnderP`
6. Return the deduplicated list as input to the next layer

### Complement-Finding Methods

The function uses several methods to find complements, chosen by the structure of M/L:

- **Coprime case** (Schur-Zassenhaus): If `gcd(|Q/M_bar|, |M_bar|) = 1`, exactly one complement class exists
- **H^1 cohomology**: For elementary abelian M_bar, uses first cohomology to enumerate complement classes efficiently
- **H^1 orbital**: When outer normalizer elements exist (elements of N_P(S) ∩ N_P(M) outside S), uses their action on H^1 to reduce complement enumeration by grouping into orbits
- **Fallback**: `ComplementClassesRepresentatives` or `NonSolvableComplementClassReps`

---

## The Two Levels of Deduplication

The algorithm has two distinct dedup stages, operating under different groups:

### Level 1: Inside LiftThroughLayer (`RemoveConjugatesUnderP`)

- **Group**: P (the direct product, e.g., S4 x S4 x S4, |P| = 13,824)
- **Purpose**: Remove P-conjugate duplicates from the `lifted` list before passing to the next layer
- **Why needed**: Different (S, L) pairs can produce P-conjugate complements. Without dedup, duplicate subgroups propagate through subsequent layers, causing combinatorial explosion — each duplicate spawns its own set of complements in the next layer.
- **Implementation**: `RemoveConjugatesUnderP` — invariant-bucketed pairwise `RepresentativeAction(P, H, rep)` calls

### Level 2: In FindFPFClassesForPartition (`incrementalDedup`)

- **Group**: N (the normalizer, e.g., S4 wr S3, |N| = 82,944 for [4,4,4])
- **Purpose**: Remove N-conjugate duplicates from the final output across all factor combinations
- **Why needed**: The lifting operates on a specific factor combination (e.g., (S4, S4, S4)). Different factor combinations may produce N-conjugate results. Also, P-conjugacy is strictly finer than N-conjugacy: two subgroups that are non-conjugate under P may be conjugate under N.

### The Asymmetry

Level 1 dedup (under P) is *necessary* for correctness of the layered lifting — it prevents exponential blowup across layers. But it's also *conservative*: it only identifies P-conjugates, while the final dedup under N will merge additional classes. This means Level 1 can output "too many" representatives, which Level 2 then reduces.

---

## Performance: The 928 -> 928 Problem

### Observed on [4,4,4] (S12)

```
LiftThroughLayer breakdown: normals=0ms complements=2657ms dedup=132047ms (928 -> 928 reps)
combo: 928 candidates -> 12 new (233 total)
```

The layer produces 928 candidates. `RemoveConjugatesUnderP` spends **132 seconds** comparing them and eliminates **zero** — all 928 are genuinely non-conjugate under P. Then `incrementalDedup` (Level 2, under the larger normalizer N) reduces 928 candidates to just **12** new representatives.

This means:
- 928 subgroups are all P-inequivalent (Level 1 confirms this, expensively)
- But only 12 are N-inequivalent relative to previously seen subgroups (Level 2)
- **132 seconds of Level 1 dedup produces no useful reduction**

### Why Does Level 1 Find Nothing?

The complements produced within a single `LiftThroughLayer` call tend to be structurally distinct under P-conjugacy. This is because:

1. They come from different input subgroups S (which are already P-inequivalent from the previous layer)
2. They come from different normal subgroups L between N and M
3. The complement construction itself (via H^1 or Schur-Zassenhaus) already returns conjugacy class representatives within Q = S/L

The P-conjugacies that *do* exist are mostly caught by Level 2 under the larger group N, which has additional symmetries (wreath permutations of equal-degree blocks) that P lacks.

### The Bug We Found

`RemoveConjugatesUnderP` had a structural inefficiency. It first bucketed subgroups by `CheapSubgroupInvariant` (size, derived subgroup, center, exponent, conjugacy classes, abelian invariants, cycle types, orbits), but then **ignored the buckets** in the comparison phase:

```gap
# Old code (buggy):
reps := [];
repInvs := [];
for key in RecNames(byInv) do
    for H in byInv.(key) do
        found := false;
        for i in [1..Length(reps)] do          # scans ALL reps
            if repInvs[i] = key then           # string comparison per rep
                if RepresentativeAction(P, H, reps[i]) <> fail then
                    found := true; break;
                fi;
            fi;
        od;
        ...
```

This is O(n * total_reps) with a string comparison for each, instead of O(n * bucket_size). For 928 reps, that's ~430,000 iterations with string comparisons, even though the buckets might have only ~50-100 reps each.

### The Fix

Compare only within the bucket that was already computed:

```gap
# Fixed code:
reps := [];
for key in RecNames(byInv) do
    bucketReps := [];
    for H in byInv.(key) do
        found := false;
        for rep in bucketReps do               # only same-bucket reps
            if RepresentativeAction(P, H, rep) <> fail then
                found := true; break;
            fi;
        od;
        if not found then
            Add(bucketReps, H);
            Add(reps, H);
        fi;
    od;
od;
```

### Impact

First measurement after fix (same [4,4,4] combination):
```
dedup=98578ms (928 -> 928 reps)   # was 132047ms — 25% faster
```

The improvement is real but modest because the invariant buckets for these 928 subgroups are large — many of them share the same abstract invariants (size, derived subgroup, etc.) even though they're embedded differently. The `RepresentativeAction` calls, not the string comparisons, dominate.

---

## Open Questions

### Is Level 1 Dedup Necessary?

If Level 1 rarely eliminates duplicates, is it worth spending 98-132 seconds on it? The risk of skipping it: without Level 1 dedup, the output of each layer feeds directly into the next. If a layer outputs 928 reps instead of (say) 900 after dedup, the next layer processes 928 inputs instead of 900. Each input spawns multiple complements, so the blowup is multiplicative across layers.

For [4,4,4], the chief series has ~6 layers. If one layer outputs 928 instead of 928 (no reduction), skipping dedup has no cost. But if another layer would have reduced 928 to 500, skipping it means the next layer processes 1.85x more inputs. This needs profiling per-layer.

### Could Level 1 Use Cheaper Dedup?

Instead of full `RepresentativeAction` (which solves the subgroup conjugacy problem), Level 1 could use:

- **Size-only bucketing**: Skip RA calls entirely, just bucket by invariants. Groups in the same bucket but not checked for conjugacy might produce some redundant work in the next layer, but avoid the 98s dedup cost.
- **Sampling**: For large buckets, compare each new subgroup against a random subset of existing reps rather than all of them. If conjugates exist, they're likely found quickly.
- **Order-based heuristic**: If the bucket is large (>100 reps) and no conjugates have been found after the first 50 comparisons, assume the rest are also non-conjugate and skip.

### Richer Invariants

The 928 reps falling into large buckets suggests `CheapSubgroupInvariant` isn't discriminating enough for these subgroups. Since they're all subgroups of S4 x S4 x S4 acting on 12 points, embedding-sensitive invariants (orbit structure, fixed point count, action on specific point sets) would split the buckets further. This is the same insight as the "richer invariants" idea from the Optimization B analysis, but applied to Level 1 instead of Level 2.
