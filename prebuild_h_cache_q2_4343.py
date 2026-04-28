"""Prebuild the Q=[C_2] H_cache for source [4,3]_[4,3]_[4,3]_[4,3] (n=16, partition [4,4,4,4]).

This is the LEFT source for n=18 combo [2,1]_[4,3]_[4,3]_[4,3]_[4,3]
(distinguished mode, M_R=2 ⇒ LEFT_Q_GROUPS = [C_2] only).

Writes to a sandbox H_cache dir to avoid colliding with the live n=18 build.
After completion, the cache file can be moved into predict_species_tmp/_h_cache_topt/.

Source has 12,525 FPF subgroups (vs 2,777 for [4,3]^3). The current [3,2]_[4,3]^3
run is ~6% through after 34 min — project ~9h for [4,3]^3 with Q=C_2,
~45h for [4,3]^4 with Q=C_2 if rate is the same per-H.
"""
import os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).parent
SANDBOX = ROOT / "predict_species_tmp_q2_test"
SANDBOX.mkdir(exist_ok=True)
(SANDBOX / "_h_cache_topt").mkdir(exist_ok=True)
(SANDBOX / "_two_factor_topt").mkdir(exist_ok=True)

env = os.environ.copy()
env["PREDICT_H_CACHE_DIR"] = str(SANDBOX / "_h_cache_topt")
env["PREDICT_TMP_DIR"] = str(SANDBOX / "_two_factor_topt")
env["PREDICT_SN_DIR"] = str(ROOT / "parallel_sn_topt")

# Use distinguished mode with M_R=2 (the [2,1] pivot).
# This forces LEFT_Q_GROUPS = [C_2] only — same as what the live [3,2]_[4,3]^3 run sees.
combo = "[2,1]_[4,3]_[4,3]_[4,3]_[4,3]"
out = SANDBOX / "result.g"

print(f"Starting prebuild for {combo} -> cache at {SANDBOX/'_h_cache_topt/16/[4,4,4,4]/[4,3]_[4,3]_[4,3]_[4,3].g'}")
print(f"Live progress: tail -f {SANDBOX}/_two_factor_topt/[2,1]_[4,3]_[4,3]_[4,3]_[4,3]/run.log")
t0 = time.time()
proc = subprocess.run(
    [sys.executable, str(ROOT / "predict_2factor_topt.py"),
     "--combo", combo,
     "--mode", "distinguished",
     "--output-path", str(out),
     "--emit-generators",
     "--force"],
    env=env, capture_output=True, text=True, timeout=10*3600)
elapsed = time.time() - t0
print(f"Done in {elapsed:.0f}s, rc={proc.returncode}")
print("Last stdout:")
print(proc.stdout[-2000:])
print("Last stderr:")
print(proc.stderr[-1000:])
