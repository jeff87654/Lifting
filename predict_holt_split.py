#!/usr/bin/env python3
"""
predict_holt_split.py — package-Goursat predictor for multi-cluster
NON_PREDICTABLE combos.

For an S_n combo c whose species multiset partitions into >=2 distinct-species
clusters, split the cluster set into two non-empty groups L and R.  Look up
pre-enumerated source files for c|_L (in S_{m_L}) and c|_R (in S_{m_R}).
For each (H1 in src_L, H2 in src_R) pair, count S_n-classes of Goursat fiber
products via Aut(Q)-orbit counting under (Stab_{N1}(K1) x Stab_{N2}(K2)).

Restricted to splits where the two halves have DIFFERENT species multisets
(no cross-package S_n swap symmetry).  Single-cluster combos require the
m=2 Burnside variant and are handled separately.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
SN_DIR = Path(os.environ.get("PREDICT_SN_DIR", str(ROOT / "parallel_sn")))
S18_DIR = ROOT / "parallel_s18"
COMPARE = ROOT / "predict_species_tmp" / "18" / "_compare_report.json"
TMP = Path(os.environ.get("PREDICT_HOLT_SPLIT_TMP_DIR",
                          str(ROOT / "predict_species_tmp" / "_holt_split")))
TMP.mkdir(parents=True, exist_ok=True)
H_CACHE_DIR = Path(os.environ.get("PREDICT_H_CACHE_DIR",
                                   str(ROOT / "predict_species_tmp" / "_h_cache")))
H_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_path_for_source(src_file: Path) -> Path:
    """Return _h_cache path matching predict_s18_species's convention.
    src_file = parallel_sn/<n>/<part>/<combo>.g  ->  _h_cache/<n>/<part>/<combo>.g"""
    rel = src_file.relative_to(SN_DIR)
    return H_CACHE_DIR / rel

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def parse_combo_str(s: str) -> tuple[tuple[int, int], ...]:
    pairs = re.findall(r'\[(\d+),(\d+)\]', s)
    return tuple(sorted((int(d), int(t)) for d, t in pairs))


def combo_filename(combo) -> str:
    return "_".join(f"[{d},{t}]" for d, t in sorted(combo))


def combo_partition(combo) -> str:
    return "[" + ",".join(str(d) for d, _ in sorted(combo, reverse=True)) + "]"


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


def source_path(combo) -> Path:
    m = sum(d for d, _ in combo)
    return SN_DIR / str(m) / combo_partition(combo) / f"{combo_filename(combo)}.g"


def candidate_splits(combo):
    """Enumerate cluster-respecting splits of `combo` into (left, right) with
    DIFFERENT species multisets and existing source files on both sides.
    Yields (left_combo, right_combo, n_left, n_right, src_left, src_right)
    tuples ranked by n_left * n_right ascending."""
    clusters = Counter(combo)
    species = sorted(clusters.keys())
    k = len(species)
    if k < 2:
        return
    candidates = []
    for mask in range(1, 2 ** k - 1):
        # avoid duplicate (mask, complement) pairs
        if mask >= 2 ** k - 1 - mask:
            continue
        left_species = [species[i] for i in range(k) if (mask >> i) & 1]
        right_species = [species[i] for i in range(k) if not ((mask >> i) & 1)]
        left = tuple(sorted(sp for sp in left_species for _ in range(clusters[sp])))
        right = tuple(sorted(sp for sp in right_species for _ in range(clusters[sp])))
        # If left and right have IDENTICAL species multisets we'd need
        # Burnside swap-counting; skip for now.
        if Counter(left) == Counter(right):
            continue
        sl = source_path(left)
        sr = source_path(right)
        if not sl.exists() or not sr.exists():
            continue
        nl = len(parse_combo_file(sl))
        nr = len(parse_combo_file(sr))
        candidates.append((nl * nr, left, right, nl, nr, sl, sr))
    candidates.sort(key=lambda x: x[0])
    for c in candidates:
        yield c[1], c[2], c[3], c[4], c[5], c[6]


GAP_PACKAGE_GOURSAT = r"""
LogTo("__LOG__");

ML := __M_LEFT__;
MR := __M_RIGHT__;
TARGET_N := ML + MR;
SUBS_LEFT_PATH  := "__SUBS_L__";
SUBS_RIGHT_PATH := "__SUBS_R__";
CACHE_LEFT_PATH  := "__CACHE_L__";
CACHE_RIGHT_PATH := "__CACHE_R__";

