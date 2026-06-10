# Proposal: streaming/incremental H-cache build (the S22 monster-cache fix)

Status: **PHASE 1 LANDED, DEFAULTS ON** (2026-06-09 commit 4a9284c7b8;
defaults flipped 0571cebe1f, user-approved 06-09).
`PRED_STREAM_HCACHE_BUILD` / `PRED_FRAMED_CACHE` / `PRED_LAZY_LEFT_RECON` all
default 1; opt out with `=0`.
**Gate 3 PASSED 2026-06-10**: fresh n=2..15 smoke on the bare defaults
(`parallel_sn_stream_smoke15`) — FPF vs A000638 and labelled
A116693/A005432 green at every n; `diff_smoke_deduped.py` vs
`parallel_sn_v3only` = 0 differing combos (159,128 total). The run survived
an overnight machine shutdown mid-n=14 and resumed cleanly. Corroborated by
the c2_glue/prelaunch/opt0610 runs, which all executed post-flip on
framed+streamed caches. Gate 4 (250k dress rehearsal) still pending before
an S22 monster attempt.
`BuildHCacheStreaming` + `_StreamHCacheValidLine` + `_StreamBuildingHeaderOk`
in `_SHARED_HELPERS`; stream branches in all three drivers; BATCH goes
windowed after a >= `PRED_STREAM_WINDOW_MIN` (20k) fresh build; Python
`_claim_stale_building` adopts dead workers' orphans (ver+count+staleness
gates, `PRED_BUILDING_STALE_S` default 30 min; a false claim of a live
builder is caught by the builder's flush-time header re-check, which aborts
loudly before any publish — see §4 hardening below). `_HCACHE_BUILD_VER`
(Python constant, hand-bumped) is the §8.1 version marker, stored in the
`.building.idx` header (NOT in the `.g`, which stays byte-identical to
`SaveHCacheFramed` output).
Validation: gates 1-2 passed at unit level (`_test_stream_hcache.py`, 23/23:
writer byte-equivalence, ckpt-quit resume across real GAP sessions, partial
tail / sidecar-behind / sidecar-ahead / ver-mismatch / foreign-coverage /
publish-gate / flush-path / claim-race cases), plus a BATCH end-to-end check
(`_test_stream_batch_e2e.py`: `[2,1]_[4,3]_[4,3]` with
`PRED_STREAM_WINDOW_MIN=10` exercises stream-build → WINDOWED pair loop;
deduped=78 / class_sum=2154600 identical to the legacy run and to the
validated staged_smoke15 tree). Gate 3 (orchestrator smoke n=2..15) + gate 4
(250k dress rehearsal) PENDING — blocked on the machine being busy with the
parallel_sn_opt0609 full run + emit bench; run them before flipping the flag
on:
```
python -u build_sn_topt.py --n-min 2 --n-max 15 \
  --out parallel_sn_stream_smoke --h-cache predict_species_tmp/_h_cache_stream_smoke \
  --predictor-tmp predict_species_tmp/_two_factor_stream_smoke --workers 8 --super-batch-jobs 10
# with PRED_FRAMED_CACHE=1 PRED_LAZY_LEFT_RECON=1 PRED_STREAM_HCACHE_BUILD=1
# then: python diff_smoke_deduped.py parallel_sn_v3only parallel_sn_stream_smoke
```

