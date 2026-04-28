# AutReduction × Hom-twists: general complement enumeration for non-abelian simple chief factors

## Status

Design doc for a future optimization. Not implemented. The targeted
bottleneck is `NonSolvableComplementClassReps` (NSCR) being called for
combos where the non-abelian simple chief-factor layer has `|C| < idx`
(non-direct-product case). NSCR takes minutes per parent on large Q;
the method here should bring that down to seconds or less.

See also:
- `lifting_algorithm.g:345` — `NonSolvableComplementClassReps` (current fallback).
- `lifting_algorithm.g:422` — `NonAbelianComplementsViaAut` (existing AutReduction; only safe when `gcd(|C|, |M_bar|) = 1`).
- `lifting_algorithm.g:487` — `HomBasedCentralizerComplements` (covers the `|C| = idx` direct-product case with `gcd > 1`).

---

## Problem

Given:
- `Q`: an ambient group at some chief-series layer of `P`.
- `M_bar`: a non-abelian simple normal subgroup of `Q`.
- Goal: enumerate `Q`-conjugacy classes of complements `K` of `M_bar` in `Q`
  (i.e., subgroups `K ≤ Q` with `|K| = [Q:M_bar]`, `K ∩ M_bar = 1`,
  `K · M_bar = Q`).

Because `Z(M_bar) = 1`, the extension `1 → M_bar → Q → Q/M_bar → 1` always splits
(`H²(·, Z(M_bar)) = 0`), so complements exist. The hard part is counting
conjugacy classes.

### Why NSCR is slow

NSCR does a brute-force maximal-subgroup descent of `Q`: `Q → max subgrps of
Q → max subgrps of those → …` keeping only candidates with trivial `∩
M_bar`. For `|Q|` around 1M, `MaximalSubgroupClassReps` on each level is
minutes. The whole descent compounds.

### Why the two existing fast paths aren't enough

1. **`HomBasedCentralizerComplements`** only handles the direct-product case
   `Q = M_bar × C_Q(M_bar)`, requiring `|C_Q(M_bar)| = idx` and
   `C_Q(M_bar) ∩ M_bar = 1`. Common for some combos, not all.

2. **`NonAbelianComplementsViaAut` (AutReduction, Holt)** works for any `Q`
   but its correctness guard requires `gcd(|C|, |M_bar|) = 1`. When
   `gcd > 1`, there are extra complements arising from non-trivial
   homomorphisms `C → M_bar` that AutReduction misses, so the guard
   sends us to NSCR.

What we want is **the general AutReduction result extended by the Hom twists**
— valid for any `|C|` and any `gcd`.

---

## Mathematical framework

### Setup

- `phi: Q → Aut(M_bar)` via conjugation (`q` sends `m` to `qmq⁻¹`).
- `C = ker(phi) = C_Q(M_bar)`.
- `A = im(phi) ≤ Aut(M_bar)`.
- `Inn(M_bar) ≤ A` because `phi(M_bar) = Inn(M_bar)` (center of `M_bar` is trivial, so `Inn(M_bar) ≅ M_bar`).

### Exact sequence for `Q/M_bar`

`phi` descends to `phi_bar: Q/M_bar → A/Inn(M_bar)` with kernel
`C · M_bar / M_bar ≅ C`:

```
1 → C → Q/M_bar → A/Inn(M_bar) → 1
```

So `Q/M_bar` is an extension of the "outer" piece `A/Inn(M_bar)` by the
"inner" piece `C`.

### Complements as 1-cocycles

The complements of `M_bar` in `Q` biject (up to Q-conjugation) with
equivalence classes of **1-cocycles** `σ: Q/M_bar → M_bar` satisfying
the identity

```
σ(g·h) = σ(g) · (g ⋅ σ(h))
```

where `g ⋅ m = phi_bar(g)(m)` is the action on `M_bar` via outer
conjugation. Two cocycles are equivalent iff they differ by a
coboundary `σ_m(g) = m · (g ⋅ m)⁻¹` for some `m ∈ M_bar`; equivalence
classes form the pointed set `H¹(Q/M_bar, M_bar)`.

### AutReduction's contribution

`NonAbelianComplementsViaAut` computes complements of `Inn(M_bar)` in
`A` — call the reps `A_1, ..., A_r`. Each lifts to

```
Base_i := phi⁻¹(A_i) ≤ Q
```

with `|Base_i| = |A_i| · |C|`. Since `|A_i| = |A|/|Inn(M_bar)| = [Q:C·M_bar]`,
we get `|Base_i| = |Q|/|M_bar| = idx`. Also `Base_i ∩ M_bar = 1` (chase
through the definition). So each `Base_i` is **one complement**.

The AutReduction reps exhaust complement classes *when* the remaining
cohomology is trivial, which is exactly when `Hom(C, M_bar) = {trivial}`,
i.e., `gcd(|C|, |M_bar|) = 1`.

### What Hom twists add (when `gcd > 1`)