Print("holt_split: m_left=", ML, " m_right=", MR, " target_n=", TARGET_N, "\n");

S_ML := SymmetricGroup(ML);
S_MR := SymmetricGroup(MR);

ConjAction := function(K, g) return K^g; end;

SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then
        return [n, 0, IdGroup(G)];
    fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

InducedAutoGens := function(stab, G, hom)
    return List(GeneratorsOfGroup(stab),
        s -> InducedAutomorphism(hom, ConjugatorAutomorphism(G, s)));
end;

# Count (Stab_NH1 x Stab_NH2)-orbits on isos Q2 -> Q1 via BFS.
CountOrbitsBFS := function(Q2, Q1, AutQ2, iso21, A1_gens, A2_gens)
    local isos, n, gensQ2, KeyOf, idx, i, seen, n_orb, queue, j, phi,
          alpha, beta, neighbor, k, key;
    isos := List(AsList(AutQ2), a -> a * iso21);
    n := Length(isos);
    gensQ2 := GeneratorsOfGroup(Q2);
    KeyOf := function(phi) return List(gensQ2, q -> Image(phi, q)); end;
    idx := rec();
    for i in [1..n] do idx.(String(KeyOf(isos[i]))) := i; od;
    seen := ListWithIdenticalEntries(n, false);
    n_orb := 0;
    for i in [1..n] do
        if seen[i] then continue; fi;
        n_orb := n_orb + 1;
        queue := [i]; seen[i] := true;
        while Length(queue) > 0 do
            j := Remove(queue);
            phi := isos[j];
            for alpha in A1_gens do
                neighbor := phi * alpha;
                key := String(KeyOf(neighbor));
                if IsBound(idx.(key)) then
                    k := idx.(key);
                    if not seen[k] then seen[k] := true; Add(queue, k); fi;
                fi;
            od;
            for beta in A2_gens do
                neighbor := InverseGeneralMapping(beta) * phi;
                key := String(KeyOf(neighbor));
                if IsBound(idx.(key)) then
                    k := idx.(key);
                    if not seen[k] then seen[k] := true; Add(queue, k); fi;
                fi;
            od;
        od;
    od;
    return n_orb;
end;

# Reconstruct per-side H data from a cached H_CACHE entry (loaded from disk).
# Cache entry shape: rec(H_gens, N_H_gens, orbits := [rec(K_H_gens, Stab_NH_KH_gens, qsize, qid)]).
# This avoids the expensive Normalizer + NormalSubgroups + Orbits computation.
SafeGroup := function(gens, default_amb)
    if Length(gens) = 0 then return TrivialSubgroup(default_amb); fi;
    return Group(gens);
end;

ReconstructHData := function(entry, S_M)
    local H, N, res, orbit_data, K, hom, Q, qsize, qid, Stab, i, key, hom_triv;
    H := SafeGroup(entry.H_gens, S_M);
    N := SafeGroup(entry.N_H_gens, S_M);
    res := rec(H := H, N := N, orbits := []);
    # The cache (predict_s18_species format) excludes K = H (trivial-Q orbit).
    # Re-add it explicitly so ContribForH1H2's qsize=1 fast path fires for the
    # direct-product term.
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N, AutQ := fail, A_gens := []));
    for orbit_data in entry.orbits do
        K := SafeGroup(orbit_data.K_H_gens, S_M);
        hom := NaturalHomomorphismByNormalSubgroup(H, K);
        Q := Range(hom);
        qsize := orbit_data.qsize;
        qid := orbit_data.qid;
        Stab := SafeGroup(orbit_data.Stab_NH_KH_gens, S_M);
        if qsize > 1 then
            Add(res.orbits, rec(K := K, hom := hom, Q := Q,
                qsize := qsize, qid := qid, Stab := Stab,
                AutQ := AutomorphismGroup(Q),
                A_gens := InducedAutoGens(Stab, H, hom)));
        else
            Add(res.orbits, rec(K := K, hom := hom, Q := Q,
                qsize := qsize, qid := qid, Stab := Stab,
                AutQ := fail, A_gens := []));
        fi;
    od;
    res.byqid := rec();
    for i in [1..Length(res.orbits)] do
        key := String(res.orbits[i].qid);
        if not IsBound(res.byqid.(key)) then res.byqid.(key) := []; fi;
        Add(res.byqid.(key), i);
    od;
    return res;
end;

