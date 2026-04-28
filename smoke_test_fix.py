"""smoke_test_fix.py — verify the _EnumerateNormalsForQGroups fix produces
the same dedup count as the reference for known-good combos.

Reference (from parallel_sn_topt/10/[3,3,2,2]/):
    [2,1]_[2,1]_[3,2]_[3,2]  -> 20 deduped
    [2,1]_[2,1]_[3,1]_[3,2]  -> ?
"""
import os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).parent
SANDBOX = ROOT / "smoke_test_fix_tmp"
if SANDBOX.exists():
    import shutil; shutil.rmtree(SANDBOX)
SANDBOX.mkdir()
(SANDBOX / "_h_cache").mkdir()
(SANDBOX / "_tmp").mkdir()

env = os.environ.copy()
env["PREDICT_H_CACHE_DIR"] = str(SANDBOX / "_h_cache")
env["PREDICT_TMP_DIR"] = str(SANDBOX / "_tmp")
env["PREDICT_SN_DIR"] = str(ROOT / "parallel_sn_topt")

CASES = [
    ("[2,1]_[2,1]_[3,2]_[3,2]", 20),
    ("[2,1]_[2,1]_[3,1]_[3,2]", None),
]

for combo, expected in CASES:
    out = SANDBOX / f"{combo}.g"
    print(f"\n=== {combo} ===")
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, str(ROOT / "predict_2factor_topt.py"),
         "--combo", combo, "--mode", "auto",
         "--output-path", str(out),
         "--emit-generators", "--force"],
        env=env, capture_output=True, text=True, timeout=600)
    elapsed = time.time() - t0
    if not out.exists():
        print(f"FAIL ({elapsed:.1f}s): no output written")
        print("stdout:", proc.stdout[-1000:])
        print("stderr:", proc.stderr[-500:])
        continue
    text = out.read_text()
    m = re.search(r"# deduped:\s*(\d+)", text)
    n = int(m.group(1)) if m else -1
    ok = (expected is None) or (n == expected)
    tag = "OK" if ok else "MISMATCH"
    print(f"{tag} ({elapsed:.1f}s): deduped={n}  expected={expected}")
