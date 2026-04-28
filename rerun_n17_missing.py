"""Re-run the 89 n=17 combos that were lost when super_1 crashed.

Spreads work across 4 worker processes, each invoking
predict_2factor_topt.py --combo X --mode auto --output-path Y --emit-generators.
"""
import json
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).parent
JOBS = json.loads((ROOT / "rerun_n17_missing.json").read_text())
LOG = ROOT / "rerun_n17_missing.log"
PREDICTOR = ROOT / "predict_2factor_topt.py"

def run_one(job):
    combo = job["combo"]
    out = ROOT / job["output"]
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(PREDICTOR),
             "--combo", combo,
             "--mode", "auto",
             "--output-path", str(out),
             "--emit-generators",
             "--force"],
            capture_output=True, text=True, timeout=3600)
        elapsed = time.time() - t0
        ok = out.exists()
        return {"combo": combo, "ok": ok, "elapsed_s": elapsed,
                "rc": proc.returncode,
                "stderr_tail": proc.stderr[-600:] if proc.stderr else "",
                "stdout_tail": proc.stdout[-600:] if proc.stdout else ""}
    except subprocess.TimeoutExpired:
        return {"combo": combo, "ok": False, "elapsed_s": time.time()-t0,
                "rc": -1, "stderr_tail": "TIMEOUT", "stdout_tail": ""}

def main():
    if LOG.exists(): LOG.unlink()
    print(f"Re-running {len(JOBS)} missing combos with 4 workers...")
    t0 = time.time()
    done = 0
    with ProcessPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(run_one, j): j for j in JOBS}
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            line = (f"[{done}/{len(JOBS)}] {'OK ' if r['ok'] else 'FAIL'} "
                    f"{r['elapsed_s']:.1f}s  {r['combo']}")
            print(line)
            with LOG.open("a") as f:
                f.write(line + "\n")
                if not r["ok"]:
                    f.write(f"  rc={r['rc']}\n  stderr: {r['stderr_tail']}\n  stdout: {r['stdout_tail']}\n")
    print(f"\nTotal: {time.time()-t0:.1f}s")

if __name__ == "__main__":
    main()
