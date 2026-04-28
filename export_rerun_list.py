#!/usr/bin/env python3
"""
export_rerun_list.py — Dump MISSING + OVER combos from the S18 compare report
to a text file for targeted reruns of parallel_s18.

Output columns: partition  combo  stored  predicted  delta  status
Sorted by abs(delta) descending so the biggest discrepancies come first.
"""
import json
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
REPORT = ROOT / "predict_species_tmp" / "18" / "_compare_report.json"
OUTPUT = ROOT / "s18_rerun_list.txt"

data = json.load(open(REPORT))
discrepancies = [r for r in data["rows"] if r["status"] in ("MISSING", "OVER")]
discrepancies.sort(key=lambda r: (-abs(r["delta"]), r["partition"], r["combo"]))

with open(OUTPUT, "w") as f:
    f.write(f"# S18 rerun list: combos where prediction disagrees with stored count\n")
    f.write(f"# MISSING = predicted > stored (S18 over-deduped, missing classes to recover)\n")
    f.write(f"# OVER    = predicted < stored (S18 missed-class dedup bug, extras to remove)\n")
    f.write(f"# Total: {len(discrepancies)} combos "
            f"({sum(1 for r in discrepancies if r['status'] == 'MISSING')} MISSING + "
            f"{sum(1 for r in discrepancies if r['status'] == 'OVER')} OVER)\n")
    f.write(f"# Net delta: "
            f"+{sum(r['delta'] for r in discrepancies if r['status']=='MISSING')} missing, "
            f"{sum(r['delta'] for r in discrepancies if r['status']=='OVER')} over\n")
    f.write(f"#\n")
    f.write(f"# {'partition':15s} {'combo':55s} {'stored':>8s} {'predicted':>10s} "
            f"{'delta':>7s} {'status':>8s}\n")
    for r in discrepancies:
        f.write(f"  {r['partition']:15s} {r['combo']:55s} {r['actual']:>8d} "
                f"{r['predicted']:>10d} {r['delta']:>+7d} {r['status']:>8s}\n")

print(f"Wrote {len(discrepancies)} discrepancies to {OUTPUT}")
n_miss = sum(1 for r in discrepancies if r["status"] == "MISSING")
n_over = sum(1 for r in discrepancies if r["status"] == "OVER")
print(f"  MISSING: {n_miss} combos, total +{sum(r['delta'] for r in discrepancies if r['status']=='MISSING')} classes")
print(f"  OVER:    {n_over} combos, total {sum(r['delta'] for r in discrepancies if r['status']=='OVER')} classes")
