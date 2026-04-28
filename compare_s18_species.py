#!/usr/bin/env python3
"""
compare_s18_species.py — Per-combo S18 prediction-vs-actual report.

Consumes predict_species_tmp/18/<combo>/from_<dt>/result.json files (produced by
predict_s18_species.py --target 18) and the in-progress S18 combo files at
parallel_s18/<part>/<combo>.g.

For each S18 combo, classifies as:
  EXACT_MATCH         distinguished, prediction == actual
  OVER                distinguished, prediction < actual  -> probable dedup bug
  MISSING             distinguished, prediction > actual  -> probable enumeration bug
  INCONSISTENT_SOURCES  multiple distinguished decompositions disagree
  NON_PREDICTABLE     no distinguished species (all repeat) -> manual audit
  NO_PREDICTION       distinguished but no source data / GAP error

Output: a sorted bug-localization table on stdout, plus a JSON report at
predict_species_tmp/18/_compare_report.json.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
S18_DIR = ROOT / "parallel_s18"
TMP_DIR = ROOT / "predict_species_tmp" / "18"

_DEDUPED_RE = re.compile(r"^#\s*deduped:\s*(\d+)", re.MULTILINE)
_COMBO_HEADER_RE = re.compile(r"^#\s*combo:\s*(\[.*\])", re.MULTILINE)
_COMBO_FILENAME_RE = re.compile(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]")


def parse_combo_str(s: str) -> tuple[tuple[int, int], ...]:
    pairs = _COMBO_FILENAME_RE.findall(s)
    return tuple(sorted((int(d), int(t)) for d, t in pairs))


def combo_filename(combo) -> str:
    return "_".join(f"[{d},{t}]" for d, t in sorted(combo))


def combo_partition(combo) -> str:
    parts = sorted((d for d, _ in combo), reverse=True)
    return "[" + ",".join(str(p) for p in parts) + "]"


def is_distinguished(combo, dt) -> bool:
    return Counter(combo)[dt] == 1


def read_actual(combo_file: Path) -> int | None:
    try:
        head = combo_file.read_text(encoding="utf-8", errors="ignore")[:1024]
    except Exception:
        return None
    m = _DEDUPED_RE.search(head)
    return int(m.group(1)) if m else None


def collect_predictions(combo) -> tuple[dict[str, int], dict[str, str]]:
    """Read predict_species_tmp/18/<combo>/from_<dt>/result.json for every
    available distinguished decomposition. Returns (predictions, errors)."""
    work = TMP_DIR / combo_filename(combo)
    preds, errors = {}, {}
    if not work.is_dir():
        return preds, errors
    for sub in work.iterdir():
        if not sub.is_dir() or not sub.name.startswith("from_"):
            continue
        rj = sub / "result.json"
        if not rj.exists():
            continue
        try:
            r = json.loads(rj.read_text())
        except Exception:
            continue
        dt_label = sub.name[len("from_"):]
        if r.get("predicted") is not None:
            preds[dt_label] = r["predicted"]
        elif r.get("error"):
            errors[dt_label] = r["error"]
    return preds, errors


def classify(combo, preds, errors, actual) -> str:
    if len(combo) == 1:
        # Single-block combo: count = 1 by definition (one S_d-conjugacy class
        # of TransitiveGroup(d, t) viewed as subgroup of S_d).
        if actual is None:
            return "PREDICTED_NO_ACTUAL"
        if actual == 1:
            return "EXACT_MATCH"
        return "OVER" if actual > 1 else "MISSING"
    species = list(set(combo))
    distinguished = any(is_distinguished(combo, s) for s in species)
    if not distinguished:
        return "NON_PREDICTABLE"
    if not preds:
        return "NO_PREDICTION"
    vals = list(preds.values())
    if len(set(vals)) > 1:
        return "INCONSISTENT_SOURCES"
    pred = vals[0]
    if actual is None:
        return "PREDICTED_NO_ACTUAL"
    if pred == actual:
        return "EXACT_MATCH"
    if pred > actual:
        return "MISSING"
    return "OVER"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="Show at most N rows per category in the table.")
    ap.add_argument("--all", action="store_true",
                    help="Show all rows including EXACT_MATCH (verbose).")
    args = ap.parse_args()

    if not S18_DIR.is_dir():
        print(f"missing: {S18_DIR}")
        sys.exit(1)

    rows = []
    by_partition = defaultdict(lambda: defaultdict(int))   # part -> status -> count
    part_actual = defaultdict(int)                          # part -> sum of actuals
    part_predicted = defaultdict(int)                       # part -> sum of predictions
    part_n_combos = defaultdict(int)

    for part_dir in sorted(S18_DIR.iterdir()):
        if not part_dir.is_dir():
            continue
        if "backup" in part_dir.name.lower() or part_dir.name.startswith("_"):
            continue
        for f in sorted(part_dir.iterdir()):
            if not (f.is_file() and f.suffix == ".g"):
                continue
            if f.name.startswith("summary") or "backup" in f.name.lower():
                continue
            combo = parse_combo_str(f.stem)
            if not combo:
                continue
            actual = read_actual(f)
            preds, errors = collect_predictions(combo)
            status = classify(combo, preds, errors, actual)
            if len(combo) == 1:
                consensus = 1
            else:
                consensus = list(preds.values())[0] if preds and len(set(preds.values())) == 1 else None
            row = {
                "partition": combo_partition(combo),
                "combo": combo_filename(combo),
                "status": status,
                "actual": actual,
                "predicted": consensus,
                "predictions": preds,
                "errors": errors,
                "delta": (consensus - actual) if (consensus is not None and actual is not None) else None,
            }
            rows.append(row)
            part = combo_partition(combo)
            by_partition[part][status] += 1
            part_n_combos[part] += 1
            if actual is not None:
                part_actual[part] += actual
            if consensus is not None:
                part_predicted[part] += consensus

    # --- Per-partition summary ---
    print("=" * 110)
    print("Per-partition summary (S18)")
    print("=" * 110)
    hdr = f"{'partition':<22} {'#combos':>8} {'pred_sum':>10} {'actual_sum':>11} {'delta':>8}  status_counts"
    print(hdr)
    print("-" * len(hdr))
    for part in sorted(by_partition.keys()):
        sc = by_partition[part]
        sc_str = " ".join(f"{k}={v}" for k, v in sorted(sc.items()))
        pa = part_actual[part]
        pp = part_predicted[part]
        delta = pp - pa
        print(f"{part:<22} {part_n_combos[part]:>8} {pp:>10} {pa:>11} {delta:>+8}  {sc_str}")

    # --- Per-combo bug rows ---
    BUG_ORDER = ["OVER", "MISSING", "INCONSISTENT_SOURCES", "NO_PREDICTION", "NON_PREDICTABLE"]
    print()
    print("=" * 110)
    print("Per-combo discrepancies (sorted by status: bug-likely first)")
    print("=" * 110)
    print(f"{'partition':<18} {'combo':<42} {'status':<22} {'actual':>7} {'pred':>7} {'delta':>7}")
    print("-" * 110)
    bug_rows = [r for r in rows if r["status"] in BUG_ORDER]
    bug_rows.sort(key=lambda r: (BUG_ORDER.index(r["status"]), r["partition"], r["combo"]))
    if args.limit:
        kept = []
        per_status = defaultdict(int)
        for r in bug_rows:
            if per_status[r["status"]] >= args.limit:
                continue
            kept.append(r)
            per_status[r["status"]] += 1
        bug_rows = kept
    for r in bug_rows:
        delta_str = f"{r['delta']:+d}" if r["delta"] is not None else ""
        actual_str = str(r["actual"]) if r["actual"] is not None else "--"
        pred_str = str(r["predicted"]) if r["predicted"] is not None else "--"
        if r["status"] == "INCONSISTENT_SOURCES":
            pred_str = ",".join(f"{k}={v}" for k, v in r["predictions"].items())
        print(f"{r['partition']:<18} {r['combo']:<42} {r['status']:<22} {actual_str:>7} {pred_str:>7} {delta_str:>7}")

    if args.all:
        print()
        print("=" * 110)
        print("All combos (full)")
        print("=" * 110)
        rows.sort(key=lambda r: (r["partition"], r["combo"]))
        for r in rows:
            delta_str = f"{r['delta']:+d}" if r["delta"] is not None else ""
            actual_str = str(r["actual"]) if r["actual"] is not None else "--"
            pred_str = str(r["predicted"]) if r["predicted"] is not None else "--"
            print(f"{r['partition']:<18} {r['combo']:<42} {r['status']:<22} {actual_str:>7} {pred_str:>7} {delta_str:>7}")

    # --- Overall counts ---
    print()
    print("=" * 110)
    overall = Counter(r["status"] for r in rows)
    print("Overall:", dict(overall))

    out = TMP_DIR / "_compare_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "n_combos": len(rows),
        "by_status": dict(overall),
        "by_partition": {p: dict(sc) for p, sc in by_partition.items()},
        "rows": rows,
    }, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
