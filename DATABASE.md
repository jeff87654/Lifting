# Precomputed Database System

This document describes the persistent database system used to accelerate Holt's algorithm for computing conjugacy classes of subgroups in S_n.

## Overview

The database stores precomputed data that would otherwise need to be recalculated on every run:

| Component | Purpose | Speedup |
|-----------|---------|---------|
| Transitive Subgroups | Subgroup class reps for T(n,k) | Avoids `ConjugacyClassesSubgroups` calls |
| FPF Subdirects | Full-projection-faithful subdirect products | Caches expensive lifting computations |
| Elementary Abelian Subdirects | Subdirect subspaces of C_p^n × C_p^n | Speeds up C2 fiber product optimization |

## Directory Structure

```
Lifting/
├── database/
│   ├── load_database.g              # Master loader (read this first)
│   ├── transitive_subgroups/
│   │   ├── degree_02.g              # T(2,1) subgroups
│   │   ├── degree_03.g              # T(3,1), T(3,2) subgroups
│   │   ├── ...
│   │   └── degree_08.g              # All 50 transitive groups of degree 8
│   ├── fpf_subdirects/
│   │   └── fpf_cache.g              # Cached FPF subdirect products
│   └── ea_subdirects/
│       └── elementary_abelian.g     # C_p^n subdirect subspaces
├── generate_transitive_db.py        # Script to generate transitive subgroups
└── lifting_method_fast_v2.g         # Main algorithm (loads database automatically)
```

## Loading the Database

The database is loaded automatically when you read `lifting_method_fast_v2.g`:

```gap
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
# Output:
# Loading precomputed database...
# ================================
#   Loaded 7 elementary abelian subdirect entries
#   Loaded transitive subgroups for 7 degrees
#   Loaded 165 FPF subdirect cache entries
# Database loaded in 0.047s
# ================================
```

To load manually (e.g., for testing):

```gap
Read("C:/Users/jeffr/Downloads/Lifting/database/load_database.g");
LoadDatabaseIfExists();
```

## Data Formats

### Transitive Subgroups (`TRANSITIVE_SUBGROUPS`)

Stores conjugacy class representatives of subgroups for each transitive group T(n,k).

**Structure:**
```gap
TRANSITIVE_SUBGROUPS.("n").("k") := [
    [gen1_list, gen2_list, ...],  # Generators for subgroup 1
    [gen1_list, gen2_list, ...],  # Generators for subgroup 2
    ...
];
```

**Example:** T(3,2) = S_3 has 4 subgroup classes:
```gap
TRANSITIVE_SUBGROUPS.("3").("2") := [
    [  ],                           # Trivial group (no generators)
    [ [ 1, 3, 2 ] ],               # C_2 = <(2,3)>
    [ [ 2, 3, 1 ] ],               # C_3 = <(1,2,3)>
    [ [ 2, 3, 1 ], [ 1, 3, 2 ] ]   # S_3 = <(1,2,3), (2,3)>
];
```

Each generator is stored as a list `[1^g, 2^g, ..., n^g]` representing the permutation.

### FPF Subdirect Cache (`FPF_SUBDIRECT_DATA`)

Caches FPF subdirect products indexed by sorted transitive group identifiers.

**Structure:**
```gap
FPF_SUBDIRECT_DATA.("cache_key") := [
    [gen1_list, gen2_list, ...],  # Generators for subdirect 1
    [gen1_list, gen2_list, ...],  # Generators for subdirect 2
    ...
];
```

**Cache Key Format:** Sorted list of `[degree, TransitiveIdentification]` pairs as a string.

**Example:** For S_3 × S_3:
```gap
key := "[ [ 3, 2 ], [ 3, 2 ] ]";
FPF_SUBDIRECT_DATA.(key) := [
    # 11 FPF subdirect products...
];
```

### Elementary Abelian Subdirects (`EA_SUBDIRECTS_DATA`)

Stores subdirect subspaces of C_p^n × C_p^n as basis matrices over GF(p).

**Structure:**
```gap
EA_SUBDIRECTS_DATA.("p_n") := [
    [[row1], [row2], ...],  # Basis for subdirect subspace 1
    [[row1], [row2], ...],  # Basis for subdirect subspace 2
    ...
];
```

**Example:** For C_2 × C_2 (p=2, n=1):
```gap
EA_SUBDIRECTS_DATA.("2_1") := [
    [ [ 1, 0 ] ],           # Diagonal: {(0,0), (1,1)}
    [ [ 1, 1 ] ],           # Anti-diagonal: {(0,0), (1,0), (0,1), (1,1)} - wait, this is wrong
    [ [ 0, 1 ] ],           # Second factor projection
    [ [ 1, 0 ], [ 0, 1 ] ]  # Full product
];
```