# Save per-side H_CACHE to disk (predict_s18_species format) so future runs
# can reload.
SaveHCacheList := function(path, h_cache)
    PrintTo(path, "H_CACHE := ", h_cache, ";\n");
end;

# Build cache entry from scratch (only used when cache file missing).
ComputeHCacheEntry := function(H, S_M)
    local N_H, normals, K_H_orbit, K_H, hom_H, Q_H, Stab_NH_KH, orbits;
    N_H := Normalizer(S_M, H);
    normals := NormalSubgroups(H);
    orbits := [];
    for K_H_orbit in Orbits(N_H, normals, ConjAction) do
        K_H := K_H_orbit[1];
        hom_H := NaturalHomomorphismByNormalSubgroup(H, K_H);
        Q_H := Range(hom_H);
        Stab_NH_KH := Stabilizer(N_H, K_H, ConjAction);
        Add(orbits, rec(
            K_H_gens := GeneratorsOfGroup(K_H),
            Stab_NH_KH_gens := GeneratorsOfGroup(Stab_NH_KH),
            qsize := Size(Q_H),
            qid := SafeId(Q_H)
        ));
    od;
    return rec(
        H_gens := GeneratorsOfGroup(H),
        N_H_gens := GeneratorsOfGroup(N_H),
        orbits := orbits
    );
end;

# Per-H side data: for each N_H-orbit on NormalSubgroups(H), compute
# K, hom, Q, qsize, qid, Stab, AutQ, A_gens.
ComputeHData := function(H, S_M)
    local N, normals, res, orbit, K, hom, Q, qsize, qid, Stab, i, key;
    N := Normalizer(S_M, H);
    normals := NormalSubgroups(H);
    res := rec(H := H, N := N, orbits := []);
    for orbit in Orbits(N, normals, ConjAction) do
        K := orbit[1];
        hom := NaturalHomomorphismByNormalSubgroup(H, K);
        Q := Range(hom);
        qsize := Size(Q);
        qid := SafeId(Q);
        Stab := Stabilizer(N, K, ConjAction);
        if qsize > 1 then
            Add(res.orbits, rec(K := K, hom := hom, Q := Q,
                qsize := qsize, qid := qid, Stab := Stab,
                AutQ := AutomorphismGroup(Q),
                A_gens := InducedAutoGens(Stab, H, hom)));
        else
            Add(res.orbits, rec(K := K, hom := hom, Q := Q,
                qsize := qsize, qid := qid, Stab := Stab,
                AutQ := fail, A_gens := []));
        fi;
    od;
    # Index orbits by qid for O(1) qid lookup
    res.byqid := rec();
    for i in [1..Length(res.orbits)] do
        key := String(res.orbits[i].qid);
        if not IsBound(res.byqid.(key)) then res.byqid.(key) := []; fi;
        Add(res.byqid.(key), i);
    od;
    return res;
end;

ContribForH1H2 := function(H1data, H2data)
    local contrib, h1orb, h2idxs, h2idx, h2orb, isoTH, key;
    contrib := 0;
    # Pair every H1 quotient orbit with every H2 quotient orbit on matching qid
    for h1orb in H1data.orbits do
        key := String(h1orb.qid);
        if not IsBound(H2data.byqid.(key)) then continue; fi;
        h2idxs := H2data.byqid.(key);

        # Trivial Q on both sides: K_H1 = H1 paired with K_H2 = H2 -> 1 fiber product.
        if h1orb.qsize = 1 then
            for h2idx in h2idxs do
                if H2data.orbits[h2idx].qsize = 1 then
                    contrib := contrib + 1;
                fi;
            od;
            continue;
        fi;

        # Non-trivial Q.  Fast path |Q|=2: Aut(C_2) trivial -> 1 orbit per match.
        if h1orb.qsize = 2 then
            for h2idx in h2idxs do
                if H2data.orbits[h2idx].qsize = 2 then
                    contrib := contrib + 1;
                fi;
            od;
            continue;
        fi;

        # General Aut(Q)-orbit BFS.
        for h2idx in h2idxs do
            h2orb := H2data.orbits[h2idx];
            if h2orb.qsize <> h1orb.qsize then continue; fi;
            isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
            if isoTH = fail then continue; fi;
            contrib := contrib + CountOrbitsBFS(
                h2orb.Q, h1orb.Q, h2orb.AutQ, isoTH,
                h1orb.A_gens, h2orb.A_gens);
        od;
    od;
    return contrib;
