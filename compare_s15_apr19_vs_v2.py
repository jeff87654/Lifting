"""Compare April 19 S_15 timing (from parallel_sn/15/ per-combo elapsed_ms)
against current v2 timing (parallel_s15_m6m7_v2/ summary.txt)."""
import os, re, glob
from pathlib import Path

APR19 = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_sn/15")
V2 = Path(r"C:/Users/jeffr/Downloads/Lifting/parallel_s15_m6m7_v2")

# April 19: sum elapsed_ms across .g files in each partition dir.
apr19 = {}
for part_dir in sorted(APR19.glob("[[]*[]]")):
    total_ms = 0
    total_cls = 0
    for g in part_dir.glob("*.g"):
        with open(g) as f:
            text = f.read()
        m = re.search(r"# elapsed_ms:\s*(\d+)", text)
        if m:
            total_ms += int(m.group(1))
        d = re.search(r"# deduped:\s*(\d+)", text)
        if d:
            total_cls += int(d.group(1))
    apr19[part_dir.name] = {"elapsed": total_ms / 1000.0, "classes": total_cls}

# v2: read summary.txt per partition
v2 = {}
for part_dir in sorted(V2.glob("[[]*[]]")):
    summary = part_dir / "summary.txt"
    if not summary.exists():
        continue
    data = {}
    with open(summary) as f:
        for line in f:
            if ":" in line:
                k, _, v = line.partition(":")
                data[k.strip()] = v.strip()
    v2[part_dir.name] = {
        "classes": int(data.get("total_classes", 0)),
        "elapsed": float(data.get("elapsed_seconds", 0)),
    }

print(f"{'partition':<20} {'apr19 cls':>10} {'apr19 sec':>10} {'v2 cls':>8} {'v2 sec':>10} {'v2/apr19':>9}")
print("-" * 75)

total_a = 0
total_v = 0
for part in sorted(set(apr19) | set(v2)):
    a = apr19.get(part, {"classes": 0, "elapsed": 0})
    b = v2.get(part, {"classes": 0, "elapsed": 0})
    ratio = ""
    if a["elapsed"] > 0 and b["elapsed"] > 0:
        ratio = f"{b['elapsed']/a['elapsed']:.2f}x"
    print(f"{part:<20} {a['classes']:>10} {a['elapsed']:>10.1f} {b['classes']:>8} {b['elapsed']:>10.1f} {ratio:>9}")
    total_a += a["elapsed"]
    total_v += b["elapsed"]

print("-" * 75)
print(f"{'TOTAL CPU seconds':<20} {sum(p['classes'] for p in apr19.values()):>10} {total_a:>10.1f} {sum(p['classes'] for p in v2.values()):>8} {total_v:>10.1f} "
      + (f"{total_v/total_a:.2f}x" if total_a > 0 else ""))
