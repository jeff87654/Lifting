# Lifting

Computation of the conjugacy classes of subgroups of the symmetric group `S_n`,
via a Holt-style chief-series lifting engine combined with an orbit-partition
decomposition and Goursat / wreath predictors for the hard cases.

The build extends [OEIS A000638](https://oeis.org/A000638) by two terms: `a(19)`
and `a(20)` are first independently computed here.

## Result

| n  | a(n) = subgroup classes of `S_n` | Source                                |
|----|---------------------------------:|---------------------------------------|
| 16 | 686,165                          | OEIS A000638                          |
| 17 | 1,466,358                        | OEIS A000638 (verified by this build) |
| 18 | 7,274,651                        | OEIS A000638 (verified by this build) |
| 19 | **16,745,233**                   | this build (FPF(19) = 9,470,582)      |
| 20 | **104,918,696**                  | this build (FPF(20) = 88,173,463)     |

Both new totals follow from the recurrence `a(n) = FPF(n) + a(n-1)`, where
`FPF(n)` is the number of fixed-point-free subgroup classes of `S_n`. Every
subgroup class of `S_{n-1}` lifts to `S_n` by adjoining `{n}` as a trivial
fixed point, so the only genuinely new classes at step `n` are the FPF ones.
That is what the build computes.

## Method

### 1. Orbit-partition decomposition

A subgroup `H ≤ S_n` partitions `{1, …, n}` into its orbits. Two subgroups
related by relabelling lie in the same `S_n`-conjugacy class, so we organise
the enumeration around two nested choices.

First, the *partition* `λ = (d_1, …, d_k)` of `n` with `d_i ≥ 2` records the
multiset of orbit sizes of an FPF subgroup. Parts of size 1 correspond to
fixed points and are absorbed by the recurrence above.

Second, the *combo* `c = ((d_1, t_1), …, (d_k, t_k))` fixes one transitive
group `T(d_i, t_i)` per orbit, drawn from GAP's transitive group library.
`T(d_i, t_i)` is the smallest transitive group containing the projection of
`H` onto its `i`-th orbit. Given a combo, `H` sits as a subdirect product
inside the direct product `P = T(d_1, t_1) × ⋯ × T(d_k, t_k)`, embedded
blockwise into `S_n`. The per-combo job is therefore to enumerate the FPF
subdirect products of `P` up to `S_n`-conjugacy.

`build_sn_topt.py` is the orchestrator. It walks partitions, then walks the
multisets of `t`-indices per repeated degree, and dispatches each combo to
the cheapest backend that applies — closed-form fast paths when `P` has a
particularly nice structure, a two-factor Goursat predictor for combos that
admit a clean `L × R` split, and a wreath predictor for the single-species
`m ≥ 3` case.

### 2. Two-factor (Goursat) predictor

`predict_2factor_topt.py` reduces a `k`-block combo to a two-block product
`P = L × R`, choosing the split to minimise work (in distinguished mode the
unique-multiplicity species becomes `R`). Goursat's lemma then classifies
subdirect products `H ≤ L × R` as triples `(N_L, N_R, φ)` with `N_L ◁ L`,
`N_R ◁ R`, and `φ: L/N_L → R/N_R` an isomorphism. Up to the relevant
normalisers, FPF subgroups of `L × R` correspond to these triples modulo the
diagonal `Aut`-action on the shared quotient.

In practice the predictor pulls the FPF subgroups of `L` and `R` from the
cached per-combo files for smaller `m`, buckets them by normal-quotient
structure, and shares a per-LEFT cache of precomputed normal subgroups,
quotients, and `Aut(Q)` data across all the right-side jobs that follow.
That cache plus a tight filter restricting candidate quotients to those the
right side can actually produce is what makes the predictor competitive on
combos with large left-side lattices.

### 3. Wreath predictor

`predict_full_general_wreath.py` handles the single-species case
`P = T(d, t)^m` for `m ≥ 3`. The natural ambient group for conjugacy is
`W = N_{S_d}(T) ≀ S_m`, which respects the block structure and is vastly
smaller than `S_n`. The predictor generates candidate FPF subgroups as
`Aut(P)`-orbits (optionally bootstrapped from a two-factor candidate list),
buckets them by cheap invariants — order, refined `Aut(Q)`-bucket, block
permutation signature — and then runs `RepresentativeAction` tests *inside
`W`* to deduplicate. A block-cycletype refinement splits `C_2^k` buckets
that would otherwise collide.

### 4. Chief-series lifting core

Underneath both predictors sits the chief-series lifting machinery in
`lifting_algorithm.g`, an implementation of Holt's algorithm (*Enumerating
subgroups of the symmetric group*, 2010). Given a parent `P` and a target
subdirect projection, it builds a chief series for `P` with coprime layers
brought to the front, loads the subgroup classes of the trivial-Fitting top
`P/L` (computed once and cached), and then lifts those representatives down
the series one elementary-abelian layer at a time. Each layer `M/N` is
realised as an `F_p`-module, and complement enumeration goes through
`H^1(S/M, M/N)` cocycle orbits under the relevant normaliser — the orbital
machinery in `h1_action.g` and `modules.g` — rather than naive subgroup
enumeration. Survivors that aren't FPF are filtered at every layer for
early termination; what remains is deduplicated by normaliser action.

