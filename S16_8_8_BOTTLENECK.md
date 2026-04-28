# S16 [8,8] Partition Bottleneck Analysis

## Summary

The partition `[8,8]` of S16 has a severe dedup bottleneck that makes it the
most expensive single partition in the S16 computation. The problem is not the
lifting algorithm itself, but the **incremental N-conjugacy deduplication** of
large candidate batches with poor invariant discrimination.

## The Problem

### Combo [8,3],[8,3]: 1096 seconds for 4 new classes

```
>> combo [[ [ 8, 3 ], [ 8, 3 ] ]] factors=[ [ 8, 3 ], [ 8, 3 ] ] |P|=64
  LiftThroughLayer [abelian p=2 dim=1] 1125ms
    64 parents, 448 complements generated, 448 FPF accepted (512 total lifted)
  combo: 512 candidates -> 4 new (635 total)
  combo #100 done (1190.625s elapsed, 635 fpf total)
```

- **Lifting**: 1.1 seconds (fast!)
- **Dedup**: ~1095 seconds (512 candidates checked against 631 existing groups)
- **Yield**: only 4 new classes out of 512 candidates (99.2% redundant)

### Why dedup is slow here

1. **Repeated parts**: Partition `[8,8]` has two equal parts, so the normalizer
   `N = S_8 wr S_2` includes block permutations. This means many candidate
   subgroups are N-conjugate (hence the 99.2% redundancy).

2. **Poor invariant bucketing**: `TransitiveGroup(8,3)` has order 8 (= C_2^3).
   All 512 candidates are order-8 subgroups acting on 16 points with similar
   cycle structures, orbit lengths, and conjugacy class histograms. The invariant
   function cannot distinguish them well, so they land in large buckets.

3. **Expensive RepresentativeAction**: Each candidate requires a
   `RepresentativeAction(N, H1, H2)` call against every group in its invariant
   bucket. With ~512 candidates and bucket sizes potentially in the hundreds,
   this is O(candidates × bucket_size) expensive conjugacy tests.

## Scale of the Problem

### Combo count
- `NrTransitiveGroups(8) = 50`
- With repeated-part symmetry: `50 × 51 / 2 = 1275` combos total

### Current progress (as of combo #105)
- 105 of 1275 combos completed in ~1475s CPU
- Average rate: ~14s/combo
- BUT one combo alone took 1096s (combo #100)

### What's coming
The first 105 combos used only small groups (T(8,1)..T(8,3), order ≤ 8).
Upcoming combos involve much larger groups:

| TransitiveGroup(8,k) | Order | Name | Impact |
|---|---|---|---|
| T(8,1)..T(8,5) | 8 | Small 2-groups | Fast lifting, slow dedup |
| T(8,14) | 56 | | Moderate |
| T(8,37) | 1344 | PGL(2,7) variant | Many lifting layers |
| T(8,48) | 1344 | AGL(1,8) variant | Many lifting layers |
| T(8,49) | 20160 | A_8 | Non-abelian simple chief factors |
| T(8,50) | 40320 | S_8 | Heaviest, A_8 chief factor |

The combo `[8,49],[8,49]` (two copies of A_8) and `[8,50],[8,50]` (two copies
of S_8) will have enormous chief series with non-abelian simple A_8 chief factors.
These combos individually could take hours.

### Time estimate
- **Optimistic** (current avg rate): 1275 × 14s = 5h
- **Realistic** (accounting for harder combos): 10-15h
- **Pessimistic** (if A_8/S_8 combos explode): 20-30h+

## Potential Mitigations

### 1. Better invariant discrimination (medium effort)
Add more invariant data for repeated-part partitions to reduce bucket sizes:
- Per-block stabilizer orders
- Derived subgroup order
- Frattini subgroup order
- Number of elements of each order (not just conjugacy classes)

### 2. Batch dedup with canonical forms (high effort)
Instead of pairwise `RepresentativeAction`, compute a canonical form for each
candidate under the normalizer action. Groups with the same canonical form are
conjugate. This turns O(k × bucket) into O(k × canonical_cost).

### 3. Dedup at the lifting level (medium effort)
Instead of generating all 512 candidates and then deduping, apply the normalizer
action DURING lifting to produce only orbit representatives. This requires
integrating the normalizer into the complement enumeration.

### 4. Skip known-redundant combos (low effort)
For the combo `[T_i, T_i]` where both factors are identical, precompute that the
only non-redundant subdirects are those not related by the S_2 block swap. This
halves the candidate count for same-factor combos.

### 5. FPF subdirect cache (already implemented)
Once `[8,3],[8,3]` is computed, the result is cached in `FPF_SUBDIRECT_CACHE`.
Future partitions that include this factor combination will reuse the cached
result. So the pain is one-time.

## Current Status

Worker 1 is actively computing (confirmed by CPU usage monitoring). It is NOT
stuck—just slow due to the dedup bottleneck. The checkpoint system will save
progress every 60-120s, so if it needs to be killed and resumed, minimal work
is lost.
