# H^1 Cache Fix and Improvement Opportunities

## Date: 2026-02-02

## Summary

Successfully fixed the H^1 cohomology cache to prevent false cache hits. The cache is now re-enabled and produces correct results (S8: 296 conjugacy classes).

---

## Part 1: Cache Fix Implementation

### Problem

The H^1 cache was disabled because it caused incorrect results (S8 returning 290-294 instead of 296). The root cause was that the cache fingerprint didn't uniquely identify modules when they had different ambient contexts.

### Root Cause Analysis

The original fingerprint in `ComputeModuleFingerprint` included:
- `p` (prime)
- `dimension`
- `Size(module.group)`
- `matrices` (full matrix data)

But was **missing**:
- `preimageGens` - the elements used by `CocycleToComplement` to convert cocycle vectors to complements
- `module.generators` - the generators of the acting group G
- `ambientGroup` identity - to distinguish different quotient groups

**Collision scenario**: Two different quotient groups Q1/M1 and Q2/M2 with:
- Identical abstract module structure (same matrices)
- Different `preimageGens` (different elements in their ambient groups)

When a cache hit occurred, the cached H^1 representatives were interpreted using the wrong `preimageGens`, producing incorrect complements.

### Fix Applied

Modified `ComputeModuleFingerprint` in `cohomology.g` (lines 95-148) to include:

```gap
ComputeModuleFingerprint := function(module)
    local matrixFingerprint, mat, contextFingerprint, gen, gensFingerprint, g;

    # Include full matrix data (existing)
    matrixFingerprint := [];
    for mat in module.matrices do
        Add(matrixFingerprint, List(mat, row -> List(row, x -> IntFFE(x))));
    od;

    # CRITICAL FIX: Include preimageGens identity
    contextFingerprint := [];
    if IsBound(module.preimageGens) then
        for gen in module.preimageGens do
            if IsPerm(gen) then
                Add(contextFingerprint, ListPerm(gen, LargestMovedPoint(gen)));
            else
                Add(contextFingerprint, String(gen));
            fi;
        od;
    fi;

    if IsBound(module.ambientGroup) then
        Add(contextFingerprint, Size(module.ambientGroup));
        # Also add IdGroup if available for small groups
        if Size(module.ambientGroup) <= 2000 and Size(module.ambientGroup) <> 1024 then
            Add(contextFingerprint, IdGroup(module.ambientGroup));
        fi;
    fi;

    # Include module.generators identity for extra uniqueness
    gensFingerprint := [];
    for g in module.generators do
        if IsPerm(g) then
            Add(gensFingerprint, ListPerm(g, LargestMovedPoint(g)));
        else
            Add(gensFingerprint, String(g));
        fi;
    od;

    return Concatenation(
        String(module.p), "_",
        String(module.dimension), "_",
        String(Size(module.group)), "_",
        String(matrixFingerprint), "_",
        String(contextFingerprint), "_",
        String(gensFingerprint)
    );
end;
```

### Verification

| Test | Cache Disabled | Cache Enabled (Fixed) | Expected |
|------|---------------|----------------------|----------|
| S8   | 296           | 296                  | 296      |

Cache statistics after fix:
- Cache entries: 110
- Cache hits: 65 (25% hit rate)
- All results correct

---

## Part 2: H^1 Method Success/Failure Analysis

### Overall Statistics (S8 Test)

| Metric | Value | Percentage |
|--------|-------|------------|
| H^1 method calls | 255 | 100% |
| Cache hits | 65 | 25% |
| Fallback to GAP | 85 | 33% |
| Successful fresh computations | ~105 | ~41% |

### Failure Breakdown by Function

#### `ChiefFactorAsModule` Failures (~80% of fallbacks)

Location: `modules.g` lines 35-228

**Failure points:**

1. **Line 94-97**: Non-split extension (no complements exist)
   ```gap
   if Length(baseComplements) = 0 then
       return fail;
   fi;
   ```

2. **Line 124**: Isomorphism construction fails
   ```gap
   if phi <> fail and IsBijective(phi) then
       # ... use inverse mapping
   fi;
   ```

3. **Line 133**: Preimage verification fails
   ```gap
   if ForAll(gens_Q, q -> q <> fail and q in baseComplement) then
       found := true;
   ```

4. **Line 199-202**: Generators insufficient
   ```gap
   if Length(gens_G) = 0 or Size(Group(gens_G)) < Size(G) then
       return fail;
   fi;
   ```

#### `EnumerateComplementsFromH1` Failures (~20% of fallbacks)

Location: `modules.g` lines 444-479

**Failure points:**

1. **Line 454-458**: Wrong order
   ```gap
   if Size(C) * Size(complementInfo.M_bar) <> Size(complementInfo.Q) then
       invalidCount := invalidCount + 1;
   ```

2. **Line 461-465**: Not a complement (non-trivial intersection)
   ```gap
   if Size(Intersection(C, complementInfo.M_bar)) > 1 then
       invalidCount := invalidCount + 1;
   ```

**Observed invalid complements in S8:**
- Partition [6,2]: 2 invalid
- Partition [4,4]: 4 invalid
- Partition [3,3,2]: 2 invalid

---

## Part 3: Improvement Opportunities

### 3.1 `ChiefFactorAsModule` Improvements

#### Issue: Pcgs Correspondence Often Fails

The function tries to use `Pcgs(G)` as module generators via inverse mapping, but this frequently fails when:
- The isomorphism `phi` cannot be constructed
- The inverse mapping produces invalid preimages

