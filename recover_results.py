#!/usr/bin/env python3
"""
recover_results.py — rebuild result.json files for predictions that GAP
already computed but Python failed to parse (due to a regex/line-wrap bug).

Walks predict_species_tmp/_batch/*/batch.log, extracts every RESULT line
with the corrected (whitespace-tolerant) regex, and writes/overwrites the
corresponding predict_species_tmp/18/<combo>/from_<dt>/result.json.

Idempotent.  Safe to re-run.  Doesn't touch GAP.
"""
import json
import re
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
TMP = ROOT / "predict_species_tmp"
BATCH = TMP / "_batch"
TARGET_N = 18

# Whitespace-tolerant version of the RESULT regex.
PAT = re.compile(
    r"RESULT\s+key=\s*(\S+)\s+predicted=\s*(\d+)\s+elapsed_ms=\s*(\d+)"
    r"\s+n_subs=\s*(\d+)(?:\s+cache_hit=\s*(\S+))?",
    re.MULTILINE,
)


def parse_key(key: str) -> tuple[list, list]:
    """key format: '<target_combo>__<dt>' where each is underscore-separated
    sequences of even-length pairs (d, t).  e.g.
        '4_1_4_1_4_1_6_2__6_2'  ->  target=[(4,1),(4,1),(4,1),(6,2)], dt=(6,2)
    """
    target_str, dt_str = key.split("__")
    target_parts = [int(x) for x in target_str.split("_")]
    dt_parts = [int(x) for x in dt_str.split("_")]
    target_combo = list(zip(target_parts[0::2], target_parts[1::2]))
    dt = tuple(dt_parts)
    return [list(p) for p in target_combo], list(dt)


def combo_filename(combo) -> str:
    return "_".join(f"[{d},{t}]" for (d, t) in sorted(combo))


def recover():
    n_logs = 0
    n_results = 0
    n_written = 0
    n_skipped = 0

    # Walk both old layout (_batch/dD_tT_mM/) and new layout (_batch/<ns>/dD_tT_mM/).
    for logfile in list(BATCH.glob("*/batch.log")) + list(BATCH.glob("*/*/batch.log")):
        n_logs += 1
        try:
            text = logfile.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # Determine (d, t, m) from path: dD_tT_mM
        m_match = re.match(r"d(\d+)_t(\d+)_m(\d+)", logfile.parent.name)
        if not m_match:
            continue
        d_dir = int(m_match.group(1))
        t_dir = int(m_match.group(2))
        m_dir = int(m_match.group(3))

        for m in PAT.finditer(text):
            key, pred, ms, nsubs, hit = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5)
            n_results += 1

            try:
                target_combo, dt = parse_key(key)
            except Exception:
                continue

            # Sanity: dt should match the batch dir's (d, t) pair.
            if (dt[0], dt[1]) != (d_dir, t_dir):
                continue

            target_str = combo_filename([tuple(p) for p in target_combo])
            dt_str = f"[{dt[0]},{dt[1]}]"
            work = TMP / str(TARGET_N) / target_str / f"from_{dt_str}"
            work.mkdir(parents=True, exist_ok=True)
            rj = work / "result.json"

            # Skip if already has a valid prediction.
            if rj.exists():
                try:
                    existing = json.loads(rj.read_text())
                    if existing.get("predicted") is not None:
                        n_skipped += 1
                        continue
                except Exception:
                    pass

            # Compute c' = target minus one block of dt.
            c_prime = [list(p) for p in target_combo]
            for i, p in enumerate(c_prime):
                if tuple(p) == tuple(dt):
                    c_prime.pop(i)
                    break
            src_n = TARGET_N - dt[0]
            partition = "[" + ",".join(str(p) for p in sorted([d for d, _ in target_combo], reverse=True)) + "]"
            src_partition = "[" + ",".join(str(p) for p in sorted([d for d, _ in c_prime], reverse=True)) + "]"
            src_combo_name = combo_filename([tuple(p) for p in c_prime])
            src_file = ROOT / "parallel_sn" / str(src_n) / src_partition / (src_combo_name + ".g")

            res = {
                "target_n": TARGET_N,
                "target_combo": target_combo,
                "dt": list(dt),
                "src_n": src_n,
                "src_combo": c_prime,
                "src_file": str(src_file),
                "subgroup_count": nsubs,
                "predicted": pred,
                "elapsed_s": ms / 1000.0,
                "cache_hit": (hit or "").lower() == "true",
            }
            rj.write_text(json.dumps(res, indent=2))
            n_written += 1

    print(f"Scanned {n_logs} batch logs, found {n_results} RESULT lines.")
    print(f"Wrote {n_written} result.json files (skipped {n_skipped} already complete).")


if __name__ == "__main__":
    recover()
