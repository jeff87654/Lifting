# Phase 3: Wreath Product Conjugacy Testing in GAP

## Project Context

This is Phase 3 of implementing Holt's algorithm for enumerating conjugacy classes of subgroups of S₁₄.

**Phase 1** implemented H¹(G, M) computations for complement enumeration.
**Phase 2** implemented orbital complement enumeration to avoid pairwise conjugacy tests during lifting.
**Phase 3** (this document) implements the final and most critical optimization: using **wreath products** instead of the full symmetric group for conjugacy testing between subdirect products.

### Why This Is the Bottleneck

From our S₈ computation, the final step was:

```
Pre-final count: 318 subgroups
Performing final conjugacy check in S8...
FINAL RESULT: 200 conjugacy classes
```

That's 318 × 317 / 2 ≈ 50,000 pairwise `IsConjugate(S₈, H₁, H₂)` calls. For S₁₄ the pre-final count will be orders of magnitude larger, and `IsConjugate` in S₁₄ (order 87 billion) uses backtrack search with potentially exponential runtime. **This is where Holt reports spending most of the computation time.**

---

## Mathematical Framework

### The Conjugacy Theorem

**Theorem (Holt, Section 3):** Let π = (n₁, n₂, ..., nₖ) be a partition of n with all parts ≥ 2. For each part nᵢ, let Hᵢ be a transitive subgroup of S_{nᵢ}. Let P = H₁ × H₂ × ... × Hₖ acting on {1, ..., n} (each Hᵢ on its own block of points).

Two subgroups of P are conjugate in Sₙ **if and only if** they are conjugate in a certain **wreath product** W that depends only on which Hᵢ are equal.

### Constructing the Wreath Product

Group the factors by equality. Suppose the distinct transitive groups appearing are G₁, G₂, ..., Gₗ with multiplicities m₁, m₂, ..., mₗ. That is:

```
P = G₁^{m₁} × G₂^{m₂} × ... × Gₗ^{mₗ}
```

where G₁^{m₁} means m₁ copies of G₁ on disjoint domains of size deg(G₁).

The wreath product is:

```
W = (S_{deg(G₁)} ≀ S_{m₁}) × (S_{deg(G₂)} ≀ S_{m₂}) × ... × (S_{deg(Gₗ)} ≀ S_{mₗ})
```

where S_d ≀ S_m is the **imprimitive wreath product** acting on d·m points.

### What the Wreath Product Does

The wreath product S_d ≀ S_m consists of:
- m independent copies of S_d (permuting within each block) — the **base group**
- S_m permuting the m blocks among themselves — the **top group**

So conjugacy in W allows:
1. Arbitrary relabeling within each block (S_d part)
2. Permuting identical blocks (S_m part)

This is exactly what Sₙ-conjugacy reduces to when the blocks have identical transitive groups.

### Why This Helps: Size Comparison

For the partition [2,2,2,2,2,2,2] of 14 (all C₂):

```
|S₁₄| = 87,178,291,200
|S₂ ≀ S₇| = (2^7) · 7! = 128 · 5040 = 645,120
```

That's a factor of 135,000× smaller. Backtrack search in W is dramatically faster.

For mixed partitions like [4,4,3,3] with (S₄, S₄, S₃, S₃):

```
|S₁₄| = 87,178,291,200
|(S₄ ≀ S₂) × (S₃ ≀ S₂)| = (24² · 2) · (6² · 2) = 1152 · 72 = 82,944
```

---

## Implementation Specification

### Data Structures

```gap
# A partition-with-groups record
PartitionRecord := rec(
    partition,          # e.g. [4, 4, 3, 3]
    transitive_groups,  # e.g. [S4, S4, S3, S3] (as permutation groups)
    domains,            # e.g. [[1..4], [5..8], [9..11], [12..14]]
    grouped_factors,    # e.g. [ rec(group := S4, degree := 4, multiplicity := 2,
                        #             indices := [1, 2]),
                        #         rec(group := S3, degree := 3, multiplicity := 2,
                        #             indices := [3, 4]) ]
);

# The wreath product ambient for conjugacy testing
WreathAmbientRecord := rec(
    partition_record,   # the PartitionRecord
    wreath_product,     # the full wreath product W as a permutation group
    component_wreaths,  # list of individual S_d ≀ S_m components
    embedding_maps,     # how to embed subdirect products of P into W
    point_mapping       # how points in [1..n] correspond to wreath product points
);
```