end;

# ---- Load right-side cache or compute from scratch ----
H_CACHE_R := fail;
if CACHE_RIGHT_PATH <> "" and IsExistingFile(CACHE_RIGHT_PATH) then
    H_CACHE := fail;
    Read(CACHE_RIGHT_PATH);   # populates H_CACHE
    if H_CACHE <> fail then
        H_CACHE_R := H_CACHE;
        Print("loaded right-side cache: ", Length(H_CACHE_R), " entries from ",
              CACHE_RIGHT_PATH, "\n");
    fi;
fi;
if H_CACHE_R = fail then
    Read(SUBS_RIGHT_PATH);    # SUBGROUPS := [...]
    SUBGROUPS_RIGHT := SUBGROUPS;
    Print("computing right-side H_CACHE for ", Length(SUBGROUPS_RIGHT),
          " subgroups...\n");
    t_compute := Runtime();
    H_CACHE_R := List(SUBGROUPS_RIGHT, H -> ComputeHCacheEntry(H, S_MR));
    Print("  done in ", (Runtime() - t_compute) / 1000.0, "s\n");
    if CACHE_RIGHT_PATH <> "" then
        SaveHCacheList(CACHE_RIGHT_PATH, H_CACHE_R);
        Print("  saved to ", CACHE_RIGHT_PATH, "\n");
    fi;
fi;

# ---- Load left-side cache or compute from scratch ----
H_CACHE_L := fail;
if CACHE_LEFT_PATH <> "" and IsExistingFile(CACHE_LEFT_PATH) then
    H_CACHE := fail;
    Read(CACHE_LEFT_PATH);
    if H_CACHE <> fail then
        H_CACHE_L := H_CACHE;
        Print("loaded left-side cache: ", Length(H_CACHE_L), " entries from ",
              CACHE_LEFT_PATH, "\n");
    fi;
fi;
if H_CACHE_L = fail then
    Read(SUBS_LEFT_PATH);
    SUBGROUPS_LEFT := SUBGROUPS;
    Print("computing left-side H_CACHE for ", Length(SUBGROUPS_LEFT),
          " subgroups...\n");
    t_compute := Runtime();
    H_CACHE_L := List(SUBGROUPS_LEFT, H -> ComputeHCacheEntry(H, S_ML));
    Print("  done in ", (Runtime() - t_compute) / 1000.0, "s\n");
    if CACHE_LEFT_PATH <> "" then
        SaveHCacheList(CACHE_LEFT_PATH, H_CACHE_L);
        Print("  saved to ", CACHE_LEFT_PATH, "\n");
    fi;
fi;

Print("loaded: |L|=", Length(H_CACHE_L), " |R|=", Length(H_CACHE_R), "\n");

# Reconstruct full H-data (with AutQ, A_gens) from cache for the right side.
t0 := Runtime();
Print("reconstructing right-side data...\n");
H2DATA := List(H_CACHE_R, e -> ReconstructHData(e, S_MR));
Print("  done in ", (Runtime() - t0) / 1000.0, "s\n");

TOTAL := 0;
t1 := Runtime();
n_left := Length(H_CACHE_L);
for i in [1..n_left] do
    H1data := ReconstructHData(H_CACHE_L[i], S_ML);
    for j in [1..Length(H2DATA)] do
        TOTAL := TOTAL + ContribForH1H2(H1data, H2DATA[j]);
    od;
    if i mod 5 = 0 or i = n_left then
        Print("  [", i, "/", n_left, "] total=", TOTAL,
              "  elapsed=", (Runtime() - t1) / 1000.0, "s\n");
    fi;
od;