`lifting_method_fast_v2.g` is an older small-`n` driver that exposes the
same engine via `FindFPFClassesForPartition`. The production pipeline drives
`lifting_algorithm.g` directly through the Python predictors.

### 5. Output format

Each completed combo writes one file at `parallel_sn_<n>/<partition>/<combo>.g`:

```
# combo: [ [d_1, t_1], [d_2, t_2], ... ]
# candidates: C
# deduped: N
# elapsed_ms: T
[<gen_1>,<gen_2>,...]          # one subgroup per line
[<gen_1>,<gen_2>,...]
...
```

Each bracketed line is a GAP permutation-generator list for one conjugacy
class representative. The `# deduped: N` header is the authoritative class
count; the orchestrator reads it for both progress accounting and integrity
checks during resume.

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
- `build_sn_topt.py` — 23-line entry point.
- `runner/` — the orchestrator split into focused modules: `constants`,
  `combos`, `route`, `predictors`, `cache`, `batches`, `scheduler`.
- `auto_snapshot.py` — watchdog that auto-commits source edits to `dev`.

Predictors (Python wrappers around GAP workers)
- `predict_2factor_topt.py` — two-factor Goursat
  (`distinguished` / `holt_split` / `burnside_m2`).
- `predict_full_general_wreath.py` — wreath predictor (`m ≥ 3`, single species).
- `run_c2_fast_path.py`, `run_b_d8_path.py`, `run_b_elemab_path.py` — fast-path drivers.

GAP engine
- `lifting_algorithm.g` — chief-series lifting, layer-by-layer complement
  enumeration, FPF filtering.
- `modules.g`, `h1_action.g` — `F_p`-module realisation and orbital `H^1`
  complement enumeration.
- `lifting_method_fast_v2.g` — legacy small-`n` driver around the same engine.
- `b_d8.g`, `b_elemab_g.g` — closed-form / linear-algebra fast paths.

Verification
- `verify_s20_outputs.py` — completeness and per-file consistency for the
  `n = 20` tree.
- `sum_fpf_s20.py` — re-tallies FPF(20) from the extracted tarball.

## References

- D.F. Holt, *Enumerating subgroups of the symmetric group*, in *Computational
  Group Theory and the Theory of Groups, II*, AMS Contemp. Math. **511**, 2010
  (`a000019_1.pdf` in this repo).
- OEIS [A000638](https://oeis.org/A000638) — number of subgroups of `S_n`.
- The GAP Group, *GAP — Groups, Algorithms, Programming*, version 4.15.1.