### Function 1: Group Factors by Equality

Two transitive groups are "equal" for this purpose if they are conjugate in S_d (i.e., the same transitive group up to relabeling). Since we're pulling from `AllTransitiveGroups`, we can use the transitive group ID.

```gap
# Input: List of transitive permutation groups, one per partition part
# Output: Grouped factors with multiplicities

GroupFactorsByEquality := function(trans_groups, degrees)
    local grouped, i, found, j, entry;
    
    grouped := [];
    
    for i in [1..Length(trans_groups)] do
        found := false;
        
        for j in [1..Length(grouped)] do
            entry := grouped[j];
            # Two transitive groups of the same degree are "equal"
            # iff they have the same TransitiveIdentification
            if degrees[i] = entry.degree and
               TransitiveIdentification(trans_groups[i]) = entry.trans_id then
                Add(entry.indices, i);
                entry.multiplicity := entry.multiplicity + 1;
                found := true;
                break;
            fi;
        od;
        
        if not found then
            Add(grouped, rec(
                group := trans_groups[i],
                degree := degrees[i],
                trans_id := TransitiveIdentification(trans_groups[i]),
                multiplicity := 1,
                indices := [i]
            ));
        fi;
    od;
    
    return grouped;
end;
```

### Function 2: Construct the Wreath Product

```gap
# Input: Grouped factors from GroupFactorsByEquality
# Output: WreathAmbientRecord

ConstructWreathAmbient := function(grouped_factors, partition, domains)
    local components, total_degree, offset, component, d, m, W_component,
          full_wreath, point_map, c, i, j, block_start;
    
    components := [];
    total_degree := 0;
    point_map := [];  # Maps original points to wreath product points
    
    for c in grouped_factors do
        d := c.degree;       # degree of each factor
        m := c.multiplicity; # number of copies
        
        if m = 1 then
            # No wreath needed: just S_d acting on d points
            W_component := SymmetricGroup(d);
        else
            # Imprimitive wreath product S_d ≀ S_m on d*m points
            W_component := WreathProduct(SymmetricGroup(d), SymmetricGroup(m));
        fi;
        
        # Shift to act on [offset+1 .. offset+d*m]
        # Record point mapping: 
        # Original domain[c.indices[j]] maps to block j of this component
        for j in [1..m] do
            for i in [1..d] do
                # Original point: domains[c.indices[j]][i]
                # Wreath point: offset + (j-1)*d + i
                point_map[domains[c.indices[j]][i]] := 
                    total_degree + (j-1)*d + i;
            od;
        od;
        
        Add(components, rec(
            wreath := W_component,
            degree := d,
            multiplicity := m,
            total_points := d * m,
            offset := total_degree,
            factor_info := c
        ));
        
        total_degree := total_degree + d * m;
    od;
    
    # Build the full wreath as direct product of components
    # Each component acts on its own set of points
    if Length(components) = 1 then
        full_wreath := components[1].wreath;
    else
        full_wreath := DirectProduct(List(components, c -> c.wreath));
    fi;
    
    return rec(
        partition_record := rec(
            partition := partition,
            domains := domains,
            grouped_factors := grouped_factors
        ),
        wreath_product := full_wreath,
        component_wreaths := components,
        point_mapping := point_map
    );
end;
```

### Function 3: Embed a Subdirect Product into the Wreath Product

Subdirect products of P live in Sₙ with the original point labeling. We need to conjugate them into the wreath product's point labeling (which groups equal factors together).

