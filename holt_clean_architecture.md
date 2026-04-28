# Clean Architecture for a Holt-Style Subgroup Enumeration Engine

## Purpose

This document describes a clean reimplementation strategy for enumerating conjugacy classes of subgroups using the architecture suggested by Derek Holt's papers, while keeping the implementation practical in GAP.

The goal is **not** to reproduce the current prototype structure. The goal is to build a system whose hot path matches Holt's performance ideas:

- isolate the solvable radical once,
- treat the nonsolvable top separately,
- use a real trivial-Fitting database,
- lift through elementary-abelian layers,
- avoid explicit subgroup conjugacy testing whenever a vector-space orbit computation can replace it,
- do almost all work inside the ambient permutation group rather than in large explicit quotient representations.

---

## 1. Design goals

The new engine should optimize for four things, in this order:

1. **Correctness**
   - produce complete and non-duplicated conjugacy class representatives,
   - preserve subgroup embeddings in the ambient permutation group,
   - expose verification hooks at every stage.

2. **Architectural clarity**
   - one pipeline for the general method,
   - well-defined interfaces between the TF-top stage and the lifting stage,
   - minimal fallback logic in the hot path.

3. **Performance**
   - avoid repeated subgroup conjugacy tests,
   - avoid generic quotient construction except where mathematically forced,
   - avoid recomputing TF-top subgroup data.

4. **Extensibility**
   - support specializations for symmetric-group orbit partitions later,
   - allow optional storage of normalizers, presentations, lattice data, etc.

---

## 2. High-level pipeline

The engine should have exactly two major stages.

### Stage A. Top-factor initialization

Given a permutation group `G`, compute a normal series

```text
1 = N0 < N1 < ... < Nr = L < G
```

such that:

- `L` is the solvable radical of `G`,
- each factor `Ni+1/Ni` is elementary abelian,
- `G/L` is trivial-Fitting (no nontrivial solvable normal subgroup).

Then:

1. identify the isomorphism type of `G/L`,
2. load subgroup class representatives of `G/L` from a persistent TF database,
3. translate those representatives into embedded subgroups of `G`.

### Stage B. Layer lifting

Starting from the subgroup classes of `G/L`, lift downward through the layers

```text
G/L -> G/Nr-1 -> ... -> G/N1 -> G.
```

Each lifting step handles one elementary-abelian factor `M/N` and transforms subgroup classes of `G/M` into subgroup classes of `G/N`.

This stage must be the true core of the implementation.

---

## 3. Module decomposition

A clean implementation should be split into the following modules.

## 3.1 `series_builder.g`

Responsible for:

- computing the solvable radical `L`,
- constructing/refining the normal series below `L`,
- ensuring every lifted layer is elementary abelian,
- refining overly large elementary-abelian layers when beneficial.

### Required API

```gap
BuildLiftSeries := function(G) -> rec(
    group := G,
    radical := L,
    layers := [ rec(N:=N0,M:=N1,p:=p1,d:=d1), ..., rec(N:=Nr-1,M:=Nr,p:=pr,d:=dr) ],
    tf_top := G/L
)
```

### Notes

This module should make the layer structure **explicit and stable**. The rest of the engine should never reconstruct chief or normal-series information ad hoc.

---

## 3.2 `tf_database.g`

Responsible for the nonsolvable top.

### Responsibilities

- identify a canonical TF-top representative,
- store and retrieve subgroup class representatives for trivial-Fitting groups,
- for larger TF groups, store only maximal subgroup data and recurse from maximals,
- translate stored subgroup representatives into the current group.

### Required API

```gap
IdentifyTFTop := function(Q) -> rec(key:=..., canonical_group:=..., iso:=...)
LoadTFClasses := function(tf_info) -> [ subgroup_class_records ]
```

### Important design rule

A cache miss must **not** fall back to `ConjugacyClassesSubgroups(Q)` in the main engine. That defeats the architecture.

Instead, there should be only two legal outcomes:

1. subgroup representatives are available directly from the TF database, or
2. maximal subgroup data are available, and the TF-top is solved recursively using the same engine.

If neither is available, the engine should stop with a controlled error or enter an explicit offline precomputation mode.

---

## 3.3 `subgroup_record.g`

Defines the data structure passed between stages.

Each subgroup class representative should be stored as a record with at least:

```gap
rec(
    subgroup := H,                  # subgroup embedded in ambient group G
    order := Size(H),
    generators := GeneratorsOfGroup(H),
    parent_index := ...,            # optional provenance
    normalizer := fail or N_G(H),   # optional lazy field
    presentation := fail or pres,   # needed during lifting
    metadata := rec(...)
)
```

