"""
Launch only Worker C with combos reordered: smallest (fastest) first,
slowest ([6,3]_[6,16]^2 and [6,16]^3) last.
This way we make progress even if hard combos hang.
"""
import os, time, subprocess
import rerun_82_combos as r

ROOT = r.ROOT
LOGDIR = r.LOGDIR
os.makedirs(LOGDIR, exist_ok=True)

by_part = r.parse_rerun_list()
by_part["[6,6,6]"].append([[6,16],[6,16],[6,16]])

# Filter out already-done
CUTOFF = time.mktime(time.strptime("2026-04-25 18:30:00", "%Y-%m-%d %H:%M:%S"))
combos = [c for c in by_part["[6,6,6]"]
          if not (os.path.exists(f"{ROOT}/parallel_s18/[6,6,6]/" + "_".join(f"[{x[0]},{x[1]}]" for x in sorted(c)) + ".g")
                  and os.path.getmtime(f"{ROOT}/parallel_s18/[6,6,6]/" + "_".join(f"[{x[0]},{x[1]}]" for x in sorted(c)) + ".g") > CUTOFF)]

# Predictor values from rerun list (for sorting by expected difficulty/size).
# k -> predictor for [6,k]_[6,16]_[6,16]
pred = {
    11:22, 13:22, 3:22, 9:16,
    10:9, 14:9, 1:9, 2:9, 5:9, 6:9, 7:9, 8:9,
    12:4, 15:4, 4:4,
    16: 999  # unknown / probably slowest [6,16]^3
}

# combo is in partition order [6,k1, 6,k2, 6,k3] - find the k that's not 16
def difficulty(c):
    # In partition order, factors are descending degree (all 6 here).
    # For [6,k]_[6,16]_[6,16], the "k" is the one that's not 16.
    ks = [pair[1] for pair in c]
    other = [k for k in ks if k != 16]
    if not other:  # [6,16]^3
        return pred[16]
    return pred.get(other[0], 99)

combos.sort(key=difficulty)
print(f"Worker C will process {len(combos)} combos in difficulty order:")
for c in combos:
    print(f"  {c}  difficulty={difficulty(c)}")

# Generate worker script
g_file, log_file = r.make_worker_g("C", "[6,6,6]", combos)
proc, sout, serr = r.launch(g_file, "C")
print(f"\nWorker C launched, pid={proc.pid}")