```gap
# Input: 
#   - H: a subdirect product of P, as subgroup of Sym(n)
#   - wreath_ambient: WreathAmbientRecord
# Output:
#   - H embedded in the wreath product's coordinate system

EmbedInWreath := function(H, wreath_ambient)
    local n, point_map, perm_list, gen, new_gen, i, gens_embedded;
    
    n := Length(wreath_ambient.point_mapping);
    point_map := wreath_ambient.point_mapping;
    
    # The point_map sends original point i to wreath point point_map[i]
    # Conjugate H by this relabeling
    
    # Build the relabeling permutation
    perm_list := ListPerm(PermList(point_map), n);
    # Actually we need the permutation sigma where sigma(i) = point_map[i]
    
    gens_embedded := [];
    for gen in GeneratorsOfGroup(H) do
        # Conjugate: new_gen(point_map[i]) = point_map[gen(i)]
        new_gen := [];
        for i in [1..n] do
            new_gen[point_map[i]] := point_map[i^gen];
        od;
        Add(gens_embedded, PermList(new_gen));
    od;
    
    return Group(gens_embedded);
end;
```

**Alternatively, compute the conjugating permutation once:**

```gap
# More efficient: compute sigma once, then conjugate all subgroups by sigma

BuildRelabelingPermutation := function(wreath_ambient)
    local n, point_map;
    
    n := Length(wreath_ambient.point_mapping);
    point_map := wreath_ambient.point_mapping;
    
    return PermList(point_map);
end;

# Then for each subgroup:
# H_embedded := H ^ sigma;
# where sigma := BuildRelabelingPermutation(wreath_ambient);
```

### Function 4: Conjugacy Testing in Wreath Product

```gap
# Input:
#   - H1, H2: two subdirect products (already embedded in wreath coordinates)
#   - wreath_ambient: WreathAmbientRecord
# Output:
#   - true if H1 and H2 are conjugate in the wreath product

AreConjugateInWreath := function(H1, H2, wreath_ambient)
    local W;
    
    W := wreath_ambient.wreath_product;
    
    # Use GAP's built-in conjugacy test in W (much smaller than S_n)
    return IsConjugate(W, H1, H2);
end;
```

### Function 5: Deduplicate by Wreath Conjugacy

```gap
# Input:
#   - subgroups: list of subdirect products of P (in original Sₙ coordinates)
#   - partition: the partition
#   - trans_groups: list of transitive groups (one per part)
#   - degrees: list of degrees (= partition parts)
# Output:
#   - list of conjugacy class representatives

DeduplicateByWreath := function(subgroups, partition, trans_groups, degrees, domains)
    local grouped, wreath_ambient, sigma, embedded, representatives, 
          i, j, is_new, W;
    
    if Length(subgroups) <= 1 then
        return subgroups;
    fi;
    
    # Step 1: Group factors and build wreath product
    grouped := GroupFactorsByEquality(trans_groups, degrees);
    wreath_ambient := ConstructWreathAmbient(grouped, partition, domains);
    W := wreath_ambient.wreath_product;
    
    Print("  Wreath product order: ", Size(W), 
          " (vs S_", Sum(partition), " = ", Factorial(Sum(partition)), ")\n");
    
    # Step 2: Embed all subgroups into wreath coordinates
    sigma := BuildRelabelingPermutation(wreath_ambient);
    embedded := List(subgroups, H -> H ^ sigma);
    
    # Step 3: Pairwise conjugacy testing in W
    representatives := [embedded[1]];
    
    for i in [2..Length(embedded)] do
        is_new := true;
        for j in [1..Length(representatives)] do
            if IsConjugate(W, embedded[i], representatives[j]) then
                is_new := false;
                break;
            fi;
        od;
        if is_new then
            Add(representatives, embedded[i]);
        fi;
    od;
    
    # Step 4: Map back to original coordinates
    representatives := List(representatives, H -> H ^ (sigma^-1));
    
    Print("  Deduplicated: ", Length(subgroups), " -> ", 
          Length(representatives), " classes\n");
    
    return representatives;
end;
```

---

## Optimization: Partition the Deduplication

Different partition-group combinations produce subgroups that **cannot** be conjugate to each other. Two subdirect products of P₁ = H₁ × H₂ × ... and P₂ = H₁' × H₂' × ... can only be conjugate in Sₙ if P₁ and P₂ have the same set of factors (up to reordering equal-degree factors).

