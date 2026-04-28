#!/usr/bin/env python3
"""
verify_nonpredictable.py — for each NON_PREDICTABLE S18 combo, run pairwise
RA-dedup on the actual stored subgroups in parallel_s18/<part>/<combo>.g.

This gives the TRUE distinct-class count for that combo (modulo S_18 conjugacy)
and compares to the stored 'deduped' value.

Output: per-combo (stored, true_distinct, redundant) tuples + summary.
Note: this only catches OVER-dedup (storing duplicates).  To also detect
MISSING classes, an independent re-enumeration is needed (separate tool).
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
S18_DIR = ROOT / "parallel_s18"
TMP = ROOT / "predict_species_tmp" / "_nonpred_verify"
TMP.mkdir(parents=True, exist_ok=True)

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def parse_combo_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = text.replace("\\\n", "").replace("\\\r\n", "")
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    text = "\n".join(lines)
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i].isspace(): i += 1; continue
        if text[i] != "[": i += 1; continue
        depth = 0; j = i
        while j < n:
            ch = text[j]
            if ch == "[": depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0: break
            j += 1
        if j >= n: break
        out.append(text[i:j+1])
        i = j + 1
    return out


GAP_DEDUPE = r"""
LogTo("__LOG__");
Read("__SUBS__");
S18 := SymmetricGroup(18);
n := Length(SUBGROUPS);

# Compute (size, IdGroup, AbelianInvariants) fingerprint for fast filtering.
fp := function(G)
    local sz, abi, idg;
    sz := Size(G);
    abi := AbelianInvariants(G);
    if IdGroupsAvailable(sz) then
        idg := IdGroup(G);
    else
        idg := [sz, AbelianInvariants(G), List(DerivedSeries(G), Size)];
    fi;
    return [sz, idg, abi];
end;

fps := List(SUBGROUPS, fp);

# UF_Union-UF_Find by RA within each fingerprint bucket.
parent := [1..n];
UF_Find := function(x)
    while parent[x] <> x do
        parent[x] := parent[parent[x]];
        x := parent[x];
    od;
    return x;
end;
UF_Union := function(x, y)
    local rx, ry;
    rx := UF_Find(x); ry := UF_Find(y);
    if rx <> ry then parent[ry] := rx; fi;
end;

# Bucket indices by fingerprint
bucket := rec();
for i in [1..n] do
    key := String(fps[i]);
    if not IsBound(bucket.(key)) then bucket.(key) := []; fi;
    Add(bucket.(key), i);
od;

n_pairs_checked := 0;
n_conj_pairs := 0;
for key in RecNames(bucket) do
    bk := bucket.(key);
    for i in [1..Length(bk)-1] do
        for j in [i+1..Length(bk)] do
            n_pairs_checked := n_pairs_checked + 1;
            if UF_Find(bk[i]) = UF_Find(bk[j]) then continue; fi;  # already merged
            if RepresentativeAction(S18, SUBGROUPS[bk[i]], SUBGROUPS[bk[j]]) <> fail then
                UF_Union(bk[i], bk[j]);
                n_conj_pairs := n_conj_pairs + 1;
            fi;
        od;
    od;
od;

# Count distinct classes
classes := Set([1..n], i -> UF_Find(i));
distinct := Length(classes);

Print("RESULT n=", n, " distinct=", distinct,
      " redundant=", n - distinct,
      " pairs_checked=", n_pairs_checked,
      " conj_pairs=", n_conj_pairs, "\n");
