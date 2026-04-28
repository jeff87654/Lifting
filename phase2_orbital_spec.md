# Phase 2: Orbital Complement Enumeration in GAP

## Project Context

This is Phase 2 of implementing Holt's algorithm for enumerating conjugacy classes of subgroups of S₁₄. 

**Phase 1** (prerequisite) implemented H¹(G, M) computations - given a group G acting on an elementary abelian p-group M, we can compute the vector space H¹(G, M) whose elements correspond to complements of M in M ⋊ G.

**Phase 2** (this document) implements the key optimization: instead of enumerating all complements and testing conjugacy (expensive), we compute **orbits** of the normalizer action on H¹ directly. Each orbit corresponds to one conjugacy class of complements.

---

## The Problem Phase 2 Solves

### Naive Approach (What We Want to Avoid)

```gap
# BAD: Enumerate all H¹ elements, build complements, test conjugacy pairwise
all_complements := [];
for f in EnumerateAllCocycles(H1) do
    Add(all_complements, CocycleToComplement(f));
od;
# Now test O(n²) pairs for conjugacy - SLOW!
classes := RemoveConjugateDuplicates(all_complements, ambient_group);
```

For large H¹ (which can have p^k elements for significant k), this is infeasible.

### Holt's Insight

Two complements Gf and Gf' are conjugate in the ambient group **if and only if** the cocycles f and f' are in the same orbit under a certain group action on H¹.