### Design rule

The engine should always keep **embedded subgroup objects in the ambient group**, not abstract quotient-only objects.

---

## 3.4 `presentation_engine.g`

Responsible for subgroup presentations used in the cohomological lifting stage.

### Responsibilities

- store or reconstruct presentations for TF-top subgroup representatives,
- propagate presentations during each lifting step,
- provide relators in a form compatible with the cocycle solver.

### Required API

```gap
PresentationForClassRep := function(classrec) -> presrec
LiftPresentation := function(parent_pres, layer_data, cocycle_solution, Lgens) -> child_pres
```

### Design rule

Presentation logic should be isolated. It should not be mixed into orbit enumeration or subgroup deduplication logic.

---

## 3.5 `module_layer.g`

Builds the module-theoretic description of a layer `M/N`.

### Responsibilities

- realize `M/N` as an `Fp`-module for the relevant parent subgroup action,
- construct basis data,
- convert between subgroup language and vector-space language,
- enumerate `S`-invariant subspaces of `M/N`,
- compute normalizer actions on those subspaces.

### Required API

```gap
LayerModule := function(G, N, M, S) -> rec(
    p := p,
    module := V,
    basis := [...],
    quotient_map := ...,
    action_matrices := ...
)

InvariantSubspaceOrbits := function(layer_module, S, R) -> [ orbit_representatives ]
```

### Design rule

This module should own **all conversions** between group objects and vector-space objects. Those conversions should not be scattered across the engine.

---

## 3.6 `cohomology_lifter.g`

Implements the main lifting algorithm across one elementary-abelian layer.

This is the most important module in the new design.

### Input

- a layer `N < M` with `M/N` elementary abelian,
- one parent subgroup class `S/M` represented by an embedded subgroup `S <= G`,
- a presentation for `S/M`.

### Output

A list of child subgroup class records `T/N` embedded in `G` such that `TM = S`.

### Algorithm outline

For a fixed parent `S`:

1. Compute `R = N_G(S)` or the equivalent normalizer acting on candidate intersections.
2. Compute the `S`-invariant subspaces `L/N <= M/N`.
3. Take orbit representatives of those subspaces under `R/M`.
4. For each `L/N` representative:
   - compute whether the extension `S/L` splits over `M/L`,
   - if non-split, skip,
   - if split, compute `H^1(S/M, M/L)` representatives,
   - turn cocycle representatives into complements `T/L`,
   - compute the induced action of `Q/S` on those complement classes, where `Q = N_R(L)`,
   - take orbit representatives under that action,
   - convert each representative into a child subgroup `T <= G`.
5. Build lifted presentations for each child subgroup.

### Required API

```gap
LiftOneParentAcrossLayer := function(G, layer, parent_classrec) -> [ child_classrecs ]
```

### Critical performance rule

This module should avoid generic subgroup conjugacy tests as much as possible. Deduplication should be expressed as:

- orbit representatives on invariant subspaces, and
- orbit representatives on `H^1` complement classes.

Direct `RepresentativeAction` or pairwise subgroup conjugacy checks should be a last resort, not the default.

---

## 3.7 `orbit_action.g`

Encapsulates finite-group actions used for deduplication.

### Responsibilities

- orbit representatives on subspaces,
- orbit representatives on complement/cocycle classes,
- compact representation of actions by quotient groups such as `Q/S`,
- stabilizer computations when needed.

### Required API

```gap
OrbitRepsOnSubspaces := function(action_group, objects) -> [ reps ]
OrbitRepsOnCocycles := function(action_group, cocycle_classes) -> [ reps ]
```

### Design rule

All orbit computations should be routed through one module so performance instrumentation and algorithm changes affect the whole engine consistently.

---

## 3.8 `dedup_invariants.g`

Provides cheap filters before any expensive conjugacy test.

### Responsibilities

Compute inexpensive invariants such as:

- order,
- orbit partition on the permutation domain,
- derived length,
- composition-factor multiset,
- abelian invariants of the abelianization,
- support size / fixed-point data when relevant.

### Usage

This module is only for **negative filtering** and bucketing. It should not decide conjugacy on its own.

---

## 3.9 `verification.g`

Correctness harness.

### Responsibilities

- verify completeness of layer lifts where possible,
- compare counts against benchmark groups,
- check that no produced subgroup falls outside the intended parent relation,
- test that lifted complements satisfy `TM = S` and `T ∩ M = L`.

### Required API

```gap
VerifyLayerLift := function(G, layer, parent_classrec, children) -> true/false
RegressionCheck := function(group_id, expected_count) -> true/false
```

### Design rule

Verification must be available independently of performance mode.

