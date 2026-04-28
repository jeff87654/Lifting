"""predict_s19_43_4_combos.py — use the prototype tiered H-cache to
generate the two S19 [4,3]^4 LEFT combos:
  - [4,3]_[4,3]_[4,3]_[4,3]_[3,1] (RIGHT = C_3)
  - [4,3]_[4,3]_[4,3]_[4,3]_[3,2] (RIGHT = S_3)

Both go through predict_2factor.py distinguished mode.  The LEFT cache
covers Q in {C_2, C_3, S_3}, sufficient for both combos.
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")

# Set up isolated dirs so we don't clobber v2 caches/outputs
H_CACHE_DIR = ROOT / "predict_species_tmp" / "_h_cache_proto"
TMP_DIR = ROOT / "predict_species_tmp" / "_two_factor_proto"
OUT_DIR = ROOT / "parallel_sn_proto"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

# Place the prototype cache where predict_2factor.py expects it
proto_cache = ROOT / "prototype_h_cache_43_4_for_S3.g"
target_cache = H_CACHE_DIR / "16" / "[4,4,4,4]" / "[4,3]_[4,3]_[4,3]_[4,3].g"
target_cache.parent.mkdir(parents=True, exist_ok=True)
shutil.copy(proto_cache, target_cache)
print(f"Prototype cache placed at: {target_cache}")

env = os.environ.copy()
env["PREDICT_SN_DIR"] = str(ROOT / "parallel_sn_v2")          # LEFT source from v2
env["PREDICT_H_CACHE_DIR"] = str(H_CACHE_DIR)                 # use proto cache
env["PREDICT_TMP_DIR"] = str(TMP_DIR)

COMBOS = [
    "[3,1]_[4,3]_[4,3]_[4,3]_[4,3]",     # filename = ascending-degree
    "[3,2]_[4,3]_[4,3]_[4,3]_[4,3]",
]

for combo_name in COMBOS:
    output_path = OUT_DIR / "19" / "[4,4,4,4,3]" / f"{combo_name}.g"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(ROOT / "predict_2factor.py"),
        "--combo", combo_name,
        "--output-path", str(output_path),
        "--mode", "distinguished",
        "--force",
        "--timeout", "0",
    ]
    print(f"\n=== running combo {combo_name} ===")
    t0 = time.time()
    proc = subprocess.run(cmd, env=env)
    elapsed = time.time() - t0
    print(f"rc={proc.returncode}  elapsed={elapsed:.1f}s")
    if output_path.exists():
        text = output_path.read_text(encoding="utf-8")
        # Read deduped count
        for line in text.splitlines()[:6]:
            if line.startswith("# deduped:"):
                print(f"  -> {line}")
                break
    else:
        print(f"  -> no output file")
