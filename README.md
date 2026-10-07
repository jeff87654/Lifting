# Lifting

Enumeration of the conjugacy classes of subgroups of the symmetric group
`S_n`, extending [OEIS A000638](https://oeis.org/A000638) by three terms:
`a(19)`, `a(20)` and `a(21)` are first computed here. The same build also
produces the labelled counts [A005432](https://oeis.org/A005432) (all
subgroups of `S_n`, conjugates counted separately) and
[A116693](https://oeis.org/A116693) (the fixed-point-free part), which serve
as an independent cross-check and give three new terms of each sequence.

All data and code are archived on Zenodo:
[doi:10.5281/zenodo.23198808](https://doi.org/10.5281/zenodo.23198808)
(latest version; the current version, 1.1, is
[10.5281/zenodo.23221877](https://doi.org/10.5281/zenodo.23221877)).

## Results

| n  | a(n) = A000638(n)   | FPF(n)          | status                                  |
|----|--------------------:|----------------:|-----------------------------------------|
| 16 | 686,165             | 527,036         | OEIS, reproduced by this build          |
| 17 | 1,466,358           | 780,193         | OEIS, reproduced by this build          |
| 18 | 7,274,651           | 5,808,293       | OEIS, reproduced by this build          |
| 19 | **16,745,233**      | 9,470,582       | new (this build)                        |
| 20 | **104,994,596**     | 88,249,363      | new (this build)                        |
| 21 | **245,393,739**     | 140,399,143     | new (this build)                        |

`FPF(n)` is the number of conjugacy classes of subgroups of `S_n` with no
fixed point. Every class of `S_{n-1}` gives a class of `S_n` fixing the
point `n`, and every class with a fixed point arises this way exactly once,
so `a(n) = FPF(n) + a(n-1)`; the build only has to produce the FPF classes.

Labelled counts (`L(n)` = A005432, `L_FPF(n)` = A116693). These are exact
integers; the build reproduces both sequences exactly for every `n ≤ 18`,
which is as far as OEIS goes:

| n  | L_FPF(n) = A116693(n)                 | L(n) = A005432(n)                     |
|----|--------------------------------------:|--------------------------------------:|
| 19 | 84,018,278,813,226,053,237            | 211,617,083,874,387,340,422           |
| 20 | 15,346,960,414,746,000,263,759        | 18,255,021,894,055,495,567,796        |
| 21 | 226,997,825,369,382,551,513,614       | 575,368,155,943,196,927,537,588       |

`L(n) = Σ_m C(n,m) · L_FPF(m)`, and `L_FPF(n)` is the sum, over the FPF
classes `H`, of the class size `[S_n : N_{S_n}(H)]`.

## How the results are checked

No single check below is a proof. Together they rule out the usual ways an
enumeration like this goes wrong: missing classes, duplicated classes, and
classes in the wrong place.

1. **Known terms, from scratch.** The published build (July 2026, see
   [Provenance](#provenance)) started from an empty output tree and
   reproduces A000638(n) exactly for every `n = 2..18`. Its per-orbit-type
   counts also match brute-force `ConjugacyClassesSubgroups(S_n)` for every
   fixed-point-free orbit type of `S_12`, `S_13` and `S_17`.
2. **Labelled counts.** Every output file records `# class_sum:`, the sum of
   `[S_n : N_{S_n}(H)]` over its classes. Summing these reproduces A116693(n) exactly, and the
   binomial transform reproduces A005432(n) exactly, for every `n ≤ 18`.
   This is a different invariant from the class count. An error that leaves
   the number of classes unchanged would still have to leave the sum of
   their class sizes unchanged to pass both checks.
3. **Independent rebuilds.** `n = 21` has been built from scratch several
   times since June 2026, with fresh caches and different code each time.
   The published July build produced 49,490 of the 170,119 `n = 21` combos
   with the identity routes (see [Method](#method)), which did not exist
   when the June reference tree was built. It agrees
   with that tree **combo by combo**, on both `# deduped:` and
   `# class_sum:`, for all 416,849 FPF combos of `n = 2..21`, including all
   170,119 combos of `n = 21`.
4. **Brute-force spot checks.** An earlier count of `n = 21` was an
   undercount (see [History](#history-of-the-n--21-value)). The combos where
   the earlier and the final counts differ were re-checked by independent
   brute-force `RepresentativeAction` conjugacy testing, and the checks
   reproduced the final counts. These include the eight combos with an `S_3`
   block and a cluster of `D_8` blocks, for example `[2,1]_[3,2]_[4,3]^4`,
   which carry almost all of the difference.
5. **Structural scan.** In the June reference tree, every class
   representative for `n = 2..21` was checked to have orbits of exactly the
   sizes of its combo's blocks. This confirms that each class is FPF and
   filed under the right orbit type.
6. **Per-file integrity.** `verify_outputs.py` re-enumerates the expected
   combos of `n` independently, and checks that each output file exists and
   that its `# deduped:` header equals its number of representatives. It then
   re-adds `FPF(n)` and `L_FPF(n)`. Every archive linked below passes it.

## Method

### Orbit types and combos

A subgroup `H ≤ S_n` with no fixed point splits `{1, …, n}` into orbits of
sizes `d_1, …, d_k ≥ 2`, and acts on the `i`-th orbit as a transitive group
`T(d_i, t_i)` from GAP's transitive-groups library. The multiset
`c = {(d_1, t_1), …, (d_k, t_k)}` is the *combo* of `H`, which is a
conjugacy invariant. Within one combo, `H` is a subdirect product of
`T(d_1, t_1) × … × T(d_k, t_k)` embedded blockwise, and two such subgroups
are `S_n`-conjugate iff they are conjugate under the block-preserving
normaliser. The build enumerates every combo of every FPF partition of `n`
and, for each one, writes a complete list of class representatives. `n = 21`
has 165 FPF partitions and 170,119 combos.

### Two-factor Goursat engine

The general engine (`predict_2factor_topt.py`) splits a combo into two
sub-combos `L × R` and applies Goursat's lemma: subdirect products of
`L × R` correspond to triples `(N_L ◁ H_L, N_R ◁ H_R, φ)` with
`φ : H_L/N_L ≅ H_R/N_R`, where `H_L` and `H_R` run over the
already-computed classes of the smaller combos. Conjugacy is then resolved
by orbits of the normalisers on these triples, via double cosets in `Aut(Q)`
of the glue quotient `Q`. The split is chosen to minimise
`#classes(L) × #classes(R)`, and the split geometry (one distinguished
species, two clusters, a doubled species `T^2`) picks the mode. Per sub-combo
"H-caches" store, for each subgroup class, its normal subgroups with quotient
types relevant to the other side and the normaliser action on them.
Elementary-abelian, `D_8` and `O_p`-split glue quotients are found by linear
algebra over `F_p` (`prototype_stage_a.g` … `prototype_stage_d.g`) instead
of generic normal-subgroup searches. `_GoursatBuildFiberProduct` in
`lifting_algorithm.g` builds the fiber products.

### Routes

`runner/route.py` sends each combo to the first engine in this order that
applies:

| route | applies to | engine |
|---|---|---|
| `bootstrap` | one block | the transitive group itself (one class) |
| `c2_fast`, `b_power`, `bd8_fast`, `elemab_fast` | `T^k` for `T` = `C_2`; `C_3`, `S_3`, `C_4`, `V_4`, `D_8`; elementary abelian | closed-form / `GL_m(F_p) ≀ S_k`-orbit engines (`run_c2_fast_path.py`, `run_b_power_path.py`, `run_b_d8_path.py`, `run_b_elemab_path.py`) |
| `id_product`, `id_absorb`, `id_transfer` | combos covered by three counting identities (below) | pure-Python text materialisation from lower-`n` files (`run_identity_path.py`) |
| `c2_glue`, `c2_glue2`, `c3_glue` | exactly one or two `[2,1]` blocks, or one degree-3 block against a rest of order coprime to 3 | streaming Goursat with a fixed glue set `{1, C_2}`, `{1, C_2, V_4}` or `{1}` and no H-cache (`run_c2_glue_path.py`, `run_c2_glue2_path.py`) |
| `distinguished`, `holt_split`, `peel_c2_pair`, `burnside_m2` | everything else with ≥ 2 clusters or a species `T^2` | two-factor Goursat engine |
| `wreath_ra`, `wreath_via_2factor` | a single species `T^m`, `m ≥ 3` | candidates, then `RepresentativeAction` dedup inside `N_{S_d}(T) ≀ S_m` (`predict_full_general_wreath.py`) |

For `n = 21`, the `# engine:` headers of the published files show:

* streaming glue: 36,764 combos, 100,142,827 classes;
* identity routes: 49,490 combos, 9,215,325 classes;
* all other engines: 83,865 combos, 31,040,991 classes.

The three identities are theorems about subdirect products, and each one was
checked exactly (class counts and labelled sums) against every applicable
combo of an independently computed tree before it was used:

* **product:** if the blocks split into clusters whose orders have pairwise
  disjoint prime supports, every glue is trivial and
  `classes = ∏ classes(cluster)`;
* **absorb:** one block whose group is `A_d` or simple, against a rest of
  order coprime to `d`, contributes a direct factor:
  `classes = classes(rest)`;
* **transfer:** one block whose group `T` has order `2d` or `d!`, with the
  rest coprime to `d` and free of `[2,1]` blocks, glues exactly like a
  `[2,1]` block:
  `classes = classes([2,1] ∪ rest)`.

### Output format

Each combo is one file `<n>/<partition>/<combo>.g`, e.g.
`21/[5,4,4,4,2,2]/[2,1]_[2,1]_[4,3]_[4,3]_[4,3]_[5,5].g`:

```
# combo: [ [ 2, 1 ], [ 2, 1 ], [ 4, 3 ], [ 4, 3 ], [ 4, 3 ], [ 5, 5 ] ]
# candidates: 497248
# deduped: 497248
# class_sum: 106454153721091176000
# elapsed_ms: 387984
# engine: c2_glue2_stream
[(2,4)(6,8)(10,12),(1,4,3,2)(5,8,7,6)(9,12,11,10),(1,3)(2,4),...]
...
```

Each line starting with `[` is a GAP list of permutation generators for one
class representative; GAP wraps long lines with a trailing `\`. The headers
`# deduped:` (number of classes) and `# class_sum:` (sum of class sizes) are
authoritative. Header order varies between engines.

## Data

| archive | n | FPF classes | where |
|---|---|---:|---|
| `parallel_sn_1_17.tar.xz` | 1–17 | | repo root |
| `parallel_sn_18.tar.xz` | 18 | 5,808,293 | repo root |
| `parallel_sn_19.tar.xz` | 19 | 9,470,582 | repo root |
| `parallel_sn_20.tar.xz` | 20 | 88,249,363 | [release `s20-results`](https://github.com/jeff87654/Lifting/releases/tag/s20-results) |
| `parallel_sn_21.tar.xz` | 21 | 140,399,143 | [release `s21-results`](https://github.com/jeff87654/Lifting/releases/tag/s21-results) |
| `combo_class_counts_s2_s21.csv.gz` | 2–21 | per combo | repo root |

Everything above is also archived permanently on Zenodo,
[doi:10.5281/zenodo.23198808](https://doi.org/10.5281/zenodo.23198808). There
the n = 20 and n = 21 archives are split into 64 MiB pieces; rejoin them with
`cat parallel_sn_21.tar.xz.part* > parallel_sn_21.tar.xz` and check the result
against `SHA256SUMS`.

The archives for `n ≤ 19` predate the labelled harvest and carry no
`# class_sum:` headers. `combo_class_counts_s2_s21.csv.gz` lists every FPF
combo for `n = 2..21` with its class count and labelled sum, taken from the
published build. It is enough to re-add every total above without
downloading the large archives.

### Verifying a release

```sh
# streams the archive; nothing is extracted
python verify_outputs.py --n 21 --tar parallel_sn_21.tar.xz
python verify_outputs.py --n 20 --tar parallel_sn_20.tar.xz
python verify_outputs.py --n 2-17 --tar parallel_sn_1_17.tar.xz

# or on an extracted tree: tar xf parallel_sn_21.tar.xz; python verify_outputs.py --n 21
```

For each `n` this prints the number of expected, missing and extra combos,
header/line mismatches, `FPF(n)`, `a(n) = FPF(n) + a(n-1)` and `L_FPF(n)`,
each compared against OEIS or the values above, and exits non-zero on any
failure.

## Provenance

The `n = 21` archive and the code in this repository are from the
**val0702** build: a complete from-scratch run of `n = 2..21` started on
2026-07-02 with fresh caches. `n = 21` ran from 2026-07-03 to 2026-07-04,
about 20 hours wall-clock, with 8 worker processes on one laptop (Intel
i7-11800H, 8 cores, 64 GB RAM). The software was GAP 4.15.1 under Cygwin on
Windows 11, driven from Python 3.11.

The code here is byte-identical to that build's working tree. The only
exceptions are comments in `runner/constants.py` and seven files that were
untracked at the time and are restored from their identical copies:
`b_c4.g`, `b_d8_v2.g`, `b_elemab.g`, `b21_writer_final.g`, `b21_canonical.g`
and `b21_support_first.g`, which the build reads, and
`predict_full_general.py`, which `verify_wreath_dedup.py` uses. The files are
otherwise as they ran. In particular, paths are hard-coded to
`C:/Users/jeffr/Downloads/Lifting` and GAP is started through Cygwin `bash`
(`runner/constants.py`, `runner/predictors.py`). Running the build elsewhere
means adjusting those paths.

```
python -u build_sn_topt.py --n-min 2 --n-max 21 \
  --out parallel_sn_<run> \
  --h-cache predict_species_tmp/_h_cache_<run> \
  --predictor-tmp predict_species_tmp/_two_factor_<run> \
  --workers 8 --super-batch-jobs 10
```

The build is resumable: re-running the same command skips every combo whose
output file is complete. At the end of each `n` the scheduler re-counts the
output tree and prints the `FPF(n)`, `a(n)`, `L_FPF(n)` and `L(n)` checks.

## History of the n = 21 value

The first count of `n = 21` (May 2026, FPF 130,186,467, giving
`a(21) = 235,181,063`) was wrong. It was computed before a fix to the glue
quotient test that had dropped genuine 2-group quotients of rank ≥ 2 when two
clusters of 2-groups are glued. The same bug made the first `n = 20` release
asset a slight undercount; it was replaced in June 2026. That old reference
tree also had a few duplicated classes. Rebuilt after the fix, exactly 20 of
the 170,119 combos of `n = 21` changed, all upward, by 10,212,676 classes in
total. Every later build has reproduced the corrected value exactly.

## Code layout

Orchestration
- `build_sn_topt.py`: entry point, which calls `runner.scheduler.main()`.
- `runner/`: `scheduler.py` (per-`n` loop, retry rounds, recount and
  validation), `route.py` (routing), `batches.py` (job packing),
  `predictors.py` (subprocess wrappers), `combos.py`, `cache.py`,
  `constants.py` (sequence values, route tables).
- `labelled_postpass.py`, `labelled_oracle.g`: labelled-count harvest and an
  independent block-wreath normaliser check.
- `verify_outputs.py`: verifier for the published data (above).
- `auto_snapshot.py`: development helper that auto-commits edits.

Engines
- `predict_2factor_topt.py`: two-factor Goursat engine (GAP drivers embedded
  as strings); `prototype_stage_{a,b,c,d}.g` are its linear-algebra
  normal-subgroup enumerators.
- `run_identity_path.py`: identity routes (no GAP).
- `run_c2_glue_path.py` + `c2_glue_path_writer.g` (`c2_glue`, `c3_glue`),
  `run_c2_glue2_path.py` + `c2_glue2_path_writer.g` (`c2_glue2`): streaming
  glue engines.
- `run_c2_fast_path.py`, `run_c2_factor_path.py`, `c2_fast_path_writer.g`,
  `b21_writer_final.g`, `b21_canonical.g`, `b21_support_first.g`: pure
  `C_2^k`.
- `run_b_elemab_path.py`, `b_elemab.g`, `b_elemab_g.g`: elementary abelian
  `T^k`.
- `run_b_power_path.py`, `b_power/`, `b_c4.g`: `C_3`/`S_3`/`C_4`/`V_4`/`D_8`
  powers.
- `run_b_d8_path.py`, `b_d8.g`, `b_d8_v2.g`, `database/bd8_u_orbits/`:
  `D_8^k`.
- `b_*_harvest.g`: labelled sums for the closed-form engines.
- `predict_full_general_wreath.py` (alias `wreath_ra_dedup.py`),
  `run_wreath_via_2factor.py`: wreath engine; `verify_wreath_dedup.py`
  cross-checks it against `predict_full_general.py`, which dedups under the
  full `S_n`.
- `lifting_algorithm.g` (fiber products) plus `modules.g`, `h1_action.g`,
  `cohomology.g`, `lifting_method_fast_v2.g`: the original Holt-style
  chief-series lifting code. It is still loaded, but only the
  fiber-product helpers are on the production path.
- `database/`: transitive-group data and `tg_orders.json`
  (`|T(d,t)|`, used by the router).
- `HCACHE_STREAMING_PROPOSAL.md`: design notes for the streaming H-cache.

## Citing and license

To cite this work, use GitHub's "Cite this repository" button (generated from
`CITATION.cff`), or cite: Jeffrey Ketchersid, *Conjugacy classes of
subgroups of the symmetric groups S_n, n ≤ 21*, Zenodo,
[doi:10.5281/zenodo.23198808](https://doi.org/10.5281/zenodo.23198808).

The code is released under the MIT License (`LICENSE`). The data — the
`parallel_sn_*.tar.xz` archives and `combo_class_counts_s2_s21.csv.gz` — is
released under CC BY 4.0 (`LICENSE-DATA`): you may use it for any purpose,
provided you give credit.

## References

- D. F. Holt, *Enumerating subgroups of the symmetric group*, in
  *Computational Group Theory and the Theory of Groups, II*, Contemp. Math.
  **511**, AMS, 2010.
- OEIS [A000638](https://oeis.org/A000638), [A005432](https://oeis.org/A005432),
  [A116693](https://oeis.org/A116693).
- The GAP Group, *GAP — Groups, Algorithms, and Programming*, version 4.15.1.
