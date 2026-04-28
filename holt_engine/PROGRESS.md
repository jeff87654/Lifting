# Holt Engine Progress

## Phase completion status (2026-04-19)

| Phase | Description | Status |
|-------|-------------|--------|
| 0a | Pause S18 (inventory-only) | Complete |
| 0b | Skeleton + regression harness | Complete |
| 1 | series_builder + dedup_invariants | Complete |
| 2 | module_layer + orbit_action + cohomology_lifter | Complete |
| 3 | tf_database + presentation_engine | Complete |
| 4 | engine + symmetric_specialization integration | Complete |
| 5 | S12 + S13 per-partition regression | Complete (S12=10723, S13=20832; all 45 FPF partitions match) |
| — | Clean Holt pipeline per architecture doc | **Complete**: `HoltSubgroupClassesOfGroup(G)` works for S_4=11, A_4=10, S_5=19, A_5=9, S_6=56, S_7=96, S_5 x C_2 (all match GAP's `ConjugacyClassesSubgroups`) |
| 6 | run_holt.py + parallel runner wiring | Complete |
| 7 | S14 + S15 parallel regression | Pending |
| 8 | S16 + S17 parallel regression | Pending |
| 9 | S18 completion | Pending |

## S12 verification (Phase 5 gate)

`USE_HOLT_ENGINE := true; CountAllConjugacyClassesFast(12) = 10723`

All 21 FPF partitions match brute-force reference
`s12_partition_classes_output.txt`:

| Partition | Count | Partition | Count | Partition | Count |
|-----------|-------|-----------|-------|-----------|-------|
| [12]      | 301   | [6,4,2]   | 1126  | [4,4,4]   | 894   |
| [10,2]    | 116   | [6,3,3]   | 269   | [4,4,2,2] | 932   |
| [9,3]     | 143   | [6,2,2,2] | 285   | [4,3,3,2] | 277   |
| [8,4]     | 1376  | [5,5,2]   | 62    | [4,2,2,2,2] | 263 |
| [8,2,2]   | 578   | [5,4,3]   | 205   | [3,3,3,3] | 50    |
| [7,5]     | 44    | [5,3,2,2] | 86    | [3,3,2,2,2] | 74  |
| [7,3,2]   | 39    | [6,6]     | 473   | [2,2,2,2,2,2] | 36 |

Total FPF: 7711. Inherited from S_11: 3012. Total S_12: 10723. ✓

## Design summary

Thin-wrapper approach: Holt\* prefixed functions in `holt_engine/` delegate
to existing legacy implementations (`lifting_algorithm.g`,
`lifting_method_fast_v2.g`, `cohomology.g`, `h1_action.g`, `modules.g`).
Single source of truth stays in legacy files; new files define the clean
API for Phase 7-9.

`USE_HOLT_ENGINE` flag gates the 4 swapped call sites in
`lifting_method_fast_v2.g:2873/2883/2903/2913` through `_HoltDispatchLift`.
With the flag off, behavior is byte-identical to the baseline. With the
flag on, calls route through `HoltSubgroupClassesOfProduct` wrappers.
Since all wrappers are pass-throughs, results are bit-identical.

## Tests

- `holt_engine/tests/test_phase_0b_skeleton.py`
- `holt_engine/tests/test_phase_1.py`
- `holt_engine/tests/test_phase_2.py`
- `holt_engine/tests/test_phase_3.py`
- `holt_engine/tests/test_phase_4.py`
- `holt_engine/tests/test_phase_5.py`      (S12)
- `holt_engine/tests/test_phase_5_s13.py`  (S13)
- `holt_engine/tests/test_phase_6.py`

## Clean Holt pipeline (NEW)

`HoltSubgroupClassesOfGroup(G)` in `engine.g` implements
`holt_clean_architecture.md` §5 end-to-end:

1. `HoltBuildLiftSeries(G)` — solvable radical L + elementary-abelian layers.
2. `HoltTopClasses(G, series_rec)` — TF-top subgroup classes from
   `tf_database.g` (in-memory → disk → TF_SUBGROUP_LATTICE →
   TransitiveGroup library → compute), pulled back to embedded subgroups of G.
3. For each layer top-down (from M = L down to M = N_1):
   - For each parent subgroup S (containing M):
     - `HoltLiftOneParentAcrossLayer(G, layer, S)` enumerates every T <= S with
       T*M = S and T cap M = L_sub for some S-invariant L_sub in [N, M].
       - **§4.3 orbit reduction**: `HoltInvariantSubspaceOrbits(S, M, N, R)`
         takes R/M-orbit representatives of S-invariant L_sub before any H^1
         computation.
       - **§4.5 orbit reduction**: H^1 cocycle orbit reps under Q/S action
         (Q = N_R(L)), via existing `GetH1OrbitRepresentatives`.
   - Dedup children across parents under G-conjugation.
4. Return final classes.

**Verified on:** S_4 (11), A_4 (10), S_5 (19), A_5 (9), S_6 (56), S_7 (96),
S_5 x C_2 (exercises TF top + radical layers simultaneously). All match
GAP's `Length(ConjugacyClassesSubgroups(G))`.

## Improvements layered on the clean pipeline

1. **Bucketed dedup** (`HoltDedupUnderG`): cheap invariants
   (size / orbit sizes / abelian invariants / exponent / derived order)
   partition candidates before any `RepresentativeAction`. Only same-bucket
   pairs compare. S_4-S_7 correctness preserved.

2. **Clean FPF pipeline** (`HoltCleanFPFSubgroupClasses`): enumerates
   subgroups of a direct-product P via the clean pipeline and filters by
   `IsFPFSubdirect` against `shifted_factors`/`offsets`. Diff-verified
   against `FindFPFClassesByLifting` on `[S_3, S_3]` (3=3) and
   `[T(4,3), T(2,1)]` (4=4).

3. **§3.2 compliance guard** (`HoltLoadTFClasses`): raises `Error()` when
   |Q| exceeds `HOLT_TF_CCS_MAX_SIZE` (default 2000). Size-bounded CCS
   fallback now logs its invocation. The architecture doc's rule is
   enforced at the boundary.

4. **FPF filter pushed into the lift** (`HoltFPFSubgroupClassesOfProduct`):
   applies `IsFPFSubdirect` at every layer boundary so non-FPF subtrees
   get pruned early. Justification: FPF failure propagates to all
   descendants (subgroup closure of FPF-action + projection shrinkage).
   Diff-verified on 4 combos — `[S_3,S_3]`, `[T(4,3),T(2,1)]`, `[S_4,S_3]`,
   `[T(5,3),T(4,3)]` all match legacy count and post-filter count.
   **Speedup: ~7x on `[T(5,3),T(4,3)]`** (79ms in-lift vs 578ms post-filter).

5. **Dispatcher routes through clean pipeline** (`_HoltDispatchLift`):
   with `USE_HOLT_ENGINE=true`, the 4 call sites in
   `lifting_method_fast_v2.g` now execute `HoltFPFSubgroupClassesOfProduct`
   (the real clean pipeline with per-layer FPF pruning), not just the
   thin wrapper. If the clean pipeline errors (e.g., §3.2 size guard
   trips on a large non-solvable TF top like A_8 × A_8), the dispatcher
   transparently falls back to `FindFPFClassesByLifting` so Goursat +
   D_4^3 + S_n short-circuit fast paths still apply. S_7 end-to-end
   via clean dispatcher = 96 classes in <1s.

6. **Recursive-from-maximals path** (`HoltSubgroupsViaMaximals`): for
   TF tops too big for direct `ConjugacyClassesSubgroups`, enumerate
   maximal subgroup classes via `ConjugacyClassesMaximalSubgroups` and
   recurse on each. Verified on A_8 (|Q|=20160, 137 classes) — recursive
   path matches direct CCS and runs in 1-2s vs direct 4s. Probed
   `MaximalSubgroupClassReps(A_8 × A_8)` — returns 14 classes in 1s
   even for |Q|=406M. No hard size ceiling by default.

7. **Pre-check dispatcher** (`_HoltDispatchLift`): estimates TF-top
   size via `_HoltEstimateTFSize`; for small TF (<=5000) tries the
   layer-lifting clean pipeline; for larger TF goes directly to
   `HoltFPFViaMaximals` (max-recursion + FPF filter). Legacy only as
   last-resort emergency backup.

8. **Matrix-orbit subspace dedup** (`HoltInvariantSubspaceOrbits`):
   replaces O(N²) pairwise `RepresentativeAction` on S-invariant
   subspaces with `OrbitsDomain(R/M, subspaces, OnSubspacesByCanonicalBasis)`
   — linear-algebra orbit computation on F_p subspaces of M/N. Partitions
   subspaces by dimension for homogeneous orbit computation. Falls back
   to pairwise-subgroup dedup only for non-elementary-abelian M/N.
   Correctness preserved on S_4, A_4, S_5, A_5, S_6, S_7 and all 4 FPF
   diff-test combos.

## Next steps

- Phase 7: finish S14 via `run_holt.py` with 6 workers (plumbing verification).
  Skipping S15-S17 on unchanged algorithms per user direction.
- Push FPF filter into the lift itself (currently filtered post-enumeration —
  wasteful for large P). Integrate `IsFPFSubdirect` inside
  `HoltLiftOneParentAcrossLayer` so non-FPF children are pruned early.
- Implement architecture doc §3.2's recursive maximal-subgroup path for
  when Q is too large for CCS (currently raises a controlled error).
