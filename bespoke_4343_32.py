"""bespoke_4343_32.py — bespoke run of [3,2]_[4,3]_[4,3]_[4,3]_[4,3] (n=19,
partition [4,4,4,4,3]) with the _EnumerateNormalsForQGroups fix.

Distinguished mode pivots on the unique [3,2] factor:
    LEFT  = [4,3]_[4,3]_[4,3]_[4,3]    (n=16, partition [4,4,4,4])
    RIGHT = [3,2]                       (n=3, M_R=3)
    LEFT_Q_GROUPS for M_R=3 = quotients of TransitiveGroup(3, *) = [C_3, S_3]

Tests the fix on a mixed-Q workload: C_3 hits the abelianization fast path,
S_3 hits GQuotients(H, S_3). Pre-fix this would have hammered NormalSubgroups
on every |H| <= 10^6.

Sandbox cache to predict_species_tmp_bespoke_4343_32/ to avoid stomping any
later n=18/n=19 build work.
"""
import os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).parent
SANDBOX = ROOT / "predict_species_tmp_bespoke_4343_32"
SANDBOX.mkdir(exist_ok=True)
(SANDBOX / "_h_cache").mkdir(exist_ok=True)
(SANDBOX / "_tmp").mkdir(exist_ok=True)

env = os.environ.copy()
env["PREDICT_H_CACHE_DIR"] = str(SANDBOX / "_h_cache")
env["PREDICT_TMP_DIR"] = str(SANDBOX / "_tmp")
env["PREDICT_SN_DIR"] = str(ROOT / "parallel_sn_topt")

combo = "[3,2]_[4,3]_[4,3]_[4,3]_[4,3]"
out = SANDBOX / "result.g"
print(f"Bespoke run: {combo}")
print(f"  LEFT cache target: {SANDBOX/'_h_cache/16/[4,4,4,4]/[4,3]_[4,3]_[4,3]_[4,3].g'}")
print(f"  Live: tail -f {SANDBOX}/_tmp/{combo}/run.log")
t0 = time.time()
proc = subprocess.run(
    [sys.executable, str(ROOT / "predict_2factor_topt.py"),
     "--combo", combo,
     "--mode", "distinguished",
     "--output-path", str(out),
     "--emit-generators",
     "--force"],
    env=env, capture_output=True, text=True, timeout=4*3600)
elapsed = time.time() - t0
print(f"\nDone in {elapsed:.0f}s, rc={proc.returncode}")
if out.exists():
    print(f"Output: {out.stat().st_size} bytes")
    with open(out) as f:
        for _ in range(4): print("  " + f.readline().rstrip())
print("\n--- last 1500 chars of stdout ---")
print(proc.stdout[-1500:])
if proc.stderr:
    print("\n--- last 800 chars of stderr ---")
    print(proc.stderr[-800:])