This means we should **never test conjugacy between subgroups from different direct products** (unless the products happen to be equal up to permutation of equal factors).

```gap
# Input: All subdirect products collected across all transitive group combinations
#        for a given partition
# Output: Conjugacy class representatives

DeduplicatePartition := function(all_subgroups_by_combo, partition, 
                                  all_trans_groups, all_domains)
    local equivalence_classes, i, key, combo_groups, combo_degrees,
          grouped, class_key, found, eq_class, results, 
          class_subgroups, class_trans, class_domains;
    
    # Step 1: Group combos that can possibly be conjugate
    # Two combos (H1,...,Hk) and (H1',...,Hk') can be conjugate in S_n iff
    # they have the same multiset of (degree, TransitiveIdentification) pairs
    
    equivalence_classes := [];
    
    for i in [1..Length(all_subgroups_by_combo)] do
        combo_groups := all_trans_groups[i];
        combo_degrees := partition;
        
        # Build a canonical key: sorted list of (degree, trans_id) pairs
        grouped := GroupFactorsByEquality(combo_groups, combo_degrees);
        class_key := SortedList(List(grouped, g -> 
            [g.degree, g.trans_id, g.multiplicity]));
        
        # Find or create equivalence class
        found := false;
        for eq_class in equivalence_classes do
            if eq_class.key = class_key then
                Append(eq_class.subgroups, all_subgroups_by_combo[i]);
                Add(eq_class.trans_groups_list, combo_groups);
                Add(eq_class.domains_list, all_domains[i]);
                found := true;
                break;
            fi;
        od;
        
        if not found then
            Add(equivalence_classes, rec(
                key := class_key,
                subgroups := ShallowCopy(all_subgroups_by_combo[i]),
                trans_groups_list := [combo_groups],
                domains_list := [all_domains[i]]
            ));
        fi;
    od;
    
    # Step 2: Deduplicate within each equivalence class
    results := [];
    
    for eq_class in equivalence_classes do
        # All subgroups in this class share the same factor types
        # Use wreath product conjugacy on the combined set
        class_subgroups := eq_class.subgroups;
        class_trans := eq_class.trans_groups_list[1];  
        class_domains := eq_class.domains_list[1];
        
        Append(results, DeduplicateByWreath(
            class_subgroups, partition, class_trans, 
            combo_degrees, class_domains
        ));
    od;
    
    return results;
end;
```

---

## Optimization: Invariant-Based Pre-Filtering

Before expensive `IsConjugate` calls, compute cheap invariants to quickly rule out non-conjugate pairs.

### Invariant 1: Order

```gap
# Trivial but eliminates many comparisons
OrderInvariant := function(H)
    return Size(H);
end;
```

### Invariant 2: Abelianization

```gap
AbelianizationInvariant := function(H)
    return AbelianInvariants(H);
end;
```

### Invariant 3: Orbit Structure

```gap
# The multiset of orbit lengths of H on [1..n]
OrbitStructureInvariant := function(H, n)
    return SortedList(List(Orbits(H, [1..n]), Length));
end;
```

### Invariant 4: Cycle Index / Order Profile

```gap
# Distribution of element orders in H
OrderProfileInvariant := function(H)
    local profile, cc;
    profile := [];
    for cc in ConjugacyClasses(H) do
        Add(profile, [Order(Representative(cc)), Size(cc)]);
    od;
    return SortedList(profile);
end;
```

### Using Invariants to Partition Before Conjugacy Testing