**Key observation:** The action on H¹ is **linear** (it's a vector space over 𝔽ₚ), so we can represent it by matrices and use efficient linear algebra / permutation group methods.

---

## Mathematical Background

### Setup

We have:
- G acting on elementary abelian p-group M ≅ (ℤ/pℤ)ⁿ
- The semidirect product E = M ⋊ G
- Complements to M in E, classified by H¹(G, M)

### The Normalizer Action

Let N = N_E(M) be the normalizer of M in E. Since M is normal in E, we have N = E, but what matters is how elements of E act on complements.

For any complement Gf = {(f(g), g) : g ∈ G} and any element (m, 1) ∈ M, conjugation gives:

```
(m, 1)⁻¹ · (f(g), g) · (m, 1) = (-m, 1) · (f(g), g) · (m, 1)
                                = (-m + f(g) + mᵍ, g)
                                = (f(g) + mᵍ - m, g)
                                = (f(g) + δm(g), g)
```

where δm(g) = mᵍ - m is the coboundary associated to m.

**Conclusion:** Conjugation by (m, 1) sends the cocycle f to f + δm. Since δm ∈ B¹(G, M), this shows that **cocycles differing by a coboundary give conjugate complements**.

### The Full Action

More generally, consider conjugation by (m, h) where h ∈ G normalizes the complement structure. The action on cocycles is:

```
(f · (m,h))(g) = h⁻¹ · f(hgh⁻¹) · h + (coboundary term)
```

This is an **affine** action on Z¹(G, M), but it descends to a **linear** action on the quotient H¹(G, M) = Z¹/B¹.

### What Acts on H¹?

In the lifting context, we have:
- A subgroup S ≥ M ≥ N with M/N elementary abelian
- We're finding complements to M/N in S/N
- The relevant acting group is **N_S(M)/M** (or a subgroup thereof)

The normalizer acts on complements by conjugation, inducing a linear action on H¹(S/M, M/N).

---

## Data Structures

### From Phase 1

```gap
# GModuleRecord: represents M as a G-module
GModuleRecord := rec(
    p,              # prime
    dimension,      # n where M ≅ (ℤ/pℤ)ⁿ  
    group,          # G
    generators,     # generators of G
    matrices        # action matrices over GF(p)
);

# CohomologyRecord: H¹ computation results
CohomologyRecord := rec(
    module,
    cocycle_space,      # Z¹ as vector space
    coboundary_space,   # B¹ as vector space
    H1_dimension,
    H1_basis            # cocycle representatives for H¹
);
```

### New for Phase 2

```gap
# Represents the action of a group on H¹
H1ActionRecord := rec(
    cohomology,         # the CohomologyRecord
    acting_group,       # group acting on H¹ (typically normalizer quotient)
    acting_generators,  # generators of acting_group
    action_matrices,    # matrices over GF(p) giving action on H¹
                        # dimension = H1_dimension × H1_dimension
    permutation_rep     # optional: if |H¹| is small, explicit permutation action
);

# Orbit computation results
OrbitRecord := rec(
    H1_action,          # the H1ActionRecord
    num_orbits,         # number of orbits
    orbit_reps,         # representative cocycles, one per orbit
    orbit_sizes         # size of each orbit
);
```

---

## Functions to Implement

### Function 1: Compute Action on Cocycles

First, we need to compute how an element x of the normalizer acts on the cocycle space Z¹.

```gap
# Input: 
#   - module: GModuleRecord for G acting on M
#   - x: an element that normalizes G and M (lives in some overgroup)
#   - cocycle: a vector in Z¹(G, M), represented as values on generators
# Output:
#   - the transformed cocycle f^x, also as vector in Z¹

ActionOnCocycle := function(module, x, cocycle)
    local G, gens, n, r, new_cocycle, i, g, g_conj, f_g_conj, f_g_conj_acted;
    
    G := module.group;
    gens := module.generators;
    n := module.dimension;
    r := Length(gens);
    
    # The action is: (f^x)(g) = x⁻¹ · f(x g x⁻¹) · x
    # where the outer x⁻¹...x is the M-action
    
    new_cocycle := [];
    
    for i in [1..r] do
        g := gens[i];
        
        # Compute x g x⁻¹ as word in generators
        g_conj := g ^ x;  # Conjugate in ambient group
        
        # Evaluate f on g_conj (need to express g_conj in terms of generators)
        f_g_conj := EvaluateCocycleOnElement(module, cocycle, g_conj);
        
        # Apply x-action on M to the result
        f_g_conj_acted := ApplyModuleElement(module, x, f_g_conj);
        
        Append(new_cocycle, f_g_conj_acted);
    od;
    
    return new_cocycle;
end;
```

**Critical helper - evaluate cocycle on arbitrary group element:**

```gap
# Given cocycle values on generators, compute f(g) for any g ∈ G
# Uses the cocycle identity f(gh) = f(g)^h + f(h)

EvaluateCocycleOnElement := function(module, cocycle, g)
    local G, gens, n, word, result, i, gen_index, sign, f_gen, f_gen_acted;
    
    G := module.group;
    gens := module.generators;
    n := module.dimension;
    
    # Express g as word in generators: g = g_{i1}^{e1} g_{i2}^{e2} ... g_{ik}^{ek}
    word := Factorization(G, g);  # Returns list of [index, exponent] pairs
    
    if Length(word) = 0 then
        # g is identity
        return ListWithIdenticalEntries(n, Zero(GF(module.p)));
    fi;
    
    # Use cocycle identities to compute f(g):
    # f(g h) = f(g)^h + f(h)
    # f(g^{-1}) = -f(g)^{g^{-1}}
    
    # Process word left to right, accumulating result
    result := ListWithIdenticalEntries(n, Zero(GF(module.p)));
    remaining := g;
    
    for i in [1..Length(word)] do
        # ... apply cocycle identity step by step
    od;
    
    return result;
end;
```

### Function 2: Compute Action Matrix on Z¹

```gap
# Input:
#   - module: GModuleRecord
#   - Z1_basis: basis for Z¹(G,M) from Phase 1
#   - x: normalizer element
# Output:
#   - matrix over GF(p) representing x-action on Z¹

ActionMatrixOnZ1 := function(module, Z1_basis, x)
    local p, dim_Z1, matrix, i, cocycle, transformed, coeffs;
    
    p := module.p;
    dim_Z1 := Length(Z1_basis);
    matrix := [];
    
    for i in [1..dim_Z1] do
        cocycle := Z1_basis[i];
        transformed := ActionOnCocycle(module, x, cocycle);
        
        # Express transformed cocycle in terms of Z1_basis
        coeffs := SolutionMat(Z1_basis, transformed);
        
        Add(matrix, coeffs);
    od;
    
    return TransposedMat(matrix);  # Convention: columns are images
end;
```

### Function 3: Induce Action on Quotient H¹ = Z¹/B¹

The action on Z¹ preserves B¹ (coboundaries map to coboundaries), so it induces an action on the quotient.

```gap
# Input:
#   - cohomology: CohomologyRecord from Phase 1
#   - x: normalizer element
# Output:
#   - matrix over GF(p) representing x-action on H¹

ActionMatrixOnH1 := function(cohomology, x)
    local module, Z1_basis, B1_basis, H1_basis, dim_H1, dim_B1, dim_Z1,
          Z1_action, extended_basis, quotient_map, induced_matrix,
          i, image_in_Z1, image_in_H1;
    
    module := cohomology.module;
    Z1_basis := BasisVectors(Basis(cohomology.cocycle_space));
    B1_basis := BasisVectors(Basis(cohomology.coboundary_space));
    H1_basis := cohomology.H1_basis;  # Coset representatives
    
    dim_H1 := cohomology.H1_dimension;
    dim_B1 := Length(B1_basis);
    dim_Z1 := Length(Z1_basis);
    
    # Get action on Z¹
    Z1_action := ActionMatrixOnZ1(module, Z1_basis, x);
    
    # Compute induced action on quotient
    # For each H¹ basis element, compute its image under x, then reduce mod B¹
    
    induced_matrix := [];
    
    for i in [1..dim_H1] do
        # H1_basis[i] is a cocycle representing a coset of B¹
        image_in_Z1 := H1_basis[i] * Z1_action;
        
        # Project to H¹: find the unique H1_basis element in same B¹-coset
        image_in_H1 := ProjectToH1(cohomology, image_in_Z1);
        
        Add(induced_matrix, image_in_H1);
    od;
    
    return TransposedMat(induced_matrix);
end;

# Helper: project a cocycle to its H¹ representative
ProjectToH1 := function(cohomology, cocycle)
    local B1_basis, H1_basis, dim_H1, remainder, coeffs;
    
    # Subtract off B¹ component to get canonical representative
    # ... linear algebra to find coset representative ...
    
    return coeffs;  # Coordinates in H1_basis
end;
```

### Function 4: Build Full Action Record

```gap
# Input:
#   - cohomology: CohomologyRecord
#   - normalizer_gens: generators of the group acting on H¹
# Output:
#   - H1ActionRecord

BuildH1Action := function(cohomology, normalizer_gens)
    local action_matrices, gen, mat;
    
    action_matrices := [];
    for gen in normalizer_gens do
        mat := ActionMatrixOnH1(cohomology, gen);
        Add(action_matrices, mat);
    od;
    
    return rec(
        cohomology := cohomology,
        acting_group := Group(normalizer_gens),
        acting_generators := normalizer_gens,
        action_matrices := action_matrices,
        permutation_rep := fail  # Compute lazily if needed
    );
end;
```

### Function 5: Compute Orbits on H¹

This is where we get the payoff - orbits on a vector space instead of conjugacy testing on subgroups.

```gap
# Input:
#   - H1_action: H1ActionRecord
# Output:
#   - OrbitRecord with orbit representatives

ComputeH1Orbits := function(H1_action)
    local p, dim, field, all_vectors, orbit_reps, orbit_sizes, 
          remaining, v, orbit, orb_size, gen_matrices;
    
    p := H1_action.cohomology.module.p;
    dim := H1_action.cohomology.H1_dimension;
    field := GF(p);
    gen_matrices := H1_action.action_matrices;
    
    if dim = 0 then
        # Trivial H¹: one orbit (the zero element)
        return rec(
            H1_action := H1_action,
            num_orbits := 1,
            orbit_reps := [ListWithIdenticalEntries(dim, Zero(field))],
            orbit_sizes := [1]
        );
    fi;
    
    # Strategy depends on |H¹| = p^dim
    
    if p^dim <= 10000 then
        # Small enough: enumerate all vectors and compute orbits explicitly
        return ComputeH1OrbitsExplicit(H1_action);
    else
        # Large H¹: use matrix group orbit algorithm
        return ComputeH1OrbitsMatrixGroup(H1_action);
    fi;
end;
```

**Explicit enumeration for small H¹:**

```gap
ComputeH1OrbitsExplicit := function(H1_action)
    local p, dim, field, gen_matrices, all_vectors, visited, 
          orbit_reps, orbit_sizes, v, orbit, w, img, i, mat;
    
    p := H1_action.cohomology.module.p;
    dim := H1_action.cohomology.H1_dimension;
    field := GF(p);
    gen_matrices := H1_action.action_matrices;
    
    # Enumerate all vectors in GF(p)^dim
    all_vectors := EnumerateVectorSpace(field, dim);
    visited := BlistList([1..Length(all_vectors)], []);
    
    orbit_reps := [];
    orbit_sizes := [];
    
    for v in all_vectors do
        if not visited[Position(all_vectors, v)] then
            # Start new orbit
            orbit := [v];
            visited[Position(all_vectors, v)] := true;
            
            # BFS/DFS to find full orbit
            i := 1;
            while i <= Length(orbit) do
                w := orbit[i];
                for mat in gen_matrices do
                    img := w * mat;
                    if not visited[Position(all_vectors, img)] then
                        Add(orbit, img);
                        visited[Position(all_vectors, img)] := true;
                    fi;
                od;
                i := i + 1;
            od;
            
            Add(orbit_reps, v);
            Add(orbit_sizes, Length(orbit));
        fi;
    od;
    
    return rec(
        H1_action := H1_action,
        num_orbits := Length(orbit_reps),
        orbit_reps := orbit_reps,
        orbit_sizes := orbit_sizes
    );
end;
```

**Matrix group method for large H¹:**

```gap
ComputeH1OrbitsMatrixGroup := function(H1_action)
    local p, dim, field, gen_matrices, mat_group, 
          vector_space, orbits, orbit_reps, orbit_sizes;
    
    p := H1_action.cohomology.module.p;
    dim := H1_action.cohomology.H1_dimension;
    field := GF(p);
    gen_matrices := H1_action.action_matrices;
    
    # Create matrix group in GL(dim, p)
    mat_group := Group(gen_matrices);
    
    # Use GAP's orbit algorithms for matrix groups acting on vectors
    # Key: don't enumerate all p^dim vectors!
    
    # Method 1: Use OrbitsDomain if available
    # Method 2: Random sampling + stabilizer computation
    # Method 3: Affine action machinery
    
    # For now, use GAP's standard Orbits on the vector space
    # This is where MAGMA is more optimized
    
    vector_space := field^dim;
    
    # Compute orbit representatives
    # ... implementation depends on available GAP packages ...
    
    return rec(
        H1_action := H1_action,
        num_orbits := Length(orbit_reps),
        orbit_reps := orbit_reps,
        orbit_sizes := orbit_sizes
    );
end;
```

### Function 6: Convert Orbit Reps to Complements

```gap
# Input:
#   - orbit_record: OrbitRecord from ComputeH1Orbits
#   - semidirect_info: structural info about M ⋊ G
# Output:
#   - list of complement subgroups (one per conjugacy class)

OrbitRepsToComplements := function(orbit_record, semidirect_info)
    local cohomology, module, orbit_reps, complements, f_coords, f_cocycle, complement;
    
    cohomology := orbit_record.H1_action.cohomology;
    module := cohomology.module;
    orbit_reps := orbit_record.orbit_reps;
    
    complements := [];
    
    for f_coords in orbit_reps do
        # Convert H¹ coordinates back to actual cocycle
        f_cocycle := H1CoordsToCoycle(cohomology, f_coords);
        
        # Build the complement (from Phase 1)
        complement := CocycleToComplement(f_cocycle, module, semidirect_info);
        
        Add(complements, complement);
    od;
    
    return complements;
end;
```

---

## Integration: The Full Lifting Step

Here's how Phase 1 and Phase 2 combine in the lifting algorithm:

```gap
# Lift subgroups from S/M to S/N where M/N is elementary abelian
# Input:
#   - subgroups_containing_M: list of subgroups S with S ≥ M
#   - M, N: normal subgroups with M ≥ N and M/N elementary abelian
#   - ambient: the ambient group for conjugacy
# Output:
#   - list of subgroups containing N (up to conjugacy in ambient)

LiftThroughLayer := function(subgroups_containing_M, M, N, ambient)
    local results, S, module, cohomology, normalizer, normalizer_gens,
          H1_action, orbits, complements, T, T_lifted;
    
    results := [];
    
    for S in subgroups_containing_M do
        # Step 1: Build module structure (Phase 1)
        module := ChiefFactorAsModule(S, M, N);
        
        # Step 2: Compute H¹ (Phase 1)
        cohomology := ComputeH1(module);
        
        if cohomology.H1_dimension = 0 then
            # Unique complement: the canonical one
            Add(results, CanonicalLift(S, M, N));
            continue;
        fi;
        
        # Step 3: Determine the acting group (Phase 2)
        # This is the tricky part: who acts on complements?
        # In context of subdirect products, it's related to N_ambient(S) ∩ N_ambient(M)
        normalizer := ComputeRelevantNormalizer(S, M, ambient);
        normalizer_gens := SmallGeneratingSet(normalizer);
        
        # Step 4: Build action on H¹ (Phase 2)
        H1_action := BuildH1Action(cohomology, normalizer_gens);
        
        # Step 5: Compute orbits (Phase 2)
        orbits := ComputeH1Orbits(H1_action);
        
        Print("  S = ", StructureDescription(S), ": ");
        Print("|H¹| = ", cohomology.module.p^cohomology.H1_dimension);
        Print(", orbits = ", orbits.num_orbits, "\n");
        
        # Step 6: Convert orbit reps to complements (Phase 2)
        complements := OrbitRepsToComplements(orbits, ...);
        
        # Step 7: Lift complements back to subgroups containing N
        for T in complements do
            T_lifted := PreimageSubgroup(T, N);
            Add(results, T_lifted);
        od;
    od;
    
    return results;
end;
```

### Computing the Relevant Normalizer

This is subtle and depends on the context:

```gap
ComputeRelevantNormalizer := function(S, M, ambient)
    # In the subdirect product setting:
    # We're lifting through a direct product P = H_1 × ... × H_k
    # The "ambient" for conjugacy is a wreath product
    
    # The group acting on complements of M/N in S/N is:
    # { x ∈ N_ambient(S) : x also normalizes M } / M
    
    # For the elementary abelian layer M/N inside S:
    # The full automorphism group of the extension acts,
    # but we only need the part coming from the ambient group
    
    local N_S, N_M, acting;
    
    N_S := Normalizer(ambient, S);
    N_M := Normalizer(ambient, M);
    acting := Intersection(N_S, N_M);
    
    # Factor out M to get action on complements
    # (Elements of M act by coboundaries, giving trivial action on H¹)
    
    return acting / M;  # Or suitable quotient
end;
```

---

## Test Cases

### Test 1: Trivial Action on H¹

When the normalizer acts trivially on H¹, orbits = individual elements.

```gap
# C_2 × C_2 acting on itself by left multiplication
# (this is a regular action, should split H¹ into singletons)
# Actually, need to construct a proper test case...

# Better test: When N_G(S)/S is trivial, action on H¹ is trivial
# So orbits = points of H¹
```

### Test 2: Transitive Action

```gap
# Some cases where the normalizer acts transitively on non-zero H¹
# Then there are exactly 2 orbits: {0} and H¹ \ {0}
# This means 2 complement classes
```

### Test 3: Verify Against Direct Complement Computation

```gap
TestOrbitComputation := function(G, M)
    local module, cohomology, H1_action, orbits, 
          direct_complements, num_classes_direct;
    
    # Phase 1: Compute H¹
    module := BuildModuleFromAction(G, M);
    cohomology := ComputeH1(module);
    
    # Phase 2: Compute orbits
    H1_action := BuildH1Action(cohomology, GeneratorsOfGroup(Normalizer(...)));
    orbits := ComputeH1Orbits(H1_action);
    
    # Direct computation for comparison
    direct_complements := ComplementClassesRepresentatives(SemidirectProduct(M, G), M);
    num_classes_direct := Length(direct_complements);
    
    # Verify
    if orbits.num_orbits <> num_classes_direct then
        Error("Mismatch! Orbits: ", orbits.num_orbits, 
              ", Direct: ", num_classes_direct);
    fi;
    
    Print("PASS: ", orbits.num_orbits, " complement classes\n");
    return true;
end;
```

### Test 4: Full Lifting Test

```gap
# Test on a specific chief series layer
TestLiftingLayer := function()
    local G, series, M, N, module, cohomology, subgroups_above_M,
          lifted_brute_force, lifted_cohomology;
    
    G := SymmetricGroup(6);
    series := ChiefSeries(G);
    # Pick a layer...
    
    # Compare:
    # 1. Brute force: compute all subgroups, filter
    # 2. Cohomological: use H¹ orbit method
    
    # Results should match
end;
```

### Test 5: Performance Comparison

```gap
# Time comparison on increasingly large examples
PerformanceTest := function(max_size)
    local test_cases, G, M, t1, t2, result1, result2;
    
    test_cases := [
        [CyclicGroup(4), ElementaryAbelianGroup(4)],
        [SymmetricGroup(4), ...],
        [DirectProduct(SymmetricGroup(4), SymmetricGroup(4)), ...]
    ];
    
    for case in test_cases do
        G := case[1]; M := case[2];
        
        t1 := Runtime();
        result1 := BruteForceComplements(G, M);
        t1 := Runtime() - t1;
        
        t2 := Runtime();
        result2 := CohomologicalComplements(G, M);
        t2 := Runtime() - t2;
        
        Print("G = ", StructureDescription(G), ": ");
        Print("Brute force: ", t1, "ms, Cohomological: ", t2, "ms\n");
    od;
end;
```

---

## Edge Cases and Pitfalls

### 1. Trivial H¹

When H¹ = 0, there's exactly one complement class. Don't try to compute orbits on an empty space.

```gap
if cohomology.H1_dimension = 0 then
    return rec(num_orbits := 1, orbit_reps := [[]], orbit_sizes := [1]);
fi;
```

### 2. Large H¹ with Small Orbits

When p^dim is large but orbits are small (normalizer acts with large stabilizers), explicit enumeration is slow. Use stabilizer-based methods:

```gap
# Instead of enumerating all p^dim vectors:
# 1. Pick random vector v
# 2. Compute Stab(v) in the acting group
# 3. Orbit size = |acting group| / |Stab(v)|
# 4. Use transversal to find orbit, then continue with remaining vectors
```

### 3. The Zero Cocycle

The zero cocycle always gives the "standard" complement (the canonical copy of G in M ⋊ G). Its orbit under the normalizer action might be just {0} or might be larger if the action is non-faithful.

### 4. Non-Split Extensions

H¹ classifies complements, but only when complements exist. If M is not complemented in E = M ⋊ G (which can't happen for semidirect products, but can in the lifting context), H¹ has a different interpretation. 

In Holt's algorithm, we're always dealing with split extensions in the lifting steps, so this shouldn't arise.

### 5. Characteristic vs Prime

The action matrices are over GF(p) where p is the prime dividing |M/N|. Make sure to use the right field throughout.

---

## Files to Create/Modify

```
gap/
├── cohomology.g          # Phase 1 (already done)
├── modules.g             # Phase 1 (already done)
├── complements.g         # Phase 1 (already done)
├── h1_action.g           # NEW: Action on H¹ (this phase)
├── h1_orbits.g           # NEW: Orbit computation (this phase)
├── lifting.g             # MODIFY: Use cohomological lifting
├── subdirect.g           # Subdirect product enumeration
├── conjugacy.g           # Phase 3: Wreath product conjugacy
└── enumerate_sn.g        # Main driver
```

---

## Performance Targets

| Scenario | Brute Force | With Phase 2 |
|----------|-------------|--------------|
| H¹ = GF(2)⁴, trivial action | ~65k vectors | 16 orbits instantly |
| H¹ = GF(2)⁶, S₃ action | ~4M vectors | ~100-1000 orbits |
| H¹ = GF(3)⁴, action by C₂ | ~6.5k vectors | fast |
| S₄ × S₄ complements | seconds | milliseconds |

The goal is to handle cases where |H¹| = p^dim is up to ~10⁶ without enumerating all elements.

---

## Success Criteria for Phase 2

- [ ] `ActionOnCocycle` correctly transforms cocycles under normalizer action
- [ ] `ActionMatrixOnH1` produces correct matrices for action on quotient
- [ ] `ComputeH1Orbits` finds correct number of orbits (verified against direct computation)
- [ ] `OrbitRepsToComplements` produces valid complements
- [ ] Full `LiftThroughLayer` matches brute-force results on test cases
- [ ] 10x+ speedup over brute force for H¹ of dimension ≥ 4
- [ ] Can handle H¹ of size up to 10⁵ in reasonable time (< 1 minute)

---

## References

1. **Holt, D.F.** "Enumerating subgroups of the symmetric group." *Contemporary Mathematics*, 2010.
   - Section 4: The cohomological lifting method
   - Section 5: Orbit computation on vector spaces

2. **Holt, Eick, O'Brien.** *Handbook of Computational Group Theory*, Chapter 7.
   - 7.6: Computing H¹ and H²
   - 7.7: Complements and extensions

3. **GAP packages:**
   - `cohomolo`: Some cohomology functionality
   - `GRAPE`/`DESIGN`: May have useful orbit algorithms

4. **MAGMA documentation:**
   - `CohomologyGroup`, `OneCocycles`: Reference implementations
   - `Complements`: What we're trying to replicate