For each `Base_i` and each homomorphism `φ: C → M_bar`, define the
twisted subgroup

```
Base_i^φ := { (c ↦ φ(c)·c) ⋅ (lift of A_i) : ... }
```

Concretely: pick a section `s: A_i → Base_i`, so every `b ∈ Base_i`
factors uniquely as `b = c · s(a)` with `c ∈ C`, `a ∈ A_i`. Define

```
Base_i^φ = { φ(c) · c · s(a) : c ∈ C, a ∈ A_i }.
```

Claim: `Base_i^φ` is a complement of `M_bar` in `Q`, and the map
`φ ↦ Base_i^φ` gives additional complement classes. Two twists
`φ_1, φ_2` give `Q`-conjugate complements iff they differ by Inn(M_bar)
conjugation *composed* with the `A_i`-action on `Hom(C, M_bar)` (the
outer twist).

So the full enumeration is

```
{ Base_i^φ : 1 ≤ i ≤ r, φ ∈ Hom(C, M_bar) }
```

deduplicated by the Q-conjugation equivalence, which restricts to

```
(φ, i) ~ (φ', i')   iff   i = i'   and
                         φ' = Inn(m) ∘ φ ∘ inv-twist-by-A_i
                         for some m ∈ M_bar and appropriate inner automorphism.
```

For the **direct product case** (`|C| = idx`, so `A = Inn(M_bar)` and
`A_i = 1`, `r = 1`): the formula collapses to `{Base_1^φ : φ ∈ Hom(C, M_bar)}` modulo
Inn(M_bar)-conjugation. This is exactly what `HomBasedCentralizerComplements`
already computes.

For `|C| < idx` and `gcd > 1`: AutReduction gives `r ≥ 2` base complements;
each gets Hom twists.

---

## Proposed algorithm

Input: `Q`, `M_bar`, `C = Centralizer(Q, M_bar)`.

Output: list of complement class reps.

```
1. Build phi: Q → Aut(M_bar):
   - gensT := SmallGeneratingSet(M_bar)
   - for each generator q of Q, compute the automorphism m ↦ qmq⁻¹ restricted to M_bar
   - Use IsomorphismPermGroup(AutomorphismGroup(M_bar)) to land in a permutation group
   - A := Image(phi), InnM := Image(phi, M_bar) ≅ Inn(M_bar)

2. AutReduction step: find complements of InnM in A:
   - complsInA := NonSolvableComplementClassReps(A, InnM)
     (fast because |A| ≤ |Aut(M_bar)|, typically small)
   - For each complement A_i of InnM in A, compute Base_i := phi⁻¹(A_i)
     (generated by C plus one preimage per generator of A_i)

3. For each Base_i:
   - Compute a section s: A_i → Base_i (explicit preimages of A_i generators,
     stored as a lookup table indexed by A_i elements).
   - Enumerate Hom(C, M_bar) classes:
       homClasses := AllHomomorphismClasses(C, M_bar)
     This dedupes under Inn(M_bar)-conjugation on the target.

4. For each (Base_i, φ) with φ ∈ homClasses:
   - Construct Base_i^φ by generators:
       for c in generators of C, emit φ(c) · c
       for a in generators of A_i (via section s), emit s(a)
       (plus any needed cross terms — the non-abelian cocycle identity
        may need additional generators)
   - result := Group(those generators)

5. Deduplicate result list under Q-conjugation:
   - Not all (i, φ) give distinct classes: if A_i-action on Hom(C, M_bar)
     is non-trivial, orbits of φ under that action collapse.
   - For each pair (i, i'), compute RepresentativeAction(Q, K_iφ, K_i'ψ)
     to detect conjugacy. Group into classes.

6. Return the class reps.
```

### Open subtleties (flagged for implementation)