```gap
DeduplicateByWreathWithInvariants := function(subgroups, partition, 
                                               trans_groups, degrees, domains)
    local grouped, wreath_ambient, sigma, embedded, W,
          invariant_map, key, inv_classes, cls, representatives, 
          i, j, is_new, H;
    
    if Length(subgroups) <= 1 then
        return subgroups;
    fi;
    
    # Build wreath
    grouped := GroupFactorsByEquality(trans_groups, degrees);
    wreath_ambient := ConstructWreathAmbient(grouped, partition, domains);
    W := wreath_ambient.wreath_product;
    sigma := BuildRelabelingPermutation(wreath_ambient);
    embedded := List(subgroups, H -> H ^ sigma);
    
    # Compute invariants and partition
    invariant_map := rec();
    
    for i in [1..Length(embedded)] do
        H := embedded[i];
        key := [Size(H), 
                AbelianInvariants(H),
                SortedList(List(Orbits(H, MovedPoints(W)), Length))];
        key := String(key);  # Hashable
        
        if not IsBound(invariant_map.(key)) then
            invariant_map.(key) := [];
        fi;
        Add(invariant_map.(key), i);
    od;
    
    # Now only test conjugacy within same invariant class
    representatives := [];
    
    for cls in RecNames(invariant_map) do
        inv_classes := invariant_map.(cls);
        
        for i in inv_classes do
            is_new := true;
            for j in representatives do
                # Only compare if same invariant class
                if String([Size(embedded[j]), 
                           AbelianInvariants(embedded[j]),
                           SortedList(List(Orbits(embedded[j], 
                               MovedPoints(W)), Length))]) = cls then
                    if IsConjugate(W, embedded[i], embedded[j]) then
                        is_new := false;
                        break;
                    fi;
                fi;
            od;
            if is_new then
                Add(representatives, i);
            fi;
        od;
    od;
    
    # Map back
    representatives := List(representatives, i -> embedded[i] ^ (sigma^-1));
    
    return representatives;
end;
```

---

## Special Case: The Many-2s Partitions

Holt specifically calls out partitions with many parts equal to 2 as the hardest cases. For S₁₄, the partition [2,2,2,2,2,2,2] gives P = (C₂)⁷ with only one transitive group combination but **thousands of subdirect products**.

### The Structure

For k copies of C₂ on disjoint 2-element domains, the wreath product is:

```
W = S₂ ≀ Sₖ
```

acting on 2k points. This has order 2ᵏ · k!.

A subdirect product of (C₂)ᵏ that projects onto each factor is simply a subgroup H ≤ (C₂)ᵏ with the property that each coordinate projection is surjective — equivalently, none of the standard basis vectors eᵢ is in the kernel of π_i restricted to H.

**In GF(2) terms:** H corresponds to a subspace V ≤ GF(2)ᵏ such that V is not contained in any coordinate hyperplane (i.e., for each i, some vector in V has a 1 in position i).

### Conjugacy in the Wreath Product

Two such subspaces V, V' ≤ GF(2)ᵏ give conjugate subgroups iff they are related by:
- Permuting coordinates (the Sₖ part of the wreath product)
- This is just: V' = σ(V) for some σ ∈ Sₖ acting on coordinates

So **conjugacy classes = orbits of Sₖ on suitable subspaces of GF(2)ᵏ**.

This can be solved purely combinatorially:

```gap
# Enumerate subspaces of GF(2)^k that hit every coordinate
# up to Sₖ-action (coordinate permutation)

EnumerateFPFSubspacesModSymmetric := function(k)
    local V, all_subspaces, fpf_subspaces, reps, S_k, 
          sub, is_fpf, i, e_i, orbit, new_rep;
    
    V := GF(2)^k;
    S_k := SymmetricGroup(k);
    
    # Enumerate subspaces of GF(2)^k
    # (for k=7: 2^7 = 128 elements, manageable)
    
    all_subspaces := [];  # Use GAP's subspace enumeration
    
    # Filter for FPF: subspace must not be contained in ker(π_i) for any i
    fpf_subspaces := [];
    for sub in all_subspaces do
        is_fpf := true;
        for i in [1..k] do
            # Check if some vector in sub has nonzero i-th coordinate
            e_i := ListWithIdenticalEntries(k, Zero(GF(2)));
            e_i[i] := One(GF(2));
            if ForAll(BasisVectors(Basis(sub)), v -> v[i] = Zero(GF(2))) then
                is_fpf := false;
                break;
            fi;
        od;
        if is_fpf then
            Add(fpf_subspaces, sub);
        fi;
    od;
    
    # Now find orbits of S_k acting on fpf_subspaces by coordinate permutation
    # Represent each subspace by its canonical form (row echelon, 
    # lexicographically smallest under coordinate permutation)
    
    reps := [];
    # ... orbit computation ...
    
    return reps;
end;
```