Original proposal follows. Implements the change deferred on 2026-06-07
("incremental-append save + fully-streaming build — a byte-identical-validated
standalone change for the NEXT fresh run"). The S21 frontier run that blocked
landing it is complete, so the window is open. This is the prerequisite for
the n=22 combo `[2,1]_[4,3]^5`, whose LEFT cache is **D8^5 = 1,604,827
entries** — 6.4x larger than the largest cache ever built by this pipeline.

## 1. Problem (measured)

The fresh-build loop (`predict_2factor_topt.py` ~5233–5286 in BATCH, mirrored
in GAP/SUPER) is:

```gap
for hi in [BUILD_START_HI..Length(SUBGROUPS_LEFT_RAW)] do
    Add(H_CACHE, ComputeHCacheEntry(SUBGROUPS_LEFT_RAW[hi], W_ML, LEFT_Q_GROUPS));
    # every 30 min: SaveHCacheList(CACHE_LEFT_PATH, H_CACHE)  <- WHOLE partial
    # every 2 h: same + state.g RESUME_BUILD(next_hi) + QuitGap
od;
SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
```

Three O(N) costs, all measured on the S21 monsters (2026-06-07 prod test):

1. **O(N) resident entry list** — the 250k-entry LEFT build held ~32 GB at 88%
   complete (single worker; distinct from the pair-loop balloon already fixed
   by gens-streaming). Linear extrapolation to 1.6M entries: ~200 GB. Not
   buildable.
2. **O(N) soft-save** — every 30-min checkpoint re-serializes the ENTIRE
   partial via `SaveHCacheList`: 17–20 min/save at 250k entries ≈ **~75% of
   build wall-time**. At 1.6M entries a single save would exceed the soft-save
   interval — the build would do nothing but checkpoint.
3. **O(N) source list** — `Read(SUBS_LEFT_PATH)` materializes all of
   `SUBGROUPS_LEFT_RAW` as Group objects up front (~29 s and a few GB at 197k;
   ~3–6 GB est. at 1.6M — survivable on 64 GB, but worth streaming too).

Additionally, the 30-min soft-saves publish **partials to the shared cache
path**, which is the root of correctness-review hole #1 (partial-as-RIGHT
silent undercount; today mitigated downstream by `EnsureHCacheComplete` +
`CountSubsGroupLines` gating).

## 2. Goals / non-goals

Goals:
- O(1) build memory in N (entry written to disk and released).
- O(ΔN) checkpoint cost (append + flush; no re-serialization, no relaunch
  needed for memory reasons).
- Crash-consistent resume with the **cache file itself as the single source
  of truth** (same philosophy as the validated gens-stream `# cp` rework;
  retires `RESUME_BUILD` state.g).
- The shared canonical path only ever carries **complete** caches (kills the
  partial-clobber hazard class at the source instead of healing it later).
- Full compatibility with every existing reader (`ReadHCacheAuto`, framed +
  monolithic, `OpenHCacheWindow` windowed reads, coverage tags,
  `EnsureHCacheComplete`, the 06-09 count-aware rules).
- Byte-level validation discipline equal to the gens-streaming change.

Non-goals (explicitly out of scope):
- `ExtendHCacheEntry` coverage extension stays a full-load + full-rewrite
  path. Monster LEFTs have their coverage fixed up-front by RIGHT-bounded
  Q-discovery (the D8^5 case is C2-only), so extension of a monster cache is
  not a real workload; if it ever fires, it full-loads exactly as today.
- Cross-worker sharded builds (phase 3 option, see §7).
- Any change to entry CONTENT or to `ComputeHCacheEntry` math.

## 3. Design

### 3.1 Append-streaming build into a private `.building` file

