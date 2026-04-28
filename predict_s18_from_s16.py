#!/usr/bin/env python3
"""
predict_s18_from_s16.py

For each S16 partition lambda with verified data in parallel_sn/16/<lambda>/,
compute the predicted FPF count for the S18 partition lambda + [2] using
the LiftCountPlusC2 (Goursat) formula:

    predicted(lambda + [2]) = sum_{H in FPF list for lambda} (1 + |N_{S_16}(H) orbits on idx-2 normal subgroups of H|)

Walks each S16 combo file, parses out generator lists, builds a GAP driver
that reads them as Groups, runs LiftCountPlusC2 per subgroup, sums the result.

Output: per-partition predicted total, written to a JSON file and printed
in a comparison table against parallel_s18/manifest.json fpf_count.

Usage:
    python predict_s18_from_s16.py [--partition LAMBDA] [--all]

Examples:
    python predict_s18_from_s16.py --partition "[13,3]"
    python predict_s18_from_s16.py --all

Output dir: predict_s18_tmp/<lambda>/
    - subgroups.g           generated GAP file with FPF list
    - run.g                 GAP driver
    - run.log               LogTo output
    - result.json           {"partition": "...", "predicted": N, "subgroup_count": M}
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT      = Path(r"C:\Users\jeffr\Downloads\Lifting")
S16_DIR   = ROOT / "parallel_sn" / "16"
S18_DIR   = ROOT / "parallel_s18"
S18_MAN   = ROOT / "parallel_s18" / "manifest.json"
TMP_DIR   = ROOT / "predict_s18_tmp"
TMP_DIR.mkdir(exist_ok=True)

GAP_BASH  = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME  = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def parse_combo_file(path: Path) -> list[str]:
    """Return list of generator-list strings (each a valid GAP list literal)."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    # Strip line continuations: "\<newline>" -> ""
    text = text.replace("\\\n", "").replace("\\\r\n", "")
    # Remove comment lines
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    text = "\n".join(lines)
    # Walk balanced brackets at top level
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c != "[":
            i += 1
            continue
        depth = 0
        j = i
        while j < n:
            ch = text[j]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if j >= n:
            break
        out.append(text[i:j+1])
        i = j + 1
    return out


def collect_subgroups(partition_dir: Path) -> tuple[int, list[str]]:
    """Return (file_count, list of GAP generator-list strings) for one partition folder."""
    files = sorted(p for p in partition_dir.iterdir()
                   if p.is_file() and p.suffix == ".g" and not p.name.startswith("summary"))
    all_subs = []
    for f in files:
        all_subs.extend(parse_combo_file(f))
    return len(files), all_subs


def write_subgroups_g(out_path: Path, subs: list[str]) -> None:
    """Write a GAP file: SUBGROUPS := [ Group(...), Group(...), ... ];"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Auto-generated FPF subgroup list (S_16 conjugacy class reps)\n")
        f.write("SUBGROUPS := [\n")
        for i, s in enumerate(subs):
            sep = "," if i < len(subs) - 1 else ""
            f.write(f"  Group({s}){sep}\n")
        f.write("];\n")


DRIVER_GAP = r"""
LogTo("__LOG__");
Print("Loading subgroups...\n");
Read("__SUBS__");
Print("Loaded ", Length(SUBGROUPS), " subgroups.\n");

S16 := SymmetricGroup(16);
TOTAL := 0;
t0 := Runtime();

# Resume support: read prior PARTIAL_TOTAL from checkpoint file if present
START := 1;
if IsExistingFile("__CKPT__") then
    Read("__CKPT__");  # sets START and TOTAL via assignments in the file
    Print("Resuming at i=", START, " with TOTAL=", TOTAL, "\n");
fi;

LiftCountForH := function(H, S)
    local nrm, maxes, idx2, orbs;
    nrm := Normalizer(S, H);
    maxes := MaximalSubgroupClassReps(H);
    idx2 := Filtered(maxes, K -> Index(H, K) = 2);
    if Length(idx2) = 0 then
        return 1;
    fi;
    orbs := Orbits(nrm, idx2, function(K, g) return K^g; end);
    return 1 + Length(orbs);
end;

for i in [START..Length(SUBGROUPS)] do
    H := SUBGROUPS[i];
    contrib := LiftCountForH(H, S16);
    TOTAL := TOTAL + contrib;
    if i mod 50 = 0 or i = Length(SUBGROUPS) then
        Print("  [", i, "/", Length(SUBGROUPS), "]  total=", TOTAL,
              "  elapsed=", Int((Runtime()-t0)/1000), "s\n");
        # Atomic-ish checkpoint: write to .tmp, then rename via PrintTo overwrite
        PrintTo("__CKPT__",
                "START := ", i + 1, ";\n",
                "TOTAL := ", TOTAL, ";\n");
    fi;
