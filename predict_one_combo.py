#!/usr/bin/env python3
"""
predict_one_combo.py — Run LiftCountPlusC2 on a SINGLE S16 combo file
and emit the predicted lift generators.

Usage:
    python predict_one_combo.py "[8,4,4]" "[4,3]_[4,3]_[8,26].g"
"""
import argparse, json, os, re, subprocess, sys, time
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

def parse_combo_file(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = text.replace("\\\n", "").replace("\\\r\n", "")
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    text = "\n".join(lines)
    out = []
    i, n = 0, len(text)
    while i < n:
        if text[i].isspace(): i += 1; continue
        if text[i] != "[": i += 1; continue
        depth, j = 0, i
        while j < n:
            if text[j] == "[": depth += 1
            elif text[j] == "]":
                depth -= 1
                if depth == 0: break
            j += 1
        if j >= n: break
        out.append(text[i:j+1]); i = j + 1
    return out


DRIVER = r"""
LogTo("__LOG__");
Read("__SUBS__");
S16 := SymmetricGroup(16);
SWAP := (17,18);

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
    local nrm, maxes, idx2, orbs, lifts, base, K;
    base := GeneratorsOfGroup(H);
    lifts := [];
    Add(lifts, Concatenation(base, [SWAP]));
    nrm := Normalizer(S16, H);
    maxes := MaximalSubgroupClassReps(H);
    idx2 := Filtered(maxes, K -> Index(H, K) = 2);
    if Length(idx2) = 0 then return lifts; fi;
    orbs := Orbits(nrm, idx2, function(K, g) return K^g; end);
    for K in List(orbs, Representative) do
        Add(lifts,
            List(base, function(h) if h in K then return h; else return h * SWAP; fi; end));
    od;
    return lifts;
end;

PrintTo("__OUT__", "# Predicted lifts (Goursat) for combo __CNAME__\n");
AppendTo("__OUT__", "# Source: __SRC__\n");
AppendTo("__OUT__", "# H_count: ", Length(SUBGROUPS), "\n");
total := 0;
t0 := Runtime();
for i in [1..Length(SUBGROUPS)] do
    H := SUBGROUPS[i];
    liftlist := LiftsForH(H);
    AppendTo("__OUT__", "# H#", i, "  |H|=", Size(H), "  lifts=", Length(liftlist), "\n");
    for g in liftlist do
        EmitGens("__OUT__", g);
    od;
    total := total + Length(liftlist);
    if i mod 25 = 0 or i = Length(SUBGROUPS) then
        Print("[", i, "/", Length(SUBGROUPS), "]  total=", total,
              "  elapsed=", Int((Runtime()-t0)/1000), "s\n");
    fi;
od;
AppendTo("__OUT__", "# PREDICTED_TOTAL: ", total, "\n");
Print("\nPREDICTED_TOTAL: ", total, "\n");
LogTo();
QUIT;
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("partition", help='S16 partition like "[8,4,4]"')
    ap.add_argument("combo",     help='combo file name like "[4,3]_[4,3]_[8,26].g"')
    args = ap.parse_args()

    src = S16_DIR / args.partition / args.combo
    if not src.exists(): sys.exit(f"missing {src}")
    work = TMP_DIR / f"{args.partition}_one" / args.combo.replace(".g", "")
    work.mkdir(parents=True, exist_ok=True)

    subs = parse_combo_file(src)
    print(f"{args.combo}: {len(subs)} subgroups")

    subs_g = work / "subgroups.g"
    with open(subs_g, "w", encoding="utf-8") as f:
        f.write("SUBGROUPS := [\n")
        for s in subs:
            f.write(f"  Group({s}),\n")
        f.write("];\n")

    log_path = work / "run.log"
    out_path = work / "lifts.g"
    if log_path.exists(): log_path.unlink()
    if out_path.exists(): out_path.unlink()
    run_g = work / "run.g"
    driver = (DRIVER
              .replace("__LOG__", to_cyg(log_path))
              .replace("__SUBS__", to_cyg(subs_g))
              .replace("__OUT__", to_cyg(out_path))
              .replace("__CNAME__", args.combo)
              .replace("__SRC__", to_cyg(src)))
    run_g.write_text(driver, encoding="utf-8")

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    print(f"Running GAP...")
    subprocess.run(cmd, env=env)
    print(f"GAP done in {time.time()-t0:.0f}s")

    # Parse predicted total from log or output
    pred = None
    if log_path.exists():
        m = re.search(r"PREDICTED_TOTAL:\s*(\d+)", log_path.read_text(errors="ignore"))
        if m: pred = int(m.group(1))

    # Find existing S18 combo dedup count
    parts = sorted([int(x) for x in args.partition.strip("[]").split(",")] + [2], reverse=True)
    s18_part = "[" + ",".join(str(p) for p in parts) + "]"
    s18_combo_name = "[2,1]_" + args.combo
    s18_path = S18_DIR / s18_part / s18_combo_name
    actual = None
    if s18_path.exists():
        head = s18_path.read_text(errors="ignore")[:512]
        m = re.search(r"^#\s*deduped:\s*(\d+)", head, re.MULTILINE)
        if m: actual = int(m.group(1))

    print()
    print("=" * 60)
    print(f"Combo:     {args.combo}")
    print(f"Predicted: {pred}")
    print(f"Actual:    {actual}")
    print(f"Delta:     {(pred - actual) if (pred is not None and actual is not None) else 'N/A'}")
    print(f"Lifts file: {out_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
