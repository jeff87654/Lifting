"""bench_pivot_compare.py — profile the 3 distinguished-pivot choices for
combo [2,1]_[2,1]_[2,1]_[3,2]_[4,3]_[6,3] to see if the smallest-LEFT heuristic
in resolve_inputs is suboptimal.

Bypasses resolve_inputs by monkey-patching it to force a specific pivot.
Runs each variant in an isolated sandbox H_cache dir so they don't share state.
"""
import os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).parent
COMBO = "[2,1]_[2,1]_[2,1]_[3,2]_[4,3]_[6,3]"
PIVOTS = [(3, 2), (4, 3), (6, 3)]

def build_driver(pivot_d, pivot_t):
    """Build a wrapper script that monkey-patches resolve_inputs to force
    the given pivot, then calls predict() on the combo."""
    return f'''
import sys, os, time
sys.path.insert(0, r"{ROOT}")

# Sandbox H_cache for this run
sandbox = r"{ROOT}/bench_pivot_tmp_{pivot_d}_{pivot_t}"
os.makedirs(sandbox + "/_h_cache", exist_ok=True)
os.makedirs(sandbox + "/_tmp", exist_ok=True)
os.environ["PREDICT_H_CACHE_DIR"] = sandbox + "/_h_cache"
os.environ["PREDICT_TMP_DIR"] = sandbox + "/_tmp"
os.environ["PREDICT_SN_DIR"] = r"{ROOT}/parallel_sn_topt"

import predict_2factor_topt as p2
from collections import Counter

# Force pivot
forced = ({pivot_d}, {pivot_t})
def forced_resolve(combo, mode):
    c_prime = list(combo)
    c_prime.remove(forced)
    c_prime = tuple(sorted(c_prime))
    return {{
        "left_combo": c_prime,
        "right_combo": None,
        "right_tg": forced,
        "m_left": sum(d for d, _ in c_prime),
        "m_right": forced[0],
        "burnside_m2": False,
    }}
p2.resolve_inputs = forced_resolve

# Parse combo
combo_tuples = []
for tok in "{COMBO}".strip("_").split("_"):
    parts = tok.strip("[]").split(",")
    combo_tuples.append((int(parts[0]), int(parts[1])))
combo = tuple(combo_tuples)
out_path = sandbox + "/result.g"

t0 = time.time()
result = p2.predict(combo, mode="distinguished",
                    output_path=out_path, emit_generators=True, force=True)
elapsed = time.time() - t0
print(f"PIVOT=({pivot_d},{pivot_t})  elapsed={{elapsed:.1f}}s  result={{result}}")
'''

print(f"=== Profiling combo {COMBO} with 3 pivot choices ===\n")

for pivot_d, pivot_t in PIVOTS:
    sb = ROOT / f"bench_pivot_tmp_{pivot_d}_{pivot_t}"
    if sb.exists():
        import shutil; shutil.rmtree(sb)
    script = ROOT / f"_pivot_runner_{pivot_d}_{pivot_t}.py"
    script.write_text(build_driver(pivot_d, pivot_t))
    print(f"--- pivot=({pivot_d},{pivot_t}) ---")
    t0 = time.time()
    proc = subprocess.run([sys.executable, str(script)],
                          capture_output=True, text=True, timeout=2*3600)
    elapsed = time.time() - t0
    print(f"  wall={elapsed:.1f}s")
    print(f"  stdout: {proc.stdout[-500:]}")
    if proc.stderr.strip():
        print(f"  stderr: {proc.stderr[-300:]}")
    script.unlink()
    print()