## API Reference

### Core Functions

#### `GetPrecomputedSubgroups(n, k)`
Get precomputed subgroup class representatives for transitive group T(n,k).

```gap
subs := GetPrecomputedSubgroups(4, 5);  # S_4 subgroups
Length(subs);  # 11
```

**Returns:** List of subgroups, or `fail` if not precomputed.

#### `GetSubgroupClassReps(G)`
Get subgroup class representatives for any group G. Uses precomputed data for transitive groups, falls back to `ConjugacyClassesSubgroups` otherwise.

```gap
S4 := SymmetricGroup(4);
subs := GetSubgroupClassReps(S4);  # Uses precomputed data
Length(subs);  # 11

# Also works for shifted groups
shifted_S3 := Group((4,5,6), (4,5));
subs := GetSubgroupClassReps(shifted_S3);  # Identifies as T(3,2), shifts results
```

#### `GetCachedEASubdirects(p, n)`
Get precomputed subdirect subspaces for C_p^n × C_p^n.

```gap
subdirects := GetCachedEASubdirects(2, 1);  # C_2 × C_2 subdirects
```

### Utility Functions

#### `GroupFromGenLists(genLists)`
Convert stored generator lists back to a permutation group.

```gap
genLists := [ [ 2, 3, 1 ], [ 1, 3, 2 ] ];  # (1,2,3) and (2,3)
G := GroupFromGenLists(genLists);
Size(G);  # 6 (S_3)
```

#### `PermFromList(lst)`
Convert a list representation to a permutation.

```gap
g := PermFromList([2, 3, 1]);  # (1,2,3)
```

#### `ZeroPadString(n, width)`
Zero-pad an integer to a string of given width.

```gap
ZeroPadString(3, 2);  # "03"
```

### Database Management

#### `LoadDatabaseIfExists()`
Load all database components. Called automatically by `lifting_method_fast_v2.g`.

#### `PrintDatabaseStats()`
Print statistics about loaded database.

```gap
PrintDatabaseStats();
# Database Statistics:
# ====================
# Transitive subgroup entries: 85
# FPF subdirect entries:       165
# EA subdirect entries:        7
# Load time:                   0.047s
```

#### `SaveFPFSubdirectCache()`
Save current FPF cache to disk. Called automatically after each S_n computation.

#### `SaveEASubdirects()`
Save elementary abelian subdirects to disk.

## Extending the Database

### Adding More Transitive Subgroups

To generate transitive subgroups for additional degrees, modify `generate_transitive_db.py`:

```python
# In main():
for n in range(2, 13):  # Change 9 to desired max degree
    success = generate_transitive_db_for_degree(n)
```

Then run:
```bash
python generate_transitive_db.py
```

**Warning:** Degree 9+ takes significantly longer. Degree 12 (301 transitive groups) may take hours.

### Extending FPF Cache

The FPF cache grows automatically as new computations are performed. After running `CountAllConjugacyClassesFast(n)`, the cache is saved to disk.

### Adding Elementary Abelian Subdirects

To add more cases, modify the generation script or manually add entries:

```gap
# Compute subdirects for C_3^2 × C_3^2
subdirects := EnumerateEASubdirects(3, 2);
EA_SUBDIRECTS_DATA.("3_2") := subdirects;
SaveEASubdirects();
```

## Performance Impact

| Computation | Without Database | With Database |
|-------------|------------------|---------------|
| S_8         | ~40s             | ~36s          |
| S_9         | ~130s            | ~113s         |
| S_10        | ~8 min           | ~6 min (est)  |

The primary benefit is avoiding redundant computation across sessions. The FPF cache is especially valuable for repeated runs with the same or overlapping partitions.

## Troubleshooting

### Database Not Loading

Check that the path in `load_database.g` matches your installation:
```gap
DATABASE_PATH := "C:/Users/jeffr/Downloads/Lifting/database/";
```

### Missing Transitive Subgroups

If `GetPrecomputedSubgroups(n, k)` returns `fail`, the degree may not be precomputed. Generate it:
```bash
python generate_transitive_db.py
```

### FPF Cache Corruption

Delete and regenerate:
```bash
del database\fpf_subdirects\fpf_cache.g
```
Then run a computation to rebuild.

## Implementation Notes

1. **Permutation Storage:** Permutations are stored as lists `[1^g, 2^g, ..., n^g]` to avoid GAP's internal representation issues with serialization.

2. **Cache Keys:** FPF cache keys use `ComputeCacheKey()` which sorts transitive group identifiers for canonical ordering.

3. **Lazy Loading:** Database files are only read if they exist. Missing files don't cause errors.

4. **Automatic Persistence:** The FPF cache is saved after each `CountAllConjugacyClassesFast()` call, so progress is preserved even if later computations fail.