### Canonical Form for Subspaces

The most efficient approach for the many-2s case is to compute a **canonical form** for each subspace under coordinate permutation, then group by canonical form.

```gap
# Canonical form of a subspace of GF(2)^k under Sₖ action
# = the lexicographically smallest row echelon form over all 
#   coordinate permutations

CanonicalSubspace := function(basis_vectors, k)
    local best, perm, permuted_basis, echelon, S_k;
    
    # For small k, try all permutations (k! is manageable for k ≤ 7)
    # For larger k, use a smarter canonical form algorithm
    
    S_k := SymmetricGroup(k);
    best := fail;
    
    for perm in S_k do
        # Permute coordinates
        permuted_basis := List(basis_vectors, v -> 
            List([1..k], i -> v[i^(perm^-1)]));
        
        # Row reduce
        echelon := SemiEchelonMat(permuted_basis * One(GF(2)));
        
        if best = fail or echelon.vectors < best then
            best := echelon.vectors;
        fi;
    od;
    
    return best;
end;
```

**Performance note:** For k = 7, |S₇| = 5040. With ~29,000 subspaces to filter and canonicalize, this is 5040 × 29000 ≈ 146M operations — feasible but not instant. A smarter canonical form using nauty-style partition refinement on the bipartite graph (rows × columns) would be faster.

---

## The General k-Factor Case

For partitions with k ≥ 3 factors of mixed types, the approach is:

### Step 1: Collect All Subdirect Products by Combination

```gap
# For partition [4, 4, 3, 3], we enumerate:
# - All pairs (H1, H2) of transitive degree-4 groups
# - All pairs (H3, H4) of transitive degree-3 groups
# - For each (H1, H2, H3, H4), find subdirect products of H1 × H2 × H3 × H4
```

### Step 2: Group Combinations with Same Factor Multiset

```gap
# (S4, S4, S3, A3) and (S4, S4, A3, S3) have the same multiset
# They share a wreath product: (S₄ ≀ S₂) × S₃ × S₃
# (the two S₃ and A₃ are NOT equal so no wreath for them)
#
# But (S4, S4, S3, S3) has wreath: (S₄ ≀ S₂) × (S₃ ≀ S₂)
# (both pairs are equal, so both get wreath treatment)
```

### Step 3: Deduplicate Within Each Group

Use wreath product conjugacy testing within each group of combinations sharing the same factor multiset.

### Step 4: Final Cross-Partition Check

After processing all partitions, there's **no cross-partition deduplication needed**. Two FPF subgroups with different orbit-length partitions cannot be conjugate in Sₙ (conjugation preserves orbit structure).

However, within a single partition like [4,4,3,3], subgroups from the combination (S₄, A₄, S₃, S₃) could potentially be conjugate to subgroups from (A₄, S₄, S₃, S₃) — this is exactly what the wreath product's "swap" action detects.

---

## Integration with the Full Pipeline