Print("\nPREDICTED_TOTAL: ", TOTAL, "\n");
LogTo();
QUIT;
"""


def write_subs(path: Path, subs: list[str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("SUBGROUPS := [\n")
        for i, s in enumerate(subs):
            sep = "," if i < len(subs) - 1 else ""
            f.write(f"  Group({s}){sep}\n")
        f.write("];\n")


def run_holt_split(combo, force=False, timeout=3600):
    """Predict count for `combo` via Holt package split."""
    splits = list(candidate_splits(combo))
    if not splits:
        return {"error": "no valid multi-cluster split", "combo": combo_filename(combo)}
    left, right, n_left, n_right, sl, sr = splits[0]
    work = TMP / combo_filename(combo)
    work.mkdir(parents=True, exist_ok=True)
    result_path = work / "result.json"
    if result_path.exists() and not force:
        return json.loads(result_path.read_text())

    m_left = sum(d for d, _ in left)
    m_right = sum(d for d, _ in right)

    subs_l = parse_combo_file(sl)
    subs_r = parse_combo_file(sr)
    subs_l_g = work / "subs_left.g"
    subs_r_g = work / "subs_right.g"
    write_subs(subs_l_g, subs_l)
    write_subs(subs_r_g, subs_r)

    log = work / "run.log"
    if log.exists(): log.unlink()
    cache_l = cache_path_for_source(sl)
    cache_r = cache_path_for_source(sr)
    cache_l.parent.mkdir(parents=True, exist_ok=True)
    cache_r.parent.mkdir(parents=True, exist_ok=True)
    run_g = work / "run.g"
    run_g.write_text(
        GAP_PACKAGE_GOURSAT
        .replace("__LOG__", to_cyg(log))
        .replace("__M_LEFT__", str(m_left))
        .replace("__M_RIGHT__", str(m_right))
        .replace("__SUBS_L__", to_cyg(subs_l_g))
        .replace("__SUBS_R__", to_cyg(subs_r_g))
        .replace("__CACHE_L__", to_cyg(cache_l))
        .replace("__CACHE_R__", to_cyg(cache_r)),
        encoding="utf-8",
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
    elapsed = round(time.time() - t0, 1)
    log_text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    m = re.search(r"PREDICTED_TOTAL:\s*(\d+)", log_text)
    if not m:
        out = {"error": "no PREDICTED_TOTAL", "log_tail": log_text[-2000:],
               "elapsed_s": elapsed}
        result_path.write_text(json.dumps(out, indent=2))
        return out
    out = {
        "combo": combo_filename(combo),
        "left": combo_filename(left),
        "right": combo_filename(right),
        "m_left": m_left,
        "m_right": m_right,
        "n_left": n_left,
        "n_right": n_right,
        "predicted": int(m.group(1)),
        "elapsed_s": elapsed,
    }
    result_path.write_text(json.dumps(out, indent=2))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", help="combo string e.g. [3,1]_[3,1]_[6,12]_[6,12]")
    ap.add_argument("--all-nonpred", action="store_true",
                    help="run on all multi-cluster NON_PREDICTABLE combos")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--max", type=int, default=None,
                    help="limit run count (for testing)")
    ap.add_argument("--smallest-first", action="store_true",
                    help="order combos by stored actual ascending")
    args = ap.parse_args()

    if args.combo:
        combo = parse_combo_str(args.combo)
        result = run_holt_split(combo, force=args.force, timeout=args.timeout)
        print(json.dumps(result, indent=2))
        return

    if args.all_nonpred:
        if not COMPARE.exists():
            print(f"Compare report missing: {COMPARE}")
            sys.exit(1)
        data = json.load(open(COMPARE))
        rows = [r for r in data["rows"] if r["status"] == "NON_PREDICTABLE"]

        def has_split(r):
            combo = parse_combo_str(r["combo"])
            return next(candidate_splits(combo), None) is not None

        eligible = [r for r in rows if has_split(r)]
        if args.smallest_first:
            eligible.sort(key=lambda r: r.get("actual") or 0)
        if args.max:
            eligible = eligible[:args.max]
        print(f"Running {len(eligible)} multi-cluster NON_PREDICTABLE combos")
        n_match = n_diff = n_err = 0
        for idx, r in enumerate(eligible, 1):
            combo = parse_combo_str(r["combo"])
            actual = r.get("actual")
            print(f"[{idx}/{len(eligible)}] {r['partition']} {r['combo']}"
                  f" (actual={actual})... ", end="", flush=True)
            t0 = time.time()
            result = run_holt_split(combo, force=args.force, timeout=args.timeout)
            dt = time.time() - t0
            if "error" in result:
                print(f"ERROR ({result['error']}, {dt:.1f}s)")
                n_err += 1
                continue
            pred = result["predicted"]
            if actual is not None and pred == actual:
                print(f"MATCH pred={pred} ({dt:.1f}s)")
                n_match += 1
            else:
                delta = pred - (actual or 0)
                print(f"DIFF pred={pred} actual={actual} delta={delta:+} ({dt:.1f}s)")
                n_diff += 1
        print(f"\n=== Summary: match={n_match} diff={n_diff} error={n_err} ===")
        return

    ap.print_help()


if __name__ == "__main__":
    main()