---

## 3.10 `symmetric_specialization.g` (optional later)

A later optimization layer for the subgroup problem in `S_n` specifically.

### Responsibilities

- split the problem by orbit partition,
- use known transitive-group libraries,
- construct subdirect-product problems for a fixed orbit partition,
- apply specialized handling for hard partitions rather than forcing the generic engine through pathological layers.

This module should be optional. The general engine must work without it.

---

## 4. The core algorithms

This section states the key algorithms that need to be implemented cleanly.

## 4.1 Build the solvable-radical series

### Goal

Construct a series

```text
1 = N0 < N1 < ... < Nr = L
```

with each factor `Ni+1/Ni` elementary abelian.

### Algorithm

1. Compute the solvable radical `L`.
2. Starting from `1`, repeatedly refine normal sections until every factor below `L` is elementary abelian.
3. If a factor is elementary abelian but too large, attempt to refine it further as a module under the relevant action.
4. Record each layer as `(N, M, p, d)` where `M/N ≅ (Cp)^d`.

### Output invariant

The series object must be deterministic enough that performance comparisons are meaningful across runs.

---

## 4.2 Identify and load the TF-top

### Goal

Given `Q = G/L`, identify its isomorphism type and load subgroup representatives from the TF database.

### Algorithm

1. Compute a faithful manageable representation of `Q`.
2. Compute invariants sufficient to narrow candidates in the TF database.
3. Construct an explicit isomorphism to the stored canonical representative.
4. Load subgroup class representatives and presentations.
5. Pull them back into embedded subgroups of `G`.

### Output invariant

Every loaded subgroup representative must already be embedded in the ambient group and ready for lifting.

---

## 4.3 Enumerate invariant intersections in one layer

### Goal

For a fixed parent subgroup `S`, determine all possible intersections `L = T ∩ M` up to the relevant normalizer action.

### Algorithm

1. Build `V = M/N` as an `S/M`-module.
2. Enumerate `S`-invariant subspaces `L/N <= V`.
3. Let `R = N_G(S)`.
4. Compute orbit representatives of these subspaces under the action of `R/M`.

### Why this matters

This replaces many expensive subgroup-level duplicate checks by one vector-space orbit computation.

---

## 4.4 Solve the complement problem by cohomology

### Goal

For fixed `S` and `L`, enumerate all complements of `M/L` in `S/L` up to conjugacy by `M/L`.

### Algorithm

1. Realize `W = M/L` as an `Fp[S/M]`-module.
2. Use the presentation of `S/M` to write the extension equations.
3. Solve the corresponding linear system for cocycles.
4. If no solution exists, the extension is non-split; return no children.
5. Compute a particular solution plus the space of homogeneous solutions.
6. Compute `Z^1(S/M, W)` and `B^1(S/M, W)`.
7. Choose canonical representatives of `H^1(S/M, W) = Z^1/B^1`.
8. Convert those representatives into complements.

### Output invariant

At this stage, the output is complete up to conjugation by `M/L`.

---

## 4.5 Deduplicate complements under the normalizer action

### Goal

Pass from `M/L`-conjugacy classes of complements to `G`-conjugacy classes of child subgroups.

### Algorithm

1. Let `Q = N_R(L)` where `R = N_G(S)`.
2. Compute the induced action of `Q/S` on the chosen `H^1` representatives.
3. Take orbit representatives under that action.
4. Convert orbit representatives into child subgroups `T <= G`.

### Design rule

The preferred implementation is again an orbit computation on cocycle data, not repeated subgroup conjugacy tests.

---

## 4.6 Lift presentations

### Goal

Attach a presentation to each lifted child subgroup.

### Algorithm

Given:

- generators of the parent subgroup,
- basis generators for `L/N`,
- a cocycle representative determining the complement,

construct the child presentation by:

1. adding relators forcing `L/N` to be elementary abelian,
2. adding relators for the action of lifted parent generators on `L/N`,
3. lifting the parent relators and correcting them by the cocycle contribution.

### Why this matters

Presentations are not optional if the next lifting step is to remain clean and mathematically faithful.

---

## 5. Data flow through the engine

A single full run should look like this:

```text
Input group G
    -> BuildLiftSeries(G)
    -> IdentifyTFTop(G/L)
    -> LoadTFClasses(G/L)
    -> current_classes := top_classes
    -> for each layer from top to bottom:
           next_classes := []
           for each parent class in current_classes:
               children := LiftOneParentAcrossLayer(...)
               append children to next_classes
           current_classes := next_classes
    -> output current_classes
```

No module outside `cohomology_lifter.g` should need to know the internal details of cocycle solving.

---