```gap
EnumerateFPFClassesSn := function(n)
    local S_n, partitions, all_classes, p, degrees, trans_groups_per_degree,
          combos, combo, domains, offset, k, subdirects_by_combo, 
          trans_by_combo, domains_by_combo, partition_classes;
    
    S_n := SymmetricGroup(n);
    partitions := Filtered(Partitions(n), p -> ForAll(p, x -> x > 1));
    all_classes := [];
    
    for p in partitions do
        Print("\n=== Partition ", p, " ===\n");
        
        degrees := p;
        trans_groups_per_degree := List(degrees, 
            d -> AllTransitiveGroups(NrMovedPoints, d));
        combos := Cartesian(trans_groups_per_degree);
        
        subdirects_by_combo := [];
        trans_by_combo := [];
        domains_by_combo := [];
        
        for combo in combos do
            # Build shifted groups on disjoint domains
            offset := 0;
            domains := [];
            for k in [1..Length(combo)] do
                Add(domains, [offset + 1 .. offset + degrees[k]]);
                offset := offset + degrees[k];
            od;
            
            # Find subdirect products (Phase 1/2 or brute force)
            local subs := FindSubdirectProducts(combo, domains);
            
            if Length(subs) > 0 then
                Add(subdirects_by_combo, subs);
                Add(trans_by_combo, combo);
                Add(domains_by_combo, domains);
            fi;
        od;
        
        # Phase 3: Wreath-based deduplication across all combos for this partition
        partition_classes := DeduplicatePartition(
            subdirects_by_combo, p, trans_by_combo, domains_by_combo);
        
        Print("  Partition ", p, ": ", Length(partition_classes), " classes\n");
        Append(all_classes, partition_classes);
    od;
    
    Print("\n=== TOTAL FPF classes of S", n, ": ", Length(all_classes), " ===\n");
    return all_classes;
end;
```

---

## Test Cases

### Test 1: S₈ Verification

We know the correct answer is 200 FPF classes. Run the wreath-based algorithm and compare.

```gap
TestS8 := function()
    local result;
    result := EnumerateFPFClassesSn(8);
    if Length(result) <> 200 then
        Error("Expected 200, got ", Length(result));
    fi;
    Print("PASS: S8 has 200 FPF classes\n");
end;
```

### Test 2: Wreath vs Full Symmetric for [4,4]

```gap
TestWreathVsSymmetric := function()
    local p, combos, domains, subs, t1, t2, result1, result2, 
          S8, W;
    
    p := [4, 4];
    # ... build subdirects for S4 x S4 combo ...
    
    S8 := SymmetricGroup(8);
    W := WreathProduct(SymmetricGroup(4), SymmetricGroup(2));
    
    t1 := Runtime();
    result1 := RemoveConjugateDuplicates(subs, S8);
    t1 := Runtime() - t1;
    
    t2 := Runtime();
    result2 := DeduplicateByWreath(subs, p, [S4, S4], [4, 4], domains);
    t2 := Runtime() - t2;
    
    Print("S8 method: ", Length(result1), " classes in ", t1, "ms\n");
    Print("Wreath method: ", Length(result2), " classes in ", t2, "ms\n");
    
    if Length(result1) <> Length(result2) then
        Error("Mismatch!");
    fi;
end;
```

### Test 3: Many-2s Case [2,2,2,2] in S₈

```gap
TestMany2s := function()
    local p, C2, subs, result_wreath, result_S8;
    
    p := [2, 2, 2, 2];
    # Build (C2)^4 subdirects
    # ...
    
    # Wreath: S2 ≀ S4, order 2^4 * 24 = 384
    # vs S8: order 40320
    
    # Compare results and timing
end;
```

### Test 4: Cross-Combo Conjugacy Detection

Verify that two subgroups from different combinations (e.g., (S₄, A₄) and (A₄, S₄) in partition [4,4]) are correctly detected as conjugate when the wreath product swaps the two blocks.

```gap
TestCrossComboConjugacy := function()
    local S4, A4, H1, H2, sigma, W;
    
    # H1 = S4 on {1,2,3,4} × A4 on {5,6,7,8}: diagonal via sign homomorphism
    # H2 = A4 on {1,2,3,4} × S4 on {5,6,7,8}: same diagonal, swapped
    
    # These should be conjugate in S4 ≀ S2 (which can swap the blocks)
    # but NOT if we only test in S4 × S4
    
    W := WreathProduct(SymmetricGroup(4), SymmetricGroup(2));
    # ... construct H1, H2, test ...
end;
```

---

## Performance Targets