**Proposed Fix**: Add alternative generator correspondence methods

```gap
# After the Pcgs approach fails (line 141), try alternative methods:

# Alternative 1: Use SmallGeneratingSet of G directly
if not found then
    smallGens := SmallGeneratingSet(G);
    if Length(smallGens) > 0 then
        # Try to find preimages via enumeration
        for g in smallGens do
            preimg := First(Elements(baseComplement), c -> Image(hom, c) = g);
            if preimg <> fail then
                Add(gens_Q, preimg);
                Add(gens_G, g);
            fi;
        od;
        if Length(gens_G) > 0 and Size(Group(gens_G)) = Size(G) then
            found := true;
        fi;
    fi;
fi;

# Alternative 2: Use the complement's generators directly (current fallback)
# but verify they generate G before accepting
```

#### Issue: Generator Filtering Removes Too Many

Lines 154-163 remove trivial generators, but this can leave insufficient generators.

**Proposed Fix**: More careful generator selection

```gap
# Instead of filtering out all trivial generators, ensure we keep enough
# to generate G. Use a greedy approach:
newGensQ := [];
newGensG := [];
currentGen := TrivialSubgroup(G);
for i in [1..Length(gens_Q)] do
    if not gens_G[i] in currentGen then
        Add(newGensQ, gens_Q[i]);
        Add(newGensG, gens_G[i]);
        currentGen := ClosureGroup(currentGen, gens_G[i]);
        if Size(currentGen) = Size(G) then
            break;
        fi;
    fi;
od;
```

### 3.2 `EnumerateComplementsFromH1` Improvements

#### Issue: Invalid Complements from Cocycle Conversion

The `CocycleToComplement` function sometimes produces groups that aren't actual complements. This indicates a bug in the cocycle-to-section formula.

**Investigation needed:**

1. **Check action convention**: The cocycle identity `f(gh) = f(g)^h + f(h)` assumes a specific action convention (left vs right). Verify consistency with `ComputeCocycleOnWordViaPcgs`.

2. **Verify tail-action handling**: In `ComputeCocycleOnWordViaPcgs` (cohomology.g lines 403-463), the "tail action" computation might have edge cases.

3. **Add diagnostic logging**:
```gap
CocycleToComplement := function(cocycle, complementInfo)
    # ... existing code ...

    # Add verification before returning
    C := Group(gens);
    if Size(Intersection(C, complementInfo.M_bar)) > 1 then
        # Log detailed diagnostics
        Print("Invalid complement from cocycle: ", cocycle, "\n");
        Print("  preimageGens: ", complementInfo.preimageGens, "\n");
        Print("  Intersection size: ", Size(Intersection(C, complementInfo.M_bar)), "\n");
    fi;
    return C;
end;
```

### 3.3 Caching Improvements

#### Current Performance
- 25% cache hit rate
- 110 cache entries for S8

#### Potential Improvements

1. **Cache at `ComplementClassesRepresentatives` level**: Cache the actual complement subgroups, not just H^1 results. This would benefit fallback calls too.

2. **Precompute common cases**: For frequently occurring module types (e.g., S_k acting on C_2^k by permutation), precompute and cache H^1 at load time.

3. **Cache normalization**: Canonicalize the fingerprint by sorting generators, which might increase hit rates for isomorphic modules.

### 3.4 Performance Optimization Ideas

1. **Avoid `ComplementClassesRepresentatives` call in `ChiefFactorAsModule`**: Line 92 calls GAP's complement enumeration just to get ONE base complement. This is expensive. Could use:
   - `Complementclasses` with early termination
   - Direct construction for common cases (e.g., semidirect products)

2. **Batch processing**: When processing multiple subgroups through the same chief layer, batch the H^1 computations.

3. **Parallel complement enumeration**: For partitions with multiple components, enumerate complements in parallel.

---

## Part 4: Files Modified

### `cohomology.g`
- Lines 76-82: Updated cache documentation
- Line 82: `H1_CACHE_ENABLED := true` (re-enabled)
- Lines 95-148: Improved `ComputeModuleFingerprint` with context fingerprinting

---

## Part 5: Testing

### Verification Commands

```bash
# Run S8 test with cache enabled
cd C:\Users\jeffr\Downloads\Lifting
python test_h1_cache_fix.py

# Run full S2-S10 suite
python run_test.py
```

### Expected Results

| n | Expected | Status |
|---|----------|--------|
| S2 | 2 | PASS |
| S3 | 4 | PASS |
| S4 | 11 | PASS |
| S5 | 19 | PASS |
| S6 | 56 | PASS |
| S7 | 96 | PASS |
| S8 | 296 | PASS |
| S9 | 554 | TBD |
| S10 | 1593 | TBD |

---

## Part 6: Next Steps

1. **Priority 1**: Investigate `CocycleToComplement` invalid complement bug
   - Add detailed logging to identify which cocycles produce invalid complements
   - Verify action convention consistency

2. **Priority 2**: Improve `ChiefFactorAsModule` generator correspondence
   - Implement alternative methods when Pcgs approach fails
   - Reduce fallback rate from 33% to <15%

3. **Priority 3**: Performance optimization for S10+
   - Profile [8,2] partition (main bottleneck)
   - Consider parallel processing for independent partitions

4. **Priority 4**: Extended caching
   - Cache complement results, not just H^1
   - Precompute common module types
