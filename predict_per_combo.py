#!/usr/bin/env python3
"""
predict_per_combo.py — Per-combo prediction for one S16 partition.
For each combo file in parallel_sn/16/<lambda>/, parse subgroups and call
LiftCountPlusC2 on each, summing per file. Then compare to the corresponding
S18 [2,1]_<combo>.g dedup count.

Usage:
    python predict_per_combo.py "[8,4,4]"

Output:
    predict_s18_tmp/<lambda>_per_combo/
        per_combo.csv       combo, n_subs, predicted, actual, delta
        per_combo.log       full GAP run log
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

ROOT     = Path(r"C:\Users\jeffr\Downloads\Lifting")
S16_DIR  = ROOT / "parallel_sn" / "16"
S18_DIR  = ROOT / "parallel_s18"
TMP_DIR  = ROOT / "predict_s18_tmp"

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"


def to_cyg(p):
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def parse_combo_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = text.replace("\\\n", "").replace("\\\r\n", "")
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    text = "\n".join(lines)
    out = []
    i, n = 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1; continue
        if text[i] != "[":
            i += 1; continue
        depth = 0; j = i
        while j < n:
            if text[j] == "[": depth += 1
            elif text[j] == "]":
                depth -= 1
                if depth == 0: break
            j += 1
        if j >= n: break
        out.append(text[i:j+1])
        i = j + 1
    return out


def s18_combo_name(s16_combo: str) -> str:
    """[4,1]_[4,1]_[8,1].g  ->  [2,1]_[4,1]_[4,1]_[8,1].g (sorted ascending by first key)."""
    # Just prepend [2,1]_; the existing S18 layout uses that convention.
    return "[2,1]_" + s16_combo


_DEDUPED_RE = re.compile(r"^#\s*deduped:\s*(\d+)", re.MULTILINE)


def actual_combo_count(s18_part: str, s18_combo: str) -> int | None:
    p = S18_DIR / s18_part / s18_combo
    if not p.exists():
        # check backup names
        for f in (S18_DIR / s18_part).iterdir():
            if f.name.startswith(s18_combo) and "backup" not in f.name.lower():
                p = f; break
        else:
            return None
    head = p.read_text(encoding="utf-8", errors="ignore")[:512]
    m = _DEDUPED_RE.search(head)
    return int(m.group(1)) if m else None


def s18_partition_name(s16_part: str) -> str:
    parts = sorted([int(x) for x in s16_part.strip("[]").split(",")] + [2], reverse=True)
    return "[" + ",".join(str(p) for p in parts) + "]"


DRIVER_GAP = r"""
LogTo("__LOG__");
Read("__SUBS__");
S16 := SymmetricGroup(16);
SWAP := (17,18);

# Output a permutation list as "[g1,g2,...]" via GAP's String()
EmitGens := function(file, gens)
    local i;
    AppendTo(file, "[");
    for i in [1..Length(gens)] do
        if i > 1 then AppendTo(file, ","); fi;
        AppendTo(file, gens[i]);
    od;
    AppendTo(file, "]\n");
end;

LiftsForH := function(H)
    # Return list of generator-lists for each lift of H to S_18 [..,2].
    local nrm, maxes, idx2, orbs, lifts, base, K, gens, h;
    base := GeneratorsOfGroup(H);
    lifts := [];
    # H x C_2
    Add(lifts, Concatenation(base, [SWAP]));
    nrm := Normalizer(S16, H);
    maxes := MaximalSubgroupClassReps(H);
    idx2 := Filtered(maxes, K -> Index(H, K) = 2);
    if Length(idx2) = 0 then
        return lifts;
    fi;
    orbs := Orbits(nrm, idx2, function(K, g) return K^g; end);
    for K in List(orbs, Representative) do
        gens := List(base, function(h) if h in K then return h; else return h * SWAP; fi; end);
        Add(lifts, gens);
    od;
    return lifts;
end;

# Open output files
PrintTo("__GENS_DIR__/_INDEX.g", "# combo, n_subs, predicted, gen_file\n");

COMBO_TOTALS := [];
for i in [1..Length(COMBO_FILES)] do
    cname := COMBO_FILES[i];
    subs := COMBO_SUBGROUPS[i];
    total := 0;
    # Output file path: __GENS_DIR__/<cname stripped of .g>.lifts.g
    out_path := Concatenation("__GENS_DIR__/", cname);
    # Header (so file is self-describing)
    PrintTo(out_path, "# Lifts predicted by Goursat formula for combo ", cname, "\n");
    AppendTo(out_path, "# (Note: counts include H x C_2 + graph_K per N-orbit on index-2 subs of H)\n");
    AppendTo(out_path, "# Format: one [gen1,gen2,...] list per lift subgroup\n");
    for H in subs do
        liftlist := LiftsForH(H);
        for g in liftlist do
            EmitGens(out_path, g);
        od;
        total := total + Length(liftlist);
    od;
    Add(COMBO_TOTALS, [cname, Length(subs), total]);
    Print("[", i, "/", Length(COMBO_FILES), "]  ", cname,
          "  n_subs=", Length(subs), "  predicted=", total, "\n");
    AppendTo("__GENS_DIR__/_INDEX.g",
             cname, ", ", Length(subs), ", ", total, ", ", cname, "\n");
