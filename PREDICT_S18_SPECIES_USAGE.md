# Species-aware S18 prediction tools

Three Python scripts predict and verify per-combo S18 conjugacy class counts
using the orbit-species idea (`(degree, TransitiveIdentification)` pairs).
The single-block addition formula is exact for any distinguished added orbit
species, generalizing `predict_s18_from_s16.py` from `+[2]` to `+[d, t]`.

## Files

- **`predict_s18_species.py`** — main predictor / GAP driver
- **`compare_s18_species.py`** — per-combo prediction-vs-actual report
- **`predict_s18_parallel.py`** — runs `predict_s18_species.py` across
  multiple S18 partitions concurrently (`ProcessPoolExecutor`)

Output is written to `predict_species_tmp/<n>/<combo>/from_<dt>/result.json`.

## Verifying the predictor (do this before trusting bug-localization)

```bash
# Small-case sanity checks (no GAP cost):
python predict_s18_species.py --target 6 --all
python predict_s18_species.py --target 7 --all
python predict_s18_species.py --target 8 --all
```

Expect every distinguished combo to print `delta=+0 CONSISTENT`. Total `MATCH`
count must equal `n_distinguished` for each S_n.

```bash
# Full FPF-total validation against OEIS:
python predict_s18_species.py --validate-fpf 9
# Expect: predicted_total + non_predictable_actuals = 258
```

The predictor is verified up to S9 in `~1 minute`; S10..S15 take longer.
Run S15 only after small-case verification passes.

## Predicting S18 (the main use case)

### Single partition
```bash
python predict_s18_species.py --target 18 --partition "[10,8]" --batch
```
- `--batch` groups jobs by `(d, t, m)` so GAP cold-start (~5.5s) is
  amortized across many predictions. Without `--batch` each prediction is
  6+ seconds; with `--batch` per-prediction is 0–300 ms after one warm-up.
- Add `--cheapest-only` to run only the smallest-`d` distinguished
  decomposition per combo (~2x speedup, loses cross-source consistency).
- Add `--force` to re-run even if `result.json` already exists.

### All S18 partitions in parallel
```bash
python predict_s18_parallel.py --workers 8 --cheapest-only
```
- 8-way concurrency; each worker handles one partition at a time.
- Largest partitions are scheduled first for better load balance.
- Each worker writes `predict_species_tmp/_parallel_logs/<partition>.log`.
- Final summary at `predict_species_tmp/_parallel_logs/_parallel_summary.json`.

Skip very large partitions if needed:
```bash
python predict_s18_parallel.py --workers 8 --cheapest-only --skip-larger-than 1000
```

## Reporting bugs / discrepancies

```bash
python compare_s18_species.py --limit 10
```

Per-combo classifier output:
- `EXACT_MATCH` — distinguished, prediction == actual (S18 looks correct here)
- `OVER` — distinguished, prediction < actual → likely **dedup bug** in S18
- `MISSING` — distinguished, prediction > actual → likely **enumeration bug** in S18
- `INCONSISTENT_SOURCES` — multiple distinguished decompositions disagree → predictor bug
- `NON_PREDICTABLE` — every species in the combo repeats; needs manual inspection
  (or 2-block bridging — not yet implemented)
- `NO_PREDICTION` — distinguished but no source data / GAP failed

`--all` shows every row including matches; `--limit N` caps each bug category at N.

Final report: `predict_species_tmp/18/_compare_report.json`.

## Known scaling notes

- GAP cold-start: **5.5s per process**. Without `--batch` this is the
  per-prediction floor.
- Heavy added orbits (`d ≥ 6`): TransitiveGroup(d, t) for large `t` (near
  A_n / S_n) builds large `Aut(Q)` which slows BFS-based orbit counting.
  Guarded by `IsomorphicGroups` size filtering and the source-side
  `AllowedSizes` filter, so impact is bounded.
- IdGroup unavailable for some sizes (e.g., 7200, 1024) — handled by
  `SafeId` fallback `(Size, AbelianInvariants, DerivedSeries sizes)`.