## 6. Things the new architecture should avoid

The reimplementation should explicitly avoid the following patterns in the hot path.

### 6.1 On-the-fly `ConjugacyClassesSubgroups` for TF tops

This should not be used as a cache-miss strategy. It destroys the point of isolating the nonsolvable top.

### 6.2 Repeated pairwise subgroup conjugacy checks

These should not be the primary deduplication mechanism. Use orbit computations on subspaces and cocycles first.

### 6.3 Ad hoc quotient construction everywhere

Most calculations should remain in the ambient group or in module form. Explicit quotient representations should be limited to the few places where they are genuinely required.

### 6.4 Mixed correctness and optimization logic

The current prototype appears to have many correctness patches and performance heuristics in the same functions. The rewrite should separate:

- mathematically required logic,
- optional fast paths,
- verification code.

### 6.5 Global mutable state controlling correctness

Runtime feature flags are fine for experimentation, but the default engine should have one canonical mathematically sound path.

---

## 7. Recommended implementation order

A staged build is safer than a full monolithic rewrite.

### Phase 1. Skeleton and interfaces

Implement:

- `subgroup_record.g`
- `series_builder.g`
- `tf_database.g` interface
- `verification.g`

Goal: be able to load top classes and represent them cleanly.

### Phase 2. One-layer lifter

Implement:

- `module_layer.g`
- `presentation_engine.g`
- `cohomology_lifter.g`
- `orbit_action.g`

Goal: correctly lift a single parent subgroup across one elementary-abelian layer.

### Phase 3. Full pipeline

Compose the full repeated-lifting loop.

Goal: solve groups with trivial or tiny TF tops and compare counts.

### Phase 4. TF database population

Populate actual TF-top data and recursive maximal-subgroup support.

Goal: eliminate on-the-fly top-factor subgroup enumeration.

### Phase 5. Performance tuning

Only after correctness is stable:

- add orbit caching,
- add normalizer caching,
- add invariant bucketing,
- refine layer heuristics,
- add symmetric-group specializations.

---

## 8. Suggested record types

These records keep interfaces explicit.

### `LayerRec`

```gap
rec(
    N := ...,
    M := ...,
    p := ...,
    dimension := ...,
    index := ...
)
```

### `TFClassRec`

```gap
rec(
    subgroup := H,
    presentation := pres,
    order := Size(H),
    source := "tf_database"
)
```

### `ParentClassRec` / `ChildClassRec`

```gap
rec(
    subgroup := H,
    presentation := pres,
    order := Size(H),
    normalizer := fail,
    metadata := rec(
        parent := ...,
        layer := ...,
        intersection := ...,
        cocycle_rep := ...
    )
)
```

### `LiftResultRec`

```gap
rec(
    parent := parent_classrec,
    children := [ ... ],
    stats := rec(
        invariant_subspaces := ...,
        subspace_orbits := ...,
        h1_dimension := ...,
        complement_orbits := ...,
        time_ms := ...
    )
)
```

---

## 9. Verification strategy

The new engine should be built around regression testing from day one.

### Minimum regression suite

- small symmetric groups where subgroup-class counts are known,
- groups with trivial solvable radical,
- groups with one elementary-abelian layer,
- groups with large `2`-layers,
- examples where the TF top repeats often,
- examples where complement splitting fails.

### Layer-level checks

For every child subgroup `T` produced from parent `S` and intersection `L`:

- check `TM = S`,
- check `T ∩ M = L`,
- check the subgroup is not conjugate to an already selected representative within the intended action domain,
- check presentation consistency when enabled.

### Whole-run checks

- compare total class counts to known counts,
- compare order distributions where available,
- compare fixed-point-free counts if applicable.

---

## 10. Recommended coding principles

1. **One mathematically canonical path first.**
2. **Fast paths must be optional and locally isolated.**
3. **Every expensive operation should be timed and attributed to a module.**
4. **Every fallback should be visible in logs.**
5. **Never let deduplication semantics depend on a heuristic invariant alone.**
6. **Do not let quotient-construction convenience dictate architecture.**

---

## 11. Summary of the architecture

The new implementation should be centered around this statement:

> Solve the nonsolvable top once, then do all remaining work as structured elementary-abelian lifting.

That means the engine should:

- begin with the solvable radical,
- get subgroup classes for the trivial-Fitting top from a database,
- lift through elementary-abelian layers using module and cohomology computations,
- deduplicate by orbit computations instead of direct subgroup conjugacy whenever possible,
- keep subgroup representatives embedded in the ambient group throughout.

This is the cleanest path to an implementation that is both mathematically faithful to Holt's approach and substantially easier to optimize than the current prototype.
