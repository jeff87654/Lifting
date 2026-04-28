# Precomputed Database for Holt's Algorithm

## Problem Statement

Holt's MAGMA implementation achieves its performance by **precomputing and storing** extensive subgroup information for "trivial-Fitting groups" (groups with no nontrivial solvable normal subgroup). Our implementation recomputes everything from scratch on every run, which is a major bottleneck.

From the 2001 paper:
> "For trivial-Fitting groups, we either store representatives of the conjugacy classes of all subgroups (after computing them once and for all, usually using the cyclic extension method) or, for larger groups, where this would be expensive in storage space, we store this information just for the maximal subgroups."

From the 2010 paper:
> "The process times in seconds for n = 13, 14, 15, 16, and 17 were respectively 105, 653, 1190, 20234, and 26640."

Our S10 computation takes ~8 minutes. Holt's S13 takes ~105 seconds. The database is a key differentiator.

---

## What Holt's Database Contains

### For Small Trivial-Fitting Groups (|G| < 216,000)
1. **All conjugacy class representatives** of subgroups
2. **Finite presentations** for each subgroup (stored as words in generators)
3. **Generators** stored as words in the group's standard generators
4. **Class parameters** (order, class length) for identification

### For Larger Trivial-Fitting Groups
1. **Maximal subgroups only** (representatives of conjugacy classes)
2. Algorithm applied recursively to maximal subgroups when needed
3. Results tested for conjugacy afterward

### Database Statistics (from paper)
- 98 trivial-Fitting groups of order ≤ 100,000
- 154 trivial-Fitting groups of order < 216,000
- Database occupies ~4 MB
- Planned extension to order 10,000,000

---

## Why This Matters for S_n Computation

For computing subgroups of S_n, the relevant trivial-Fitting groups are:
- **A_n** (alternating groups) - the largest solvable normal subgroup of S_n is trivial for n ≥ 5
- **Simple groups** appearing as composition factors
- **Products of simple groups** and their automorphism groups

When lifting through the chief series, the "top layer" G/L (where L is the largest solvable normal subgroup) is a trivial-Fitting group. Having precomputed subgroups for this layer eliminates the most expensive part of the computation.

---

## Desiderata for Our Database

### D1: Transitive Group Subgroup Cache
**Store:** For each transitive group T(n,k), store representatives of conjugacy classes of subgroups.

**Rationale:** Every factor in a partition uses a transitive group. We enumerate T(n,k) for each part.

**Format:**
```
Key: (n, k) where T(n,k) is the k-th transitive group of degree n
Value: {
  subgroup_classes: [list of generating sets],
  class_sizes: [conjugacy class sizes],
  orders: [subgroup orders],
  # Optional: presentations, normalizers
}
```

**Priority:** HIGH - directly reusable across partitions

### D2: FPF Subdirect Product Cache
**Store:** For each tuple of transitive group IDs, store FPF subdirect products.

**Rationale:** The function `FindFPFClassesByLifting` is called repeatedly for the same combinations. Cache results.

**Current partial implementation:** `FPF_SUBDIRECT_CACHE` in `lifting_method_fast_v2.g` (line 24) - but it's session-only, not persistent.

**Format:**
```
Key: Sorted list of (degree, TransitiveIdentification) pairs
Value: [list of FPF subdirect product generating sets]
```

**Priority:** HIGH - already partially implemented, needs persistence

### D3: Elementary Abelian Subdirect Cache
**Store:** All subdirect subspaces of C_p^r × C_p^s for small p, r, s.

**Rationale:** The C2 fiber product optimization (and potential C_p generalizations) need these repeatedly.

**Current partial implementation:** `ELEMENTARY_ABELIAN_SUBDIRECTS` in `lifting_algorithm.g` (line 60) and `EnumerateSubdirectSubspaces` in `lifting_method_fast_v2.g`.

**Format:**
```
Key: (p, r, s)
Value: [list of basis matrices representing subdirect subspaces]
```

**Priority:** MEDIUM - useful for C2 optimization

### D4: Complement Class Cache
**Store:** For quotient structures Q/M where M is elementary abelian, cache H^1 dimensions and representative cocycles.

**Rationale:** The cohomology computation is expensive. Same module structures appear repeatedly.

**Current partial implementation:** `H1_CACHE` in `cohomology.g` (line 81) - session-only.

