# Lifting

Computation of the conjugacy classes of subgroups of the symmetric group `S_n`,
via a Holt-style chief-series lifting engine combined with an orbit-partition
decomposition and Goursat / wreath predictors for the hard cases.

The build extends [OEIS A000638](https://oeis.org/A000638) by two terms:
`a(19)` and `a(20)` are first independently computed here.

## Result

| n  | a(n) = subgroup classes of `S_n` | Source                                |
|----|---------------------------------:|---------------------------------------|
| 16 | 686,165                          | OEIS A000638                          |
| 17 | 1,466,358                        | OEIS A000638 (verified by this build) |
| 18 | 7,274,651                        | OEIS A000638 (verified by this build) |
| 19 | **16,745,233**                   | this build (FPF(19) = 9,470,582)      |
| 20 | **104,918,696**                  | this build (FPF(20) = 88,173,463)     |

Both new totals are obtained from the recurrence
`a(n) = FPF(n) + a(n-1)`, where `FPF(n)` is the number of fixed-point-free
subgroup classes of `S_n` produced by the build. Every subgroup class of
`S_{n-1}` extends to `S_n` by adjoining `{n}` as a trivial fixed point, so
the only new classes at step `n` are the FPF ones.

## Method

### 1. Orbit-partition decomposition

A subgroup `H ≤ S_n` partitions `{1,…,n}` into its orbits. Two subgroups
related by relabelling lie in the same conjugacy class of `S_n`, so the
ambient enumeration is organised by:

1. **Partition** `λ = (d_1, …, d_k)` of `n` with `d_i ≥ 2` — the multiset of
   orbit sizes of an FPF subgroup. Parts of size `1` correspond to fixed
   points and are handled by the recurrence above.
2. **Combo** `c = ((d_1, t_1), …, (d_k, t_k))` — one transitive group
   `T(d_i, t_i)` per orbit, chosen from GAP's transitive group library.
   The `T(d_i, t_i)` is the projection of `H` onto the `i`-th orbit, i.e.
   the smallest transitive group containing that projection.

For each combo, `H` is realised as a *subdirect product* of the projections,
sitting inside the direct product `P = T(d_1,t_1) × ⋯ × T(d_k,t_k)` embedded
blockwise into `S_n`. The job per combo is to enumerate FPF subdirect
products up to conjugacy in `S_n`.

`build_sn_topt.py` is the orchestrator. It enumerates partitions, then for
each partition iterates the multisets of `t`-indices per repeated degree
(`combos_for_partition`), and dispatches each combo to the appropriate
backend.

### 2. Routing

`build_sn_topt.py:route()` picks the cheapest method that applies:

| Route                  | When                                                                 | Backend                                                                 |
|------------------------|----------------------------------------------------------------------|-------------------------------------------------------------------------|
| `bootstrap`            | `len(combo) = 1`                                                     | Write generators of `T(d,t)` directly.                                  |
| `c2_fast`              | Partition is all 2's (so `P = C_2^k`)                                | `GF(2)` linear-algebra subspace enumeration up to `GL_k(F_2) ≀ S_k`.    |
| `bd8_fast`             | Combo is `[4,3]^k` (so `P = D_8^k`)                                  | Frattini-factor enumeration in `b_d8.g`.                                |
| `elemab_fast`          | Combo is `[(d,t)]^k` with `T(d,t)` elementary abelian                | `b_elemab_g.g` — `GL_m(F_p) ≀ S_k` orbit enumeration.                   |
| `distinguished`        | One species (= one `(d,t)` value) has multiplicity 1                 | 2-factor Goursat in `predict_2factor_topt.py --mode distinguished`.     |
| `holt_split`           | ≥ 2 distinct species                                                 | 2-factor Goursat with cluster split.                                    |
| `burnside_m2`          | Single species, multiplicity 2                                       | Burnside `m=2` symmetric Goursat.                                       |
| `wreath_ra`            | Single species, multiplicity `m ≥ 3`, `n < 16`                       | `predict_full_general_wreath.py` — materialize + dedup in `N_T ≀ S_m`. |
| `wreath_via_2factor`   | Single species, multiplicity `m ≥ 3`, `n ≥ 16`                       | Two-pass: 2-factor emit + wreath bucket/RA dedup.                       |

The fast paths (`c2_fast`, `bd8_fast`, `elemab_fast`) fall through to the
generic routes on failure, so correctness never depends on them succeeding.

### 3. Two-factor (Goursat) predictor

`predict_2factor_topt.py` reduces a `k`-block combo to a 2-block product
`P = L × R` (the split chosen to minimise work; for distinguished mode the
unique-multiplicity species is `R`). Subdirect products `H ≤ L × R` are
classified by Goursat's lemma as triples `(N_L, N_R, φ)` where
`N_L ◁ L`, `N_R ◁ R`, and `φ: L/N_L → R/N_R` is an isomorphism; up to the
respective normalizers, the FPF subgroups of `L × R` correspond to these
triples modulo the diagonal `Aut`-action on the shared quotient `Q`.

The implementation pulls FPF subgroups of `L` and `R` from cached per-combo
files (`parallel_sn_topt/<m>/…/<sub-combo>.g` for `m < n`), buckets them by
their normal-quotient structure, and uses a shared per-LEFT **H-cache** of
precomputed normal-subgroup / quotient / `Aut(Q)` data. A **qfree3** filter
("Q-free, version 3") restricts the candidate quotients `Q` to those that
can actually appear from the RIGHT side, which is the largest single win
for combos with large LEFT lattices.

### 4. Wreath predictor

`predict_full_general_wreath.py` handles `P = T(d,t)^m` with `m ≥ 3` of one
species. The ambient group for conjugacy is `W = N_{S_d}(T) ≀ S_m`, which is
vastly smaller than `S_n` and respects the block structure. The predictor:

1. Generates candidate FPF subgroups as `Aut(P)`-orbits, optionally bootstrapped
   from a 2-factor candidate file (`wreath_via_2factor` route).
2. Buckets candidates by cheap invariants (order, refined `Aut(Q)`-bucket,
   block-permutation signature).
3. Within each bucket performs `RepresentativeAction` tests *in `W`*, not in
   `S_n`. The "block cycletype" invariant splits `C_2^k` buckets that would
   otherwise collide.

### 5. Chief-series lifting core

Underlying both predictors is the chief-series lifting machinery in
`lifting_algorithm.g`, an implementation of Holt's algorithm
(Holt, *Enumerating subgroups of the symmetric group*, 2010). Given a parent
`P` and a target subdirect projection, it:

1. Builds a chief series for `P` with coprime layers reordered first
   (`RefinedChiefSeries`).
2. Loads (or computes) the conjugacy classes of subgroups of the
   trivial-Fitting top `P/L`.
3. Lifts class representatives layer-by-layer. Each layer `M/N` is realised
   as an `F_p`-module; complement enumeration uses
   `H^1(S/M, M/N)` cocycle orbits under the relevant normalizer
   (`h1_action.g`, `modules.g`) rather than naive subgroup enumeration.
4. Filters non-FPF survivors out of each layer (early termination) and
   deduplicates surviving classes by normalizer action.

`lifting_method_fast_v2.g` is an older small-`n` driver that exposes the
same engine via `FindFPFClassesForPartition`; the production pipeline drives
`lifting_algorithm.g` directly through the Python predictors.

### 6. Output format

Each completed combo writes a single file
`parallel_sn_<n>/<partition>/<combo>.g`:

```
# combo: [ [d_1, t_1], [d_2, t_2], ... ]
# candidates: C
# deduped: N
# elapsed_ms: T
[<gen_1>,<gen_2>,...]          # one subgroup per line
[<gen_1>,<gen_2>,...]
...
```

Each `[…]` line is a GAP permutation-generator list for one conjugacy class
representative. The `# deduped: N` header is the authoritative class count;
the orchestrator reads it for both progress accounting and integrity checks.

## Reproducing a result

```sh
# expand the bundled data (n = 1..17 small; 18, 19, 20 larger)
tar xf parallel_sn_1_17.tar.xz
tar xf parallel_sn_18.tar.xz
tar xf parallel_sn_19.tar.xz
tar xf parallel_sn_20.tar.xz   # from Releases

# integrity check on n = 20: every combo present, every file's # deduped
# header matches its generator-line count
python verify_s20_outputs.py

# FPF total for n = 20
python sum_fpf_s20.py          # 88,173,463
```

`a(20) = FPF(20) + a(19) = 88,173,463 + 16,745,233 = 104,918,696`, and
`a(19) = FPF(19) + a(18) = 9,470,582 + 7,274,651 = 16,745,233`.

## Data archives

| Archive                          | Coverage | Where                                                                         |
|----------------------------------|----------|-------------------------------------------------------------------------------|
| `parallel_sn_1_17.tar.xz`        | n = 1..17 | repo root                                                                    |
| `parallel_sn_18.tar.xz`          | n = 18    | repo root                                                                    |
| `parallel_sn_19.tar.xz`          | n = 19    | repo root                                                                    |
| `parallel_sn_20.tar.xz` (409 MB) | n = 20    | [Releases](https://github.com/jeff87654/Lifting/releases) (GitHub 100 MB cap) |

## Code layout

Orchestration
- `build_sn_topt.py` — per-`n` dispatch, route selection, retry / deferred-combo handling, FPF total check against OEIS.
- `auto_snapshot.py` — watchdog that auto-commits source edits.

Predictors (Python wrappers around GAP workers)
- `predict_2factor_topt.py` — 2-factor Goursat (`distinguished` / `holt_split` / `burnside_m2`).
- `predict_full_general_wreath.py` — wreath predictor (`m ≥ 3` single species).
- `run_c2_fast_path.py`, `run_b_d8_path.py`, `run_b_elemab_path.py` — fast-path drivers.

GAP engine
- `lifting_algorithm.g` — chief-series lifting, layer-by-layer complement enumeration, FPF filtering.
- `modules.g`, `h1_action.g` — `F_p`-module realisation and `H^1`-orbital complement enumeration.
- `lifting_method_fast_v2.g` — legacy small-`n` driver around the same engine.
- `b_d8.g`, `b_elemab_g.g`, `b21_*.g` — closed-form / linear-algebra fast paths.

Verification
- `verify_s20_outputs.py` — checks completeness and per-file consistency for the `n = 20` tree.
- `sum_fpf_s20.py` — re-tallies FPF(20) from the extracted tarball.

## References

- D.F. Holt, *Enumerating subgroups of the symmetric group*, in *Computational
  Group Theory and the Theory of Groups, II*, AMS Contemp. Math. **511**, 2010
  (`a000019_1.pdf` in this repo).
- OEIS [A000638](https://oeis.org/A000638) — number of subgroups of `S_n`.
- The GAP Group, *GAP — Groups, Algorithms, Programming*, version 4.15.1.