LogTo();
QUIT;
"""


def run_gap_dedupe(subs_g: Path, log_path: Path, timeout=600) -> dict:
    work = subs_g.parent
    run_g = work / "run.g"
    run_g.write_text(
        GAP_DEDUPE.replace("__LOG__", to_cyg(log_path))
                  .replace("__SUBS__", to_cyg(subs_g))
    )
    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    try:
        subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "elapsed_s": time.time() - t0}
    log = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
    m = re.search(
        r"RESULT n=(\d+) distinct=(\d+) redundant=(\d+) pairs_checked=(\d+) conj_pairs=(\d+)",
        log,
    )
    if not m:
        return {"error": "no RESULT line", "log_tail": log[-500:], "elapsed_s": time.time() - t0}
    return {
        "n_stored": int(m.group(1)),
        "distinct": int(m.group(2)),
        "redundant": int(m.group(3)),
        "pairs_checked": int(m.group(4)),
        "conj_pairs": int(m.group(5)),
        "elapsed_s": round(time.time() - t0, 1),
    }


def main():
    # UF_Find all NON_PREDICTABLE combos from the latest compare report
    rep_path = ROOT / "predict_species_tmp" / "18" / "_compare_report.json"
    if not rep_path.exists():
        print("Run compare_s18_species.py first")
        sys.exit(1)
    data = json.load(open(rep_path))
    nonpred = [r for r in data["rows"] if r["status"] == "NON_PREDICTABLE"]
    print(f"Found {len(nonpred)} NON_PREDICTABLE combos to verify")

    results = []
    for idx, r in enumerate(nonpred, 1):
        combo = r["combo"]
        partition = r["partition"]
        actual = r["actual"]
        if actual is None or actual <= 1:
            results.append({**r, "distinct": actual or 0, "redundant": 0, "skipped": True})
            continue
        if actual > 50:
            # Skip very large combos — RA too slow to be practical here.
            print(f"[{idx}/{len(nonpred)}] {partition} {combo} (n_stored={actual}): SKIP (too large)", flush=True)
            results.append({**r, "skipped_too_large": True})
            continue

        print(f"[{idx}/{len(nonpred)}] {partition} {combo} (n_stored={actual})... ", end="", flush=True)
        src = S18_DIR / partition / f"{combo}.g"
        if not src.exists():
            print("MISSING source file")
            results.append({**r, "error": "src not found"})
            continue

        ns = partition.strip("[]").replace(",", "_")
        cb = combo.replace("[", "").replace("]", "").replace(",", "_")
        work = TMP / ns / cb
        work.mkdir(parents=True, exist_ok=True)

        subs = parse_combo_file(src)
        subs_g = work / "subs.g"
        with open(subs_g, "w") as f:
            f.write("SUBGROUPS := [\n")
            for i, s in enumerate(subs):
                sep = "," if i < len(subs) - 1 else ""
                f.write(f"  Group({s}){sep}\n")
            f.write("];\n")

        log = work / "verify.log"
        if log.exists(): log.unlink()
        result = run_gap_dedupe(subs_g, log)
        if "error" in result:
            print(f"ERROR ({result.get('error')})")
            results.append({**r, **result})
            continue
        result["combo"] = combo
        result["partition"] = partition
        result["actual"] = actual
        result["bug"] = result["distinct"] != actual
        bug_str = " *S18-OVER*" if result["distinct"] < actual else ""
        print(f"distinct={result['distinct']} (stored={actual}, redundant={result['redundant']}, "
              f"{result['elapsed_s']}s){bug_str}")
        results.append(result)

    # Summary
    total_stored = sum(r.get("actual", 0) for r in results)
    total_distinct = sum(r.get("distinct", 0) for r in results)
    total_redundant = sum(r.get("redundant", 0) for r in results)
    n_buggy = sum(1 for r in results if r.get("bug"))
    print()
    print("=" * 70)
    print(f"NON_PREDICTABLE summary ({len(results)} combos):")
    print(f"  total stored:    {total_stored}")
    print(f"  total distinct:  {total_distinct}")
    print(f"  total redundant: {total_redundant}")
    print(f"  buggy combos:    {n_buggy}")

    out = TMP / "_nonpred_summary.json"
    out.write_text(json.dumps({
        "n_combos": len(results),
        "total_stored": total_stored,
        "total_distinct": total_distinct,
        "total_redundant": total_redundant,
        "n_buggy": n_buggy,
        "results": results,
    }, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
