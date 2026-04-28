# S18 Pause State (2026-04-19)

## Status at pause

S18 parallel run was already halted before this session; no GAP or Python
processes running. Last worker heartbeats dated 2026-04-09 (10 days stale).

## Inventory

`parallel_s18/` contains:

- **114** archived partitions (`[partition].tar.gz`) — completed, compressed
- **88** uncompressed partition directories — completed or in-progress,
  each containing per-combo `.g` files of the form
  `[a,b]_[c,d]_[e,f].g` (generator-list snapshots per combo)
- Worker logs: `worker_0.log` through `worker_N.log` + matching
  `worker_N_heartbeat.txt`

## Example last-heartbeat state

`worker_0_heartbeat.txt`:
```
alive 43069s dedup 6965/13463
```

This worker was mid-dedup when halted — checkpointed state is in
`checkpoints/worker_0/` per the project's `.g`+`.log` convention.

## Resume compatibility

No code changes here. All checkpoints and combo output remain in place.
The Phase 9 resume (after new-engine validation) will reuse this directory
as-is; either the old engine or the new engine (if checkpoint format
stayed compatible) can resume from this state.

## Known totals

From `memory/MEMORY.md` baseline at start of session:
- S18 target: 7,274,651 (OEIS)
- Progress at pause: ~3.3M / 5.8M FPF classes (~57%)
- FPF(S18) target: 5,808,293 (= 7,274,651 − 1,466,358 inherited)