od;
PrintTo("__OUT__", "PER_COMBO := [\n");
for r in COMBO_TOTALS do
    AppendTo("__OUT__", "  [\"", r[1], "\", ", r[2], ", ", r[3], "],\n");
od;
AppendTo("__OUT__", "];\n");
LogTo();
QUIT;
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("partition", help='S16 partition like "[8,4,4]"')
    args = ap.parse_args()
    s16_part = args.partition
    src = S16_DIR / s16_part
    if not src.is_dir():
        sys.exit(f"missing {src}")

    work = TMP_DIR / (s16_part + "_per_combo")
    work.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in src.iterdir()
                   if p.is_file() and p.suffix == ".g" and not p.name.startswith("summary"))
    print(f"{s16_part}: {len(files)} combo files")

    # Build a single GAP file containing parallel arrays
    subs_g = work / "subgroups.g"
    with open(subs_g, "w", encoding="utf-8") as f:
        f.write("# Auto-generated per-combo subgroup arrays\n")
        f.write("COMBO_FILES := [\n")
        for cf in files:
            f.write(f'  "{cf.name}",\n')
        f.write("];\n")
        f.write("COMBO_SUBGROUPS := [\n")
        for cf in files:
            subs = parse_combo_file(cf)
            f.write("  [\n")
            for s in subs:
                f.write(f"    Group({s}),\n")
            f.write("  ],\n")
        f.write("];\n")

    log_path = work / "run.log"
    out_path = work / "per_combo_results.g"
    gens_dir = work / "lifts"
    gens_dir.mkdir(exist_ok=True)
    if log_path.exists(): log_path.unlink()
    if out_path.exists(): out_path.unlink()
    run_g = work / "run.g"
    driver = (DRIVER_GAP
              .replace("__LOG__", to_cyg(log_path))
              .replace("__SUBS__", to_cyg(subs_g))
              .replace("__OUT__", to_cyg(out_path))
              .replace("__GENS_DIR__", to_cyg(gens_dir)))
    run_g.write_text(driver, encoding="utf-8")

    print(f"Running GAP (this may take a while)...")
    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    elapsed = time.time() - t0
    print(f"GAP done ({elapsed:.0f}s).")

    # Parse per_combo_results.g
    if not out_path.exists():
        sys.exit(f"GAP did not produce {out_path}")
    text = out_path.read_text(encoding="utf-8")
    rows = []
    for m in re.finditer(r'\["([^"]+)",\s*(\d+),\s*(\d+)\]', text):
        rows.append((m.group(1), int(m.group(2)), int(m.group(3))))

    s18_part = s18_partition_name(s16_part)
    csv = work / "per_combo.csv"
    with open(csv, "w", encoding="utf-8") as f:
        f.write("combo,n_subs,predicted,actual,delta\n")
        total_pred = 0; total_act = 0; total_delta = 0
        mismatches = []
        for name, n_subs, pred in rows:
            s18c = s18_combo_name(name)
            act = actual_combo_count(s18_part, s18c)
            delta = (pred - act) if act is not None else None
            f.write(f"{name},{n_subs},{pred},{act if act is not None else ''},{delta if delta is not None else ''}\n")
            total_pred += pred
            if act is not None:
                total_act += act
                total_delta += delta
                if delta != 0:
                    mismatches.append((name, n_subs, pred, act, delta))

    print(f"\nCSV written: {csv}")
    print(f"Totals: predicted={total_pred}, actual={total_act}, delta={total_delta}")
    print(f"\nMismatched combos ({len(mismatches)} of {len(rows)}):")
    print(f"{'combo':<45} {'n_subs':>7} {'predicted':>10} {'actual':>8} {'delta':>8}")
    print("-" * 90)
    mismatches.sort(key=lambda r: -r[4])  # biggest delta first
    for name, n_subs, pred, act, delta in mismatches[:50]:
        print(f"{name:<45} {n_subs:>7} {pred:>10} {act:>8} {delta:>+8}")
    if len(mismatches) > 50:
        print(f"... ({len(mismatches) - 50} more in CSV)")


if __name__ == "__main__":
    main()