New shared helper `BuildHCacheStreaming(subs, amb, q_groups, path)` in
`_SHARED_HELPERS` (one copy; called from all three drivers' build blocks),
gated by `PRED_STREAM_HCACHE_BUILD=1`:

- Open `<path>.building.<pid>` (process-private — no cross-process clobber by
  construction) with header:
  - line 1: `# coverage_qids: ...;` (unchanged — coverage = `LEFT_Q_GROUPS`,
    known before the loop starts)
  - line 2: `# hcache_framed: count=<N_expected>` (N = `Length(subs)`, known
    up front)
  - line 3 (new, ignored by readers): `# hcache_building: ver=<engine marker>`
- Per entry: `s := String(ComputeHCacheEntry(...))`; `WriteAll(stream, s)` +
  newline; append the byte offset to the **append-friendly sidecar**
  `<path>.building.<pid>.idx` (one decimal offset per line — the canonical
  `HCACHE_OFFSETS := [...]` single-statement format is not appendable);
  release the entry (no list).
- Flush both streams every 500 entries or 60 s (matches the existing
  heartbeat cadence). Soft checkpoints become these flushes — the 30-min
  `SaveHCacheList` calls in the build loop are deleted.
- On completion (entries written == N_expected, else `Error` loudly):
  - convert the line-sidecar to the canonical `.idx` format,
  - publish exactly as `SaveHCacheFramed` does today: atomic `mv` of `.idx`
    first, then the main file onto `<path>` — readers never observe a torn
    state (`IsFramedCacheFile` detects via the `.g` marker alone;
    `OpenHCacheWindow` falls back to full read if `.idx` is briefly absent).

The published file is **byte-identical to what `SaveHCacheFramed` would have
written for the same entry list** (same header, same `String(entry)` lines,
same `.idx` semantics) — so every existing reader works unchanged, and the
validation can literally diff the two writers' output.

### 3.2 Resume = adopt the `.building` file

On build start, before computing anything:
1. Scan for `<path>.building.*`. If present, pick the one with the most
   complete entries; discard it if its `ver=` marker mismatches the current
   engine marker (the `hcache_reuse_across_code_changes_unsafe` lesson:
   never mix entries computed by different enumeration code).
2. Validate cheaply: read the line-sidecar; cross-check the last offset
   against file size; if the sidecar is behind (crash between flushes), scan
   forward line-by-line from the last known-good offset, `EvalString` only
   the FINAL line to confirm integrity, and truncate any partial trailing
   line. (Entries are written strictly in `hi` order, so this preserves the
   prefix invariant that `EnsureHCacheComplete` and the 06-06 undercount fix
   rely on.)
3. Resume the loop at `hi = entries_present + 1`, appending. No `state.g`
   involvement; `RESUME_BUILD` is retired for streamed builds (kept for the
   legacy path).

The 2-h hard-checkpoint QuitGap is no longer needed for memory, but is KEPT
(relaunch revalidates + adopts the `.building` file) because it also bounds
GAP long-runtime degradation — it just becomes nearly free.

### 3.3 Pair-loop access after a fresh build: always-windowed

Today `USE_WINDOWED_LEFT` fires only on a pure pair-loop **resume**. With
streaming, the freshly published cache is never in memory, so after the
publish the BATCH driver opens it with `OpenHCacheWindow` and runs the pair
loop windowed (`GetHCacheEntry(i)` + `ReconstructHData`, exactly the
already-validated resume path), keeping build→pair-loop memory O(1)
end-to-end. Small caches (< ~20k entries, tunable) full-load as today — no
behavior change where the current code is fine. Requires `PRED_FRAMED_CACHE=1`
and `PRED_LAZY_LEFT_RECON=1` as defaults (already the USER directive for
future runs) and lands together with the deferred 06-07 follow-up: on a
windowed pair-loop resume, derive `LEFT_Q_GROUPS` from the cache's line-1
coverage tag and **skip the `subs_left.g` re-read** (~29 s/epoch on monsters).

### 3.4 Source-side streaming (phase 2, separable)

The build loop touches `SUBGROUPS_LEFT_RAW[hi]` once, in order. Replace the
up-front `Read(SUBS_LEFT_PATH)` with a line-iterator (`subs` files carry one
`Group(...)` per line — the `CountSubsGroupLines` precedent) that constructs
and releases one group per entry. The Q-type-derivation pass at job start
still needs a full sweep; it can stream the same way in a first pass (it only
needs each group transiently for h_to_qs lookups). At ~3–6 GB for the D8^5
source list this is a robustness improvement rather than a blocker — ship as
a follow-up so phase 1 stays small and auditable.

## 4. Failure-mode analysis

| failure | outcome |
|---|---|
| kill mid-entry-write | trailing partial line; resume truncates to last complete entry (§3.2.2) |
| kill between `.g` flush and sidecar append | sidecar behind; forward-scan regenerates offsets |
| kill during publish | `mv` is atomic per file; idx-first ordering means worst case = new `.idx` + old `.g`, which `OpenHCacheWindow`'s count cross-check rejects → full read; next build re-publishes |
| orphaned `.building` from an old engine version | discarded by `ver=` marker mismatch → fresh build |
| two workers building the same LEFT path | each writes its own private `.building.<pid>`; duplicate work (same as today), last publish wins atomically; both publishes are complete & internally consistent |
| disk full | `WriteAll` fails → GAP error → job dies loudly; no partial published to the canonical path (strictly better than today) |
| source file changed between build sessions | `count=` header vs `Length(subs)` mismatch on adoption → discard `.building`, rebuild (mirrors `EnsureHCacheComplete`'s over-length Error policy) |

## 5. Expected wins

- 250k-entry monster (measured baseline): soft-save overhead (~75% of build
  wall) → ~0; build RAM ~32 GB → O(1) (a few GB transient). Build wall ≈
  pure compute.
- D8^5 (1.6M entries, C2-only coverage): per-entry ≈ Normalizer + Stage-A
  linear orbits ≈ 10–30 ms → **~4.5–13 h single worker, flat memory** —
  feasible. (Phase 3 sharding would cut this to ~1–2 h but adds an
  orchestrator task type; decide after a dress rehearsal, see §7.)
- Every restart of a monster job stops paying the O(N) cache re-parse + the
  O(N) re-serialization; combined with windowed reads this makes monster
  combos restart in seconds.

## 6. Validation plan (gate to land, in order)

1. **Writer equivalence**: build a mid-size cache twice in one session — once
   via the in-memory list + `SaveHCacheFramed`, once via the streaming
   builder fed the same precomputed entries — assert byte-identical `.g` and
   `.idx`.
2. **Kill matrix**: scripted kills at mid-line / between flushes / pre-publish
   / between idx-mv and g-mv; resume each; final cache must equal the
   uninterrupted build (count + per-entry `String` equality) and downstream
   combo output must match.
3. **Orchestrator smoke** n=2..15, fresh trees, `PRED_FRAMED_CACHE=1
   PRED_LAZY_LEFT_RECON=1 PRED_STREAM_HCACHE_BUILD=1`: OEIS + labelled all
   OK, `diff_smoke_deduped.py` vs `parallel_sn_v3only` = 0 differing combos.
   (Today's Stage-D smoke re-established this baseline.)
4. **Dress rehearsal**: rebuild the real 250,965-entry `[3,2]_[4,3]^4` LEFT
   cache (n=19 sources in `parallel_sn_topt_fresh_0604`) with the old and new
   builders; compare wall, peak RAM, and a downstream n=21 combo's
   deduped/class_sum.
5. Only then attempt D8^5.

## 7. Rollout & sequencing

- Env-gated `PRED_STREAM_HCACHE_BUILD` (default 0) → flip to default-on after
  gates 1–4, alongside the already-directed `PRED_FRAMED_CACHE=1` /
  `PRED_LAZY_LEFT_RECON=1` defaults.
- Independent of the emit-path investigation (different code regions); both
  must land before an S22 attempt.
- Phase 2 (source streaming + Q-derivation streaming) and phase 3 (sharded
  build: split `[1..N]` into per-worker ranges, each streams its own shard,
  finalize = byte-concat + offset-shift merge of sidecars) are separable
  follow-ups; phase 3 only if the D8^5 dress-rehearsal wall time is
  unacceptable.

## 8. Open questions

1. Engine-version marker granularity: hash of the `_SHARED_HELPERS` enum
   section vs a hand-bumped constant. (Recommend hand-bumped constant —
   deterministic, no false invalidations from comment edits.)
2. Whether SUPER/GAP drivers get the windowed pair-loop too or keep full-load
   (their caches are small by routing; recommend: builder shared, windowed
   stays BATCH-only, matching today's structure).
3. Adoption of `.building` files older than some age? (Recommend: no age
   limit; the `ver=` + count checks are the real guards.)