**Format:**
```
Key: Module fingerprint (p, dim, |G|, action matrices hash)
Value: {
  H1_dimension: int,
  cocycle_basis: [vectors],
  coboundary_basis: [vectors],
  # Optionally: representative complements
}
```

**Priority:** MEDIUM - depends on fixing cohomology bugs first

### D5: Normalizer Cache
**Store:** For Young subgroups and their wreath product generalizations, cache normalizers in S_n.

**Rationale:** `BuildYoungNormalizer` and `BuildConjugacyTestGroup` are called for every partition.

**Format:**
```
Key: (n, partition)
Value: Generators of Normalizer(S_n, Young subgroup)
```

**Priority:** LOW - these computations are relatively fast

---

## Implementation Options

### Option A: GAP Native Persistence
Use GAP's `SaveWorkspace`/`LoadWorkspace` or `WriteGenerators`/`ReadGenerators`.

**Pros:** Simple, no external dependencies
**Cons:** Binary format, version-sensitive, large files

### Option B: JSON/Text Format
Store data as JSON or structured text files.

**Pros:** Human-readable, portable, version-control friendly
**Cons:** Slower to parse, need serialization code

### Option C: SQLite Database
Use GAP's IO package to interface with SQLite.

**Pros:** Fast queries, mature technology, compact storage
**Cons:** External dependency, more complex setup

### Option D: Precomputed GAP Code
Generate `.g` files that define the data structures directly.

**Pros:** No parsing overhead, works with standard GAP
**Cons:** Large files, regeneration needed for updates

**Recommendation:** Start with **Option D** (precomputed GAP code) for simplicity. The database can be generated once and `Read()` at load time.

---

## Computation Strategy for Building the Database

### Phase 1: Transitive Group Subgroups (D1)
```
For n in [2..12]:  # Start small
  For k in [1..NrTransitiveGroups(n)]:
    T := TransitiveGroup(n, k)
    classes := ConjugacyClassesSubgroups(T)
    Store(n, k, classes)
```

Estimated storage: ~1-10 MB for n ≤ 12

### Phase 2: FPF Subdirect Products (D2)
```
For each partition of n in [2..10]:
  For each combination of transitive groups:
    Compute FPF subdirects
    Store with cache key
```

This is expensive but only done once.

### Phase 3: Elementary Abelian Subdirects (D3)
```
For p in [2, 3, 5]:
  For r in [1..6]:
    For s in [1..6]:
      Enumerate subdirect subspaces of C_p^r × C_p^s
      Store
```

This is purely linear algebra, fast to compute.

---

## File Structure Proposal

```
Lifting/
├── database/
│   ├── transitive_subgroups/
│   │   ├── degree_2.g
│   │   ├── degree_3.g
│   │   ├── ...
│   │   └── degree_12.g
│   ├── fpf_subdirects/
│   │   ├── partition_2_2.g
│   │   ├── partition_3_2.g
│   │   ├── ...
│   │   └── index.g  # Maps cache keys to files
│   ├── ea_subdirects/
│   │   └── elementary_abelian.g
│   └── load_database.g  # Master loader
├── lifting_algorithm.g
├── lifting_method_fast_v2.g
└── ...
```

---

## Immediate Action Items

1. **Create `database/` directory structure**

2. **Implement database generation script** (`generate_database.py` or `.g`)
   - Start with transitive group subgroups for degrees 2-8
   - Add FPF subdirect cache for partitions of n ≤ 8

3. **Modify `lifting_method_fast_v2.g` to load database on startup**
   - Check for database files
   - Populate `FPF_SUBDIRECT_CACHE` from stored data
   - Add fallback to computation if not found

4. **Benchmark before/after**
   - Measure S8, S9, S10 times with and without database
   - Identify remaining bottlenecks

---

## Expected Impact

Based on Holt's paper, having precomputed data should:
- Eliminate redundant subgroup enumeration across runs
- Reduce S10 time from ~8 minutes to potentially ~1-2 minutes
- Make S12/S13 feasible (currently intractable)

The database approach trades disk space (~10-100 MB) for computation time. This is the same tradeoff MAGMA makes successfully.

---

## References

1. Cannon, Cox, Holt (2001). "Computing the Subgroups of a Permutation Group." J. Symbolic Computation 31, 149-161.

2. Holt (2010). "Enumerating subgroups of the symmetric group." Contemporary Mathematics.

3. GAP TransitiveGroups library documentation.