| Partition | # Subdirects | Wreath Order | S₁₄ Order | Expected Speedup |
|-----------|-------------|--------------|-----------|------------------|
| [2,2,2,2,2,2,2] | ~29,000 | 645,120 | 8.7×10¹⁰ | 100x+ |
| [4,4,3,3] | ~500 | 82,944 | 8.7×10¹⁰ | 1000x+ |
| [7,7] | ~3 | 10,080 | 8.7×10¹⁰ | ∞ (trivial either way) |
| [4,2,2,2,2,2] | ~2000 | 15,360 | 8.7×10¹⁰ | 500x+ |
| [3,3,2,2,2,2] | ~100 | 41,472 | 8.7×10¹⁰ | 200x+ |

The biggest win is on partitions with many repeated parts and many subdirect products. The [2,2,2,2,2,2,2] partition is the single hardest case for S₁₄.

---

## Potential Further Optimizations

### 1. Canonical Representatives via nauty/bliss

Instead of O(n²) pairwise `IsConjugate` calls, compute a canonical form for each subgroup under the wreath action using a graph isomorphism tool. Two subgroups are conjugate iff they have the same canonical form.

GAP's `GRAPE` package or external calls to `nauty`/`bliss` can do this. Encode the subgroup as a colored graph and compute the canonical labeling.

### 2. Batch Processing with Stabilizer Chains

Compute the stabilizer chain of W once, then use it for all conjugacy tests. GAP's backtrack for `IsConjugate` rebuilds internal structures each call — batching amortizes this.

### 3. Hash-Based Bucketing

Before any `IsConjugate` calls, hash subgroups by cheap invariants (order, abelianization, orbit structure, element order distribution). Only test conjugacy within same hash bucket.

### 4. The images Package

GAP's `images` package by Christopher Jefferson provides `MinimalImage` for permutation groups acting on sets/partitions. This can compute canonical forms for subgroups under wreath product action much faster than pairwise testing.

```gap
LoadPackage("images");
# MinimalImage(W, H, OnSets) or similar
# This would replace all pairwise testing with a single canonical form per subgroup
```

---

## Files to Create/Modify

```
gap/
├── cohomology.g          # Phase 1
├── modules.g             # Phase 1
├── complements.g         # Phase 1
├── h1_action.g           # Phase 2
├── h1_orbits.g           # Phase 2
├── wreath_construct.g    # NEW: Build wreath products for partitions
├── wreath_conjugacy.g    # NEW: Conjugacy testing in wreath products
├── wreath_canonical.g    # NEW: Canonical forms (optional, advanced)
├── invariants.g          # NEW: Cheap subgroup invariants for pre-filtering
├── many_twos.g           # NEW: Specialized handler for (C₂)ᵏ partitions
├── goursat.g             # 2-factor handler (from earlier discussion)
├── lifting.g             # Full lifting algorithm
├── subdirect.g           # Subdirect product enumeration
└── enumerate_sn.g        # Main driver
```

---

## Success Criteria for Phase 3

- [ ] `GroupFactorsByEquality` correctly identifies equal transitive groups
- [ ] `ConstructWreathAmbient` builds the correct wreath product with proper point mapping
- [ ] `EmbedInWreath` correctly conjugates subgroups into wreath coordinates
- [ ] `DeduplicateByWreath` produces same class count as `RemoveConjugateDuplicates` in Sₙ
- [ ] S₈ full enumeration returns 200 with wreath method
- [ ] 10x+ speedup over naive Sₙ conjugacy for partitions with repeated parts
- [ ] [2,2,2,2] partition of S₈ runs in < 1 second with wreath method
- [ ] Can handle [2,2,2,2,2,2,2] partition of S₁₄ (the hardest case)

---

## References

1. **Holt, D.F.** "Enumerating subgroups of the symmetric group." *Contemporary Mathematics*, 2010.
   - Section 3: The wreath product conjugacy framework
   - Section 6: Specialized techniques for partitions with part 2

2. **Dixon, J.D. and Mortimer, B.** *Permutation Groups.* Springer, 1996.
   - Chapter 2.6: Wreath products

3. **Jefferson, C.** The `images` package for GAP.
   - Canonical images of objects under group actions
   - https://gap-packages.github.io/images/

4. **McKay, B. and Piperno, A.** nauty and Traces.
   - Graph canonical labeling for subgroup canonicalization
   - https://pallini.di.uniroma1.it/