od;

Print("\nPREDICTED_TOTAL: ", TOTAL, "\n");
Print("SUBGROUP_COUNT: ", Length(SUBGROUPS), "\n");
LogTo();
QUIT;
"""


def run_gap(work_dir: Path, log_path: Path, timeout: int | None = None) -> str:
    cyg_dir = to_cyg(work_dir / "run.g")
    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{cyg_dir}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    log = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
    return log + "\n--- STDERR ---\n" + (proc.stderr or "")


def predict_partition(part_name: str, timeout: int | None = None) -> dict:
    """Run prediction for a single S16 partition, return result dict."""
    src = S16_DIR / part_name
    if not src.is_dir():
        raise FileNotFoundError(src)
    work = TMP_DIR / part_name
    work.mkdir(parents=True, exist_ok=True)

    print(f"\n=== {part_name} ===")
    n_files, subs = collect_subgroups(src)
    print(f"  files: {n_files}, subgroups: {len(subs)}")

    subs_g = work / "subgroups.g"
    write_subgroups_g(subs_g, subs)

    log_path = work / "run.log"
    ckpt_path = work / "checkpoint.g"
    if log_path.exists():
        log_path.unlink()
    run_g = work / "run.g"
    driver = (DRIVER_GAP
              .replace("__LOG__", to_cyg(log_path))
              .replace("__CKPT__", to_cyg(ckpt_path))
              .replace("__SUBS__", to_cyg(subs_g)))
    run_g.write_text(driver, encoding="utf-8")

    t0 = time.time()
    log = run_gap(work, log_path, timeout=timeout)
    elapsed = time.time() - t0

    m_pred = re.search(r"PREDICTED_TOTAL:\s*(\d+)", log)
    m_cnt  = re.search(r"SUBGROUP_COUNT:\s*(\d+)", log)
    predicted = int(m_pred.group(1)) if m_pred else None
    sub_count = int(m_cnt.group(1)) if m_cnt else None
    if predicted is None:
        print(f"  !! GAP did not return a result. Tail of log:")
        for ln in log.splitlines()[-15:]:
            print(f"    {ln}")

    result = {
        "partition": part_name,
        "subgroup_count": sub_count if sub_count is not None else len(subs),
        "predicted": predicted,
        "elapsed_s": round(elapsed, 1),
    }
    (work / "result.json").write_text(json.dumps(result, indent=2))
    print(f"  predicted [..,2] count: {predicted}  ({elapsed:.1f}s)")
    return result


def s18_partition_name(s16_part_name: str) -> str:
    """[13,3] -> [13,3,2] (sorted desc)"""
    inner = s16_part_name.strip("[]")
    parts = [int(x) for x in inner.split(",")]
    parts.append(2)
    parts.sort(reverse=True)
    return "[" + ",".join(str(p) for p in parts) + "]"


def is_rigid(s16_part_name: str) -> bool:
    """A partition lambda is 'rigid' for the +[2] extension iff lambda has no 2-part.
    In that case, the new 2-block is uniquely identifiable in lambda+[2], and the
    Goursat lift formula gives an exact count. Otherwise it gives an upper bound."""
    inner = s16_part_name.strip("[]")
    parts = [int(x) for x in inner.split(",")]
    return 2 not in parts


_DEDUPED_RE = re.compile(r"^#\s*deduped:\s*(\d+)", re.MULTILINE)


def s18_actual_count(s18_part_name: str) -> tuple[int | None, int]:
    """Sum 'deduped:' counts across S18 combo files for a partition.
    Returns (total, num_combo_files). Returns (None, 0) if folder missing."""
    folder = S18_DIR / s18_part_name
    if not folder.is_dir():
        return None, 0
    total = 0
    n_files = 0
    for f in folder.iterdir():
        if not (f.is_file() and f.suffix == ".g"):
            continue
        if f.name.startswith("summary"):
            continue
        if "backup" in f.name.lower():
            continue
        try:
            head = f.read_text(encoding="utf-8", errors="ignore")[:512]
        except Exception:
            continue
        m = _DEDUPED_RE.search(head)
        if m:
            total += int(m.group(1))
            n_files += 1
    return total, n_files


def s18_summary_count(s18_part_name: str) -> int | None:
    """Read total_classes from S18 partition's summary.txt if present."""
    summ = S18_DIR / s18_part_name / "summary.txt"
    if not summ.exists():
        return None
    txt = summ.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"total_classes:\s*(\d+)", txt)
    return int(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--partition", help='S16 partition like "[13,3]"')
    ap.add_argument("--all", action="store_true", help="Run all S16 partitions")
    ap.add_argument("--rigid-only", action="store_true",
                    help="Only run S16 partitions with no 2-part (formula is exact)")
    ap.add_argument("--timeout", type=int, default=None,
                    help="Per-partition GAP timeout in seconds")
    ap.add_argument("--skip-large", type=int, default=None,
                    help="Skip partitions with > N subgroups")
    ap.add_argument("--force", action="store_true",
                    help="Re-run even if result.json already exists")
    args = ap.parse_args()

    if not args.partition and not args.all and not args.rigid_only:
        ap.error("specify --partition, --all, or --rigid-only")

    if args.partition:
        partitions = [args.partition]
    elif args.rigid_only:
        partitions = sorted(p.name for p in S16_DIR.iterdir() if p.is_dir() and is_rigid(p.name))
    else:
        partitions = sorted(p.name for p in S16_DIR.iterdir() if p.is_dir())

    results = []
    for p in partitions:
        # Skip partitions that already have result.json (unless --force)
        existing = TMP_DIR / p / "result.json"
        if existing.exists() and not args.force:
            try:
                r = json.loads(existing.read_text())
                if r.get("predicted") is not None:
                    print(f"{p}: skip (existing result.json with predicted={r['predicted']})")
                    s18_name = s18_partition_name(p)
                    r["partition"] = p
                    r["s18_partition"] = s18_name
                    r["rigid"] = is_rigid(p)
                    actual_files, n_combo_files = s18_actual_count(s18_name)
                    r["actual_files_sum"] = actual_files
                    r["actual_summary"] = s18_summary_count(s18_name)
                    r["n_combo_files"] = n_combo_files
                    actual = r["actual_summary"] if r["actual_summary"] is not None else actual_files
                    r["actual"] = actual
                    r["delta"] = (r["predicted"] - actual) if (r["predicted"] is not None and actual is not None) else None
                    results.append(r)
                    continue
            except Exception:
                pass
        try:
            n_files, subs = collect_subgroups(S16_DIR / p)
        except Exception as e:
            print(f"{p}: skip ({e})")
            continue
        if args.skip_large is not None and len(subs) > args.skip_large:
            print(f"{p}: skipping ({len(subs)} subgroups > {args.skip_large})")
            continue
        try:
            r = predict_partition(p, timeout=args.timeout)
            s18_name = s18_partition_name(p)
            r["s18_partition"] = s18_name
            r["rigid"] = is_rigid(p)
            actual_files, n_combo_files = s18_actual_count(s18_name)
            r["actual_files_sum"] = actual_files
            r["actual_summary"] = s18_summary_count(s18_name)
            r["n_combo_files"] = n_combo_files
            # Prefer summary.txt total; fall back to file sum
            actual = r["actual_summary"] if r["actual_summary"] is not None else actual_files
            r["actual"] = actual
            r["delta"] = (r["predicted"] - actual) if (r["predicted"] is not None and actual is not None) else None
            results.append(r)
        except subprocess.TimeoutExpired:
            print(f"{p}: TIMEOUT")
        except Exception as e:
            print(f"{p}: ERROR {e}")

    out_json = TMP_DIR / "summary.json"
    out_json.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_json}")

    print("\n=== Comparison ===")
    print("(rigid = lambda has no 2-part; formula gives EXACT count.")
    print(" non-rigid: lambda has a 2-part already; formula is upper bound only.)")
    hdr = f"{'rig':<3} {'S16 partition':<22} {'S18 partition':<22} {'subs':>6} {'predicted':>10} {'actual_sum':>11} {'actual_summary':>14} {'delta':>8}"
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        pred = r["predicted"]
        a_sum = r["actual_files_sum"]
        a_summ = r["actual_summary"]
        delta = r["delta"]
        rig = "Y" if r.get("rigid") else "N"
        flag = ""
        if r.get("rigid") and delta is not None and delta != 0:
            flag = "  <-- MISSING (rigid)"
        elif not r.get("rigid") and delta is not None and delta != 0:
            flag = "  (upper bound, expected delta>=0)"
        print(f"{rig:<3} {r['partition']:<22} {r['s18_partition']:<22} {r['subgroup_count']:>6} "
              f"{pred if pred is not None else 'N/A':>10} "
              f"{a_sum if a_sum is not None else 'N/A':>11} "
              f"{a_summ if a_summ is not None else 'N/A':>14} "
              f"{delta if delta is not None else '':>8}{flag}")


if __name__ == "__main__":
    main()