- **Step 4 cocycle correction.** When `A_i` acts non-trivially on `M_bar`
  (i.e., `A_i` isn't inside `Inn(M_bar)`), the simple "emit `φ(c)·c`"
  construction is not a closed subgroup unless we also twist the `s(a)`
  generators. Specifically, each generator `a ∈ A_i` may need replacement
  by `τ(a) · s(a)` where `τ: A_i → M_bar` is a partial cocycle chosen
  to make the group closure correct. Working out `τ` from `φ` and the
  `A_i`-action is the crux — a page of careful group theory.

- **Step 5 dedup scope.** For `|A_i| · |Hom(C, M_bar)|` candidates across
  `i`, pairwise `RepresentativeAction(Q, ...)` is `O(n²·|Q|)` which is
  expensive for large Q. Better to compute `Q`-orbit representatives
  via invariants (abelianization, derived length, order histogram) and
  only `RepresentativeAction` within buckets, as the rest of the codebase
  already does.

- **`A_i`-action on `Hom(C, M_bar)`.** For each `a ∈ A_i`, there's an
  induced action on `Hom(C, M_bar)`:
  `(a · φ)(c) = a(φ(a⁻¹ · c · a))` where `A_i` acts on `C` by conjugation
  (which is via the normalizer structure inside `Q`). Computing orbits
  of `Hom(C, M_bar)` classes under this action gives the true count of
  twisted complements per `Base_i`.

---

## Implementation notes

### Where to place the new function

Add `GeneralAutHomComplements(Q, M_bar, C_Q_M)` adjacent to the existing
helpers in `lifting_algorithm.g`. Gate the integration behind a flag:

```gap
if not IsBound(USE_GENERAL_AUT_HOM) then
    USE_GENERAL_AUT_HOM := true;
fi;
```

### Integration in the complement-finding logic

Current code path (simplified, `lifting_algorithm.g:1211-1290`):

```
if Size(C) = idx and Size(Intersection(C, M_bar)) = 1 then
    # direct-product fast path
    if Gcd = 1   → return [C]
    elif USE_HOM_CENTRALIZER_PATH → return HomBased(C, M_bar)
    else fall through
fi;
# AutReduction path
_autResult := NonAbelianComplementsViaAut(Q, M_bar, C);
if _autResult <> fail then return _autResult; fi;
# CCR
if idx <= 120 then try CCR; fi;
# NSCR fallback (slow)
return NonSolvableComplementClassReps(Q, M_bar);
```

Proposed addition: between the direct-product check and AutReduction, insert

```gap
if USE_GENERAL_AUT_HOM then
    result := GeneralAutHomComplements(Q, M_bar, C);
    if result <> fail then
        return result;
    fi;
fi;
```

This covers both the `|C| = idx` case (subsumes `HomBasedCentralizerComplements`,
since when `r = 1` the formula reduces to the Hom-only enumeration) and
the `|C| < idx` case.

### Graceful fallback

Have `GeneralAutHomComplements` return `fail` on:
- `|A|` too large for `NonSolvableComplementClassReps(A, InnM)` to
  complete quickly (e.g., `|Aut(M_bar)|` > 10⁵ — shouldn't happen for
  M_bar ≤ A_8).
- `AllHomomorphismClasses(C, M_bar)` returning a warning about "many
  generators" combined with timeout (defensive; see testing below).

Tests should confirm the fallback never triggers in practice on the S18
affected combos.

---

## Testing strategy

### Unit tests (small constructed Q)

1. **Direct product sanity** (`|C| = idx`): verify `GeneralAutHomComplements`
   matches `HomBasedCentralizerComplements` on cases like `A_5 × C_2`,
   `A_6 × (C_2 × C_2)`, `A_8 × C_2`.

2. **Non-direct-product with `gcd = 1`** (existing AutReduction handles this):
   verify match on cases like `S_5` (which is `A_5 ⋊ C_2` with
   `C_{S_5}(A_5) = 1`, `gcd(1, 60) = 1`, expect a single complement).

3. **Non-direct-product with `gcd > 1`** (the new territory): verify
   match with NSCR on cases like `A_5 ≀ C_2` (action non-trivial,
   centralizer non-trivial). Expected to have more complements than
   AutReduction alone.

### Regression suite

Re-run S2–S10 with the new flag enabled; counts must match the
pre-existing verified totals (known from `LIFT_CACHE`).

### S18 regression

The S18 bugfix rerun (current work) produces our new ground truth.
After `GeneralAutHomComplements` is enabled, re-run the 12K affected
combos; all counts should match (faster but same numbers).

---

## Expected performance

- `|A|` and `|Aut(M_bar)|`: both small (≤ 40320 for A_8 → S_8 pair).
  `NonSolvableComplementClassReps(A, InnM)` on small `A` takes < 1s.
- `AllHomomorphismClasses(C, M_bar)`: the dominant cost. For `M_bar` small
  (360 to 20160) and "reasonable" `C` (a few generators), takes ms.
  For pathological `C` with many generators (e.g. `C_3^5 × D_8`), takes
  20+s — still an order of magnitude better than NSCR's minutes.
- Dedup across `(i, φ)` candidates: with `r` typically ≤ 5 and `|Hom|`
  typically ≤ 50, candidate count ≤ 250. Even `O(n²)` dedup via
  `RepresentativeAction` is manageable if the groups are small. For
  large Q, use invariant bucketing first.

**Expected overall speedup on the 12K affected combos**: 10–30× aggregate
runtime reduction, assuming the non-direct-product case dominates the
tail (as observed in W501 logs where single parents took 357s in NSCR).

---

## References

- Holt, D. F. *The computation of subgroups of the alternating and symmetric groups.* (Conceptual framework for Aut-reduction.)
- Serre, J.-P. *Cohomologie Galoisienne* (non-abelian H¹ framework).
- Eick & Leedham-Green, *On the construction of groups with prescribed properties* (GAP algorithm details for `AllHomomorphismClasses`, `ComplementClassesRepresentatives`).
- `lifting_algorithm.g` lines 422-485 (`NonAbelianComplementsViaAut`) and
  487-520 (`HomBasedCentralizerComplements`) — existing special cases.
