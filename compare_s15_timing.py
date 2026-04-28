import os, glob
from pathlib import Path

def scan(root):
    out = {}
    for d in sorted(glob.glob(os.path.join(root, "[[]*[]]"))):
        summary = os.path.join(d, "summary.txt")
        if not os.path.exists(summary):
            continue
        with open(summary) as f:
            data = {}
            for line in f:
                if ":" in line:
                    k, _, v = line.partition(":")
                    data[k.strip()] = v.strip()
        part = Path(d).name
        out[part] = {
            "classes": int(data.get("total_classes", 0)),
            "elapsed": float(data.get("elapsed_seconds", 0)),
        }
    return out

v1 = scan(r"C:/Users/jeffr/Downloads/Lifting/parallel_s15_m6m7")
v2 = scan(r"C:/Users/jeffr/Downloads/Lifting/parallel_s15_m6m7_v2")

print(f"{'partition':<20} {'v1 cls':>8} {'v1 sec':>10} {'v2 cls':>8} {'v2 sec':>10} {'delta %':>8}")
print("-" * 70)
for part in sorted(set(v1) | set(v2)):
    a = v1.get(part, {"classes": 0, "elapsed": 0})
    b = v2.get(part, {"classes": 0, "elapsed": 0})
    delta_pct = ""
    if a["elapsed"] > 0 and b["elapsed"] > 0:
        pct = 100.0 * (b["elapsed"] - a["elapsed"]) / a["elapsed"]
        delta_pct = f"{pct:+.0f}"
    print(f"{part:<20} {a['classes']:>8} {a['elapsed']:>10.1f} {b['classes']:>8} {b['elapsed']:>10.1f} {delta_pct:>8}")

tot_v1 = sum(p["elapsed"] for p in v1.values())
tot_v2 = sum(p["elapsed"] for p in v2.values())
print("-" * 70)
print(f"{'TOTAL (CPU)':<20} {sum(p['classes'] for p in v1.values()):>8} {tot_v1:>10.1f} {sum(p['classes'] for p in v2.values()):>8} {tot_v2:>10.1f}")
