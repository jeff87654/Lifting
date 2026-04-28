#!/usr/bin/env python3
"""
predict_s18_species.py — Species-aware Goursat lift predictor.

Generalizes predict_s18_from_s16.py from "+[2,1]" to any added orbit species
(d, t). For target FPF combo c on S_n:
  - For each species (d, t) appearing exactly once in c (distinguished),
    decompose c = c' + (d, t) where c' is a combo on S_(n-d).
  - Read verified subgroup list from parallel_sn/<n-d>/<part(c')>/<combo(c')>.g
  - Run a GAP driver that, per H in the list, counts fiber products of
    H x T = TransitiveGroup(d, t) over common quotients Q, modulo the
    induced (N_{S_(n-d)}(H) x N_{S_d}(T)) action on isomorphisms Q_H ~ Q_T.
  - Sum gives the predicted count for c on S_n.

Modes:
  --reduction-test           Reduce to +(2,1); compare to predict_s18_tmp/.
  --validate-fpf N           Predict every FPF combo of S_N from sources S2..S(N-2).
  --target N --partition P   Predict combos for a single partition P of S_N.
  --target N --all           Predict every FPF combo of S_N (mostly for N=18).

Output: predict_species_tmp/<target_n>/<combo_filename>/from_<dt_str>/result.json
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
SN_DIR = ROOT / "parallel_sn"            # parallel_sn/<n>/<partition>/<combo>.g
S18_DIR = ROOT / "parallel_s18"          # in-progress S18 data
TMP_DIR = ROOT / "predict_species_tmp"
TMP_DIR.mkdir(exist_ok=True)
H_CACHE_DIR = TMP_DIR / "_h_cache"       # per-source-file H-side precompute cache
H_CACHE_DIR.mkdir(exist_ok=True)


def cache_path_for_source(src_file: Path) -> Path:
    """H-cache path for a source combo file. Lives at
       predict_species_tmp/_h_cache/<m>/<part>/<combo>.g
    Cache is keyed by (m, partition, combo) implicit in the path. Stable
    across runs since parallel_sn/ source files don't change."""
    rel = src_file.relative_to(SN_DIR)
    return H_CACHE_DIR / rel

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"

OEIS = {1: 1, 2: 2, 3: 4, 4: 11, 5: 19, 6: 56, 7: 96, 8: 296, 9: 554,
        10: 1593, 11: 3094, 12: 10723, 13: 20832, 14: 75154, 15: 159129,
        16: 686165, 17: 1466358, 18: 7274651}
# FPF(n) = OEIS(n) - OEIS(n-1)
FPF_TARGET = {n: OEIS[n] - OEIS[n - 1] for n in range(2, 19)}


# ---------------------------------------------------------------------------
# Combo / partition parsing
# ---------------------------------------------------------------------------
_COMBO_FILENAME_RE = re.compile(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]")


def parse_combo_str(s: str) -> tuple[tuple[int, int], ...]:
    """Parse combo from filename like '[2,1]_[6,8]_[10,3]' OR header '[ [2,1], [6,8] ]'."""
    pairs = _COMBO_FILENAME_RE.findall(s)
    return tuple(sorted((int(d), int(t)) for d, t in pairs))


def combo_filename(combo: tuple[tuple[int, int], ...]) -> str:
    """Canonical filename: sorted [d,t] pairs joined by underscore (no .g)."""
    return "_".join(f"[{d},{t}]" for d, t in sorted(combo))


def combo_partition(combo: tuple[tuple[int, int], ...]) -> str:
    """Partition string for parallel_sn/<n>/ folder lookup: '[10,8,6]' sorted desc."""
    parts = sorted((d for d, _ in combo), reverse=True)
    return "[" + ",".join(str(p) for p in parts) + "]"


def partition_of(combo) -> tuple[int, ...]:
    return tuple(sorted((d for d, _ in combo), reverse=True))


def is_distinguished(combo, dt) -> bool:
    """A species (d,t) is distinguished in combo iff it appears exactly once."""
    return Counter(combo)[dt] == 1


def remove_one(combo, dt) -> tuple[tuple[int, int], ...]:
    out = list(combo)
    out.remove(dt)
    return tuple(sorted(out))


# ---------------------------------------------------------------------------
# Combo file IO (reused logic from predict_s18_from_s16.py)
# ---------------------------------------------------------------------------
_DEDUPED_RE = re.compile(r"^#\s*deduped:\s*(\d+)", re.MULTILINE)
_COMBO_HEADER_RE = re.compile(r"^#\s*combo:\s*(\[.*\])", re.MULTILINE)


def parse_combo_file(path: Path) -> list[str]:
    """Return list of generator-list strings (each a valid GAP list literal)."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = text.replace("\\\n", "").replace("\\\r\n", "")
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    text = "\n".join(lines)
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        if text[i] != "[":
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
        out.append(text[i:j + 1])
        i = j + 1
    return out


def read_deduped(path: Path) -> int | None:
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:1024]
    except Exception:
        return None
    m = _DEDUPED_RE.search(head)
    return int(m.group(1)) if m else None


def read_combo_header(path: Path) -> tuple[tuple[int, int], ...] | None:
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:2048]
    except Exception:
        return None
    # GAP wraps long lines with `\\` + newline.  Unwrap before regex.
    head = head.replace("\\\n", "").replace("\\\r\n", "")
    m = _COMBO_HEADER_RE.search(head)
    return parse_combo_str(m.group(1)) if m else None


def find_source_combo_file(target_n: int, c_prime: tuple, d: int) -> Path | None:
    """Look up source combo file at parallel_sn/<n-d>/<part(c')>/<combo(c').g>."""
    src_n = target_n - d
    src_dir = SN_DIR / str(src_n) / combo_partition(c_prime)
    if not src_dir.is_dir():
        return None
    f = src_dir / (combo_filename(c_prime) + ".g")
    return f if f.is_file() else None


# ---------------------------------------------------------------------------
# GAP driver template
# ---------------------------------------------------------------------------
DRIVER_GAP = r"""
LogTo("__LOG__");

# ---- inputs (substituted by Python) ----
M     := __M__;        # source degree (m = target_n - d)
DD    := __D__;        # added orbit degree
TID   := __T_ID__;     # TransitiveIdentification of added orbit type
SUBS_PATH := "__SUBS_CYG__";

Print("predict_species: m=", M, " d=", DD, " t=", TID, "\n");
Read(SUBS_PATH);   # defines SUBGROUPS := [Group(...), ...];
Print("Loaded ", Length(SUBGROUPS), " source subgroups.\n");

S_M := SymmetricGroup(M);
T   := TransitiveGroup(DD, TID);
S_D := SymmetricGroup(DD);
N_T := Normalizer(S_D, T);

# Conjugation action of group on subgroups
ConjAction := function(K, g) return K^g; end;

# Structural fingerprint for matching quotient isomorphism types.
# Uses IdGroup when the SmallGroups library covers the order; otherwise
# falls back to a structural tuple (size, abelian invariants, derived series
# size profile) that is a sufficient discriminator for matching against
# IsomorphismGroups (which we always call to confirm).
SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then
        return [n, 0, IdGroup(G)];
    fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

# Build induced auto generator list from Stab_N(K) on Q = G/K.
# Returned list contains automorphisms in family of AutomorphismGroup(Range(hom)).
InducedAutoGens := function(stab, G, hom)
    return List(GeneratorsOfGroup(stab),
        s -> InducedAutomorphism(hom, ConjugatorAutomorphism(G, s)));
end;

# Pre-compute T-side data once: for each N_T-orbit on NormalSubgroups(T),
# record K_T, hom_T, Q_T, qsize, qid, AutQT, A_T_in_QT (induced auto subgroup).
T_orbit_data := [];
for orbit in Orbits(N_T, NormalSubgroups(T), ConjAction) do
    Add(T_orbit_data, rec(K_T := orbit[1]));
od;
for r in T_orbit_data do
    r.hom_T := NaturalHomomorphismByNormalSubgroup(T, r.K_T);
    r.Q_T   := Range(r.hom_T);
    r.qsize := Size(r.Q_T);
    r.qid   := SafeId(r.Q_T);
    r.Stab_NT_KT := Stabilizer(N_T, r.K_T, ConjAction);
    if r.qsize > 1 then
        r.AutQT := AutomorphismGroup(r.Q_T);
        r.A_T_gens := InducedAutoGens(r.Stab_NT_KT, T, r.hom_T);
    else
        r.AutQT := fail;
        r.A_T_gens := [];
    fi;
od;

# Allowed quotient sizes / qids that can match against H.
AllowedSizes := Set(List(T_orbit_data, x -> x.qsize));
AllowedQids  := Set(List(T_orbit_data, x -> x.qid));

# Group T-orbit data by qid string for O(1) match-lookup.
T_by_qid := rec();
for r in T_orbit_data do
    key := String(r.qid);
    if not IsBound(T_by_qid.(key)) then
        T_by_qid.(key) := [];
    fi;
    Add(T_by_qid.(key), r);
od;

Print("T has ", Length(T_orbit_data), " N_T-orbits, AllowedSizes=", AllowedSizes, "\n");

# Count (Stab_NH x Stab_NT)-orbits on Iso(Q_T, Q_H) via BFS.
# A_H_gens: list of induced autos in Aut(Q_H), act by phi -> phi * alpha (GAP).
# A_T_gens: list of induced autos in Aut(Q_T), act by
#           phi -> InverseGeneralMapping(beta) * phi (GAP).
# Returns number of orbits.
CountOrbitsBFS := function(Q_T, Q_H, AutQT, isoTH, A_H_gens, A_T_gens)
    local isos, n, gensQT, KeyOf, idx, i, seen, n_orb, queue, j, phi,
          alpha, beta, neighbor, k, key;
    # Every iso Q_T -> Q_H equals (some auto of Q_T) * isoTH.
    isos := List(AsList(AutQT), aT -> aT * isoTH);
    n := Length(isos);
    gensQT := GeneratorsOfGroup(Q_T);

    KeyOf := function(phi)
        return List(gensQT, q -> Image(phi, q));
    end;

    idx := rec();
    for i in [1..n] do
        idx.(String(KeyOf(isos[i]))) := i;
    od;

    seen := ListWithIdenticalEntries(n, false);
    n_orb := 0;
    for i in [1..n] do
        if seen[i] then continue; fi;
        n_orb := n_orb + 1;
        queue := [i];
        seen[i] := true;
        while Length(queue) > 0 do
            j := Remove(queue);
            phi := isos[j];
            for alpha in A_H_gens do
                neighbor := phi * alpha;
                key := String(KeyOf(neighbor));
                if IsBound(idx.(key)) then
                    k := idx.(key);
                    if not seen[k] then
                        seen[k] := true;
                        Add(queue, k);
                    fi;
                fi;
            od;
            for beta in A_T_gens do
                neighbor := InverseGeneralMapping(beta) * phi;
                key := String(KeyOf(neighbor));
                if IsBound(idx.(key)) then
                    k := idx.(key);
                    if not seen[k] then
                        seen[k] := true;
                        Add(queue, k);
                    fi;
                fi;
            od;
        od;
    od;
    return n_orb;
end;

# For one source subgroup H, sum over (K_H, K_T)-orbit pairs with iso quotient.
# Direct-product term (trivial Q) contributes 1 baseline.
# Hot-path optimizations (Performance Review):
#   - Filter NormalSubgroups(H) by Index in AllowedSizes BEFORE building
#     quotients / autos / stabilizers.
#   - Lookup matching T data by IdGroup string.
#   - Fast path for |Q|=2 (Aut(C2) trivial) avoids BFS / AutomorphismGroup(Q_H).
ContribForH := function(H)
    local N_H, contrib, normals, eligible, K_H_orbit, K_H, hom_H, Q_H,
          qid_H, key, tlist, Stab_NH_KH, AutQH, A_H_gens,
          tdata, isoTH;

    N_H := Normalizer(S_M, H);
    contrib := 1;   # trivial quotient: direct product H x T

    normals := NormalSubgroups(H);
    # Skip K_H = H (trivial quotient handled by baseline) and any K_H whose
    # quotient size doesn't appear among T's quotients.
    eligible := Filtered(normals, K -> K <> H and (Index(H, K) in AllowedSizes));

    for K_H_orbit in Orbits(N_H, eligible, ConjAction) do
        K_H := K_H_orbit[1];
        hom_H := NaturalHomomorphismByNormalSubgroup(H, K_H);
        Q_H := Range(hom_H);
        qid_H := SafeId(Q_H);
        key := String(qid_H);
        if not IsBound(T_by_qid.(key)) then continue; fi;
        tlist := T_by_qid.(key);

        # Fast path: |Q_H| = 2.  Aut(C_2) = trivial, so each (K_H, K_T) pair
        # contributes exactly 1 iso orbit.
        if Size(Q_H) = 2 then
            contrib := contrib + Length(tlist);
            continue;
        fi;

        # General path: need Aut(Q_H) and induced N_H action.
        Stab_NH_KH := Stabilizer(N_H, K_H, ConjAction);
        AutQH := AutomorphismGroup(Q_H);
        A_H_gens := InducedAutoGens(Stab_NH_KH, H, hom_H);

        for tdata in tlist do
            isoTH := IsomorphismGroups(tdata.Q_T, Q_H);
            if isoTH = fail then continue; fi;
            contrib := contrib + CountOrbitsBFS(tdata.Q_T, Q_H,
                                                tdata.AutQT, isoTH,
                                                A_H_gens, tdata.A_T_gens);
        od;
    od;
    return contrib;
end;

TOTAL := 0;
t0 := Runtime();
for i in [1..Length(SUBGROUPS)] do
    TOTAL := TOTAL + ContribForH(SUBGROUPS[i]);
    if i mod 25 = 0 or i = Length(SUBGROUPS) then
        Print("  [", i, "/", Length(SUBGROUPS), "]  total=", TOTAL,
              "  elapsed=", (Runtime() - t0) / 1000, "s\n");
    fi;
od;

Print("\nPREDICTED_TOTAL: ", TOTAL, "\n");
Print("SUBGROUP_COUNT: ", Length(SUBGROUPS), "\n");
LogTo();
QUIT;
"""


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def write_subgroups_g(out_path: Path, subs: list[str]) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Auto-generated FPF subgroup list (S_n conjugacy class reps)\n")
        f.write("SUBGROUPS := [\n")
        for i, s in enumerate(subs):
            sep = "," if i < len(subs) - 1 else ""
            f.write(f"  Group({s}){sep}\n")
        f.write("];\n")


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


# ---------------------------------------------------------------------------
# Batched GAP runner: process many decompositions sharing (d, t, m) in one
# GAP session.  GAP cold-start is ~5.5s; batching brings per-job amortized
# cost down to the actual computation time.
# ---------------------------------------------------------------------------
BATCH_HEADER_GAP = r"""
LogTo("__BATCH_LOG__");
M     := __M__;
DD    := __D__;
TID   := __T_ID__;
Print("batch_setup: m=", M, " d=", DD, " t=", TID, "\n");

S_M := SymmetricGroup(M);
T   := TransitiveGroup(DD, TID);
S_D := SymmetricGroup(DD);
N_T := Normalizer(S_D, T);

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

T_orbit_data := [];
for orbit in Orbits(N_T, NormalSubgroups(T), ConjAction) do
    Add(T_orbit_data, rec(K_T := orbit[1]));
od;
for r in T_orbit_data do
    r.hom_T := NaturalHomomorphismByNormalSubgroup(T, r.K_T);
    r.Q_T   := Range(r.hom_T);
    r.qsize := Size(r.Q_T);
    r.qid   := SafeId(r.Q_T);
    r.Stab_NT_KT := Stabilizer(N_T, r.K_T, ConjAction);
    if r.qsize > 1 then
        r.AutQT := AutomorphismGroup(r.Q_T);
        r.A_T_gens := InducedAutoGens(r.Stab_NT_KT, T, r.hom_T);
    else
        r.AutQT := fail;
        r.A_T_gens := [];
    fi;
od;
AllowedSizes := Set(List(T_orbit_data, x -> x.qsize));

T_by_qid := rec();
for r in T_orbit_data do
    key := String(r.qid);
    if not IsBound(T_by_qid.(key)) then T_by_qid.(key) := []; fi;
    Add(T_by_qid.(key), r);
od;
Print("batch_T: ", Length(T_orbit_data), " orbits, AllowedSizes=", AllowedSizes, "\n");

CountOrbitsBFS := function(Q_T, Q_H, AutQT, isoTH, A_H_gens, A_T_gens)
    local isos, n, gensQT, KeyOf, idx, i, seen, n_orb, queue, j, phi,
          alpha, beta, neighbor, k, key;
    isos := List(AsList(AutQT), aT -> aT * isoTH);
    n := Length(isos);
    gensQT := GeneratorsOfGroup(Q_T);
    KeyOf := function(phi) return List(gensQT, q -> Image(phi, q)); end;
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
            for alpha in A_H_gens do
                neighbor := phi * alpha;
                key := String(KeyOf(neighbor));
                if IsBound(idx.(key)) then
                    k := idx.(key);
                    if not seen[k] then seen[k] := true; Add(queue, k); fi;
                fi;
            od;
            for beta in A_T_gens do
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

ContribForH := function(H)
    local N_H, contrib, normals, eligible, K_H_orbit, K_H, hom_H, Q_H,
          qid_H, key, tlist, Stab_NH_KH, AutQH, A_H_gens, tdata, isoTH;
    N_H := Normalizer(S_M, H);
    contrib := 1;
    normals := NormalSubgroups(H);
    eligible := Filtered(normals, K -> K <> H and (Index(H, K) in AllowedSizes));
    for K_H_orbit in Orbits(N_H, eligible, ConjAction) do
        K_H := K_H_orbit[1];
        hom_H := NaturalHomomorphismByNormalSubgroup(H, K_H);
        Q_H := Range(hom_H);
        qid_H := SafeId(Q_H);
        key := String(qid_H);
        if not IsBound(T_by_qid.(key)) then continue; fi;
        tlist := T_by_qid.(key);
        if Size(Q_H) = 2 then
            contrib := contrib + Length(tlist);
            continue;
        fi;
        Stab_NH_KH := Stabilizer(N_H, K_H, ConjAction);
        AutQH := AutomorphismGroup(Q_H);
        A_H_gens := InducedAutoGens(Stab_NH_KH, H, hom_H);
        for tdata in tlist do
            isoTH := IsomorphismGroups(tdata.Q_T, Q_H);
            if isoTH = fail then continue; fi;
            contrib := contrib + CountOrbitsBFS(tdata.Q_T, Q_H, tdata.AutQT,
                                                isoTH, A_H_gens, tdata.A_T_gens);
        od;
    od;
    return contrib;
end;

# ----- Persistent H-cache helpers -----
# H_CACHE entry shape:
#   rec( H_gens, N_H_gens, orbits := [
#          rec(K_H_gens, Stab_NH_KH_gens, qsize, qid)
#       ] )
# Cached values are independent of T (the added orbit), so the same cache
# is reused across every batch sharing a source file.  AllowedSizes / qid
# filters are applied at use-time inside ContribForH_cached, so a cache
# generated for one T works for any other T.

ComputeHCacheEntry := function(H)
    local N_H, normals, K_H_orbit, K_H, hom_H, Q_H, Stab_NH_KH, orbits;
    N_H := Normalizer(S_M, H);
    normals := NormalSubgroups(H);
    orbits := [];
    for K_H_orbit in Orbits(N_H, Filtered(normals, K -> K <> H), ConjAction) do
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

SafeGroup := function(gens)
    if Length(gens) = 0 then return TrivialSubgroup(SymmetricGroup(M)); fi;
    return Group(gens);
end;

ContribForH_cached := function(h_entry)
    local H, contrib, orbit_data, key, tlist, K_H, hom_H, Q_H, AutQH,
          Stab_NH_KH, A_H_gens, tdata, isoTH;
    H := SafeGroup(h_entry.H_gens);
    contrib := 1;   # trivial-quotient direct product
    for orbit_data in h_entry.orbits do
        if not (orbit_data.qsize in AllowedSizes) then continue; fi;
        key := String(orbit_data.qid);
        if not IsBound(T_by_qid.(key)) then continue; fi;
        tlist := T_by_qid.(key);
        if orbit_data.qsize = 2 then
            contrib := contrib + Length(tlist);
            continue;
        fi;
        K_H := SafeGroup(orbit_data.K_H_gens);
        hom_H := NaturalHomomorphismByNormalSubgroup(H, K_H);
        Q_H := Range(hom_H);
        AutQH := AutomorphismGroup(Q_H);
        Stab_NH_KH := SafeGroup(orbit_data.Stab_NH_KH_gens);
        A_H_gens := InducedAutoGens(Stab_NH_KH, H, hom_H);
        for tdata in tlist do
            isoTH := IsomorphismGroups(tdata.Q_T, Q_H);
            if isoTH = fail then continue; fi;
            contrib := contrib + CountOrbitsBFS(tdata.Q_T, Q_H, tdata.AutQT,
                                                isoTH, A_H_gens, tdata.A_T_gens);
        od;
    od;
    return contrib;
end;

# Save H_CACHE to disk (overwrite, single Print).  GAP's PrintTo + record/list
# output is read-back compatible.
SaveHCache := function(path, h_cache)
    PrintTo(path, "H_CACHE := ", h_cache, ";\n");
end;

Print("BATCH_SETUP_DONE\n");
"""

BATCH_JOB_GAP = r"""
# job: __JOB_KEY__   subs: __SUBS_CYG__   cache: __CACHE_CYG__
H_CACHE := fail;
SUBGROUPS := fail;
__JOB_T0__ := Runtime();
__JOB_CACHE_HIT__ := false;
if IsExistingFile("__CACHE_CYG__") then
    Read("__CACHE_CYG__");
    if H_CACHE <> fail then __JOB_CACHE_HIT__ := true; fi;
fi;
if not __JOB_CACHE_HIT__ then
    Read("__SUBS_CYG__");
    H_CACHE := List(SUBGROUPS, ComputeHCacheEntry);
    SaveHCache("__CACHE_CYG__", H_CACHE);
fi;
__JOB_TOTAL__ := 0;
for __JOB_H__ in [1..Length(H_CACHE)] do
    __JOB_TOTAL__ := __JOB_TOTAL__ + ContribForH_cached(H_CACHE[__JOB_H__]);
od;
Print("RESULT key=__JOB_KEY__ predicted=", __JOB_TOTAL__,
      " elapsed_ms=", Runtime() - __JOB_T0__,
      " n_subs=", Length(H_CACHE),
      " cache_hit=", __JOB_CACHE_HIT__, "\n");
"""

BATCH_FOOTER_GAP = r"""
Print("BATCH_DONE\n");
LogTo();
QUIT;
"""


def run_batch(d: int, t: int, m: int, jobs: list[dict],
              timeout: int | None = None,
              namespace: str | None = None) -> dict:
    """Run a batch of jobs sharing (d, t, m) in one GAP session.

    Each job dict must have: 'key' (unique str), 'src_file' (Path), 'subs_g' (Path)
    where subs_g is where to write the SUBGROUPS list. Updates each job dict
    with 'predicted', 'elapsed_ms', 'n_subs', or 'error'.

    `namespace` (e.g. target partition string) prefixes the batch dir so
    parallel workers running different target partitions don't overwrite
    each other's batch.log.  H-cache stays per-source-file (unaffected).
    """
    if not jobs:
        return {}
    if namespace:
        batch_dir = TMP_DIR / "_batch" / namespace / f"d{d}_t{t}_m{m}"
    else:
        batch_dir = TMP_DIR / "_batch" / f"d{d}_t{t}_m{m}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    log_path = batch_dir / "batch.log"
    if log_path.exists():
        log_path.unlink()
    run_path = batch_dir / "run.g"

    # Write SUBGROUPS file per job (parse once, write GAP form).
    # Determine the H-cache path per job (persistent, keyed by source file).
    for job in jobs:
        if "subs_g" not in job:
            job["subs_g"] = batch_dir / f"subs_{job['key']}.g"
        if not job["subs_g"].exists():
            subs = parse_combo_file(job["src_file"])
            write_subgroups_g(job["subs_g"], subs)
        # H-cache lives next to the source file's hierarchy (persists across runs).
        cp = cache_path_for_source(job["src_file"])
        cp.parent.mkdir(parents=True, exist_ok=True)
        job["cache_g"] = cp

    # Build GAP script.
    parts = [(BATCH_HEADER_GAP
              .replace("__BATCH_LOG__", to_cyg(log_path))
              .replace("__M__", str(m))
              .replace("__D__", str(d))
              .replace("__T_ID__", str(t)))]
    for job in jobs:
        parts.append(BATCH_JOB_GAP
                     .replace("__JOB_KEY__", job["key"])
                     .replace("__SUBS_CYG__", to_cyg(job["subs_g"]))
                     .replace("__CACHE_CYG__", to_cyg(job["cache_g"])))
    parts.append(BATCH_FOOTER_GAP)
    run_path.write_text("\n".join(parts), encoding="utf-8")

    cyg_run = to_cyg(run_path)
    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{cyg_run}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        for j in jobs:
            j["error"] = "batch timeout"
        return {"elapsed_s": time.time() - t0, "stderr": "timeout"}
    elapsed = time.time() - t0
    log = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""

    # Parse RESULT lines.  cache_hit field is optional (older format had none).
    # GAP's Print wraps lines at ~80 cols, so allow whitespace after each `=`.
    pat = re.compile(r"RESULT\s+key=\s*(\S+)\s+predicted=\s*(\d+)\s+elapsed_ms=\s*(\d+)\s+n_subs=\s*(\d+)(?:\s+cache_hit=\s*(\S+))?")
    by_key = {m.group(1): (int(m.group(2)), int(m.group(3)), int(m.group(4)),
                            (m.group(5) or "").lower() == "true")
              for m in pat.finditer(log)}
    for job in jobs:
        if job["key"] in by_key:
            pred, ms, nsubs, hit = by_key[job["key"]]
            job["predicted"] = pred
            job["elapsed_ms"] = ms
            job["n_subs"] = nsubs
            job["cache_hit"] = hit
        else:
            job["error"] = "no RESULT line"
            job["log_tail"] = "\n".join(log.splitlines()[-15:])

    return {"elapsed_s": elapsed, "n_jobs": len(jobs),
            "n_ok": sum(1 for j in jobs if "predicted" in j),
            "stderr": (proc.stderr or "")[-2000:]}


# ---------------------------------------------------------------------------
# Predictor entry: predict count(combo c on S_n) from one decomposition c=c'+(d,t)
# ---------------------------------------------------------------------------
def predict_decomposition(target_n: int, target_combo: tuple, dt: tuple[int, int],
                          force: bool = False, timeout: int | None = None) -> dict:
    """Predict count(target_combo on S_target_n) by removing one block of species dt.

    Returns a dict with predicted count, or {'predicted': None} on failure.
    """
    if not is_distinguished(target_combo, dt):
        return {"target_n": target_n, "target_combo": list(target_combo),
                "dt": list(dt), "error": "not distinguished"}

    c_prime = remove_one(target_combo, dt)
    src_n = target_n - dt[0]
    if src_n < 1:
        return {"target_n": target_n, "target_combo": list(target_combo),
                "dt": list(dt), "error": f"src_n={src_n} < 1"}

    src_file = find_source_combo_file(target_n, c_prime, dt[0])
    if src_file is None:
        return {"target_n": target_n, "target_combo": list(target_combo),
                "dt": list(dt), "src_n": src_n, "src_combo": list(c_prime),
                "error": "source file missing"}

    target_str = combo_filename(target_combo)
    dt_str = f"[{dt[0]},{dt[1]}]"
    work = TMP_DIR / str(target_n) / target_str / f"from_{dt_str}"
    work.mkdir(parents=True, exist_ok=True)

    rj = work / "result.json"
    if rj.exists() and not force:
        try:
            r = json.loads(rj.read_text())
            if r.get("predicted") is not None:
                return r
        except Exception:
            pass

    subs = parse_combo_file(src_file)
    subs_g = work / "subgroups.g"
    write_subgroups_g(subs_g, subs)

    log_path = work / "run.log"
    if log_path.exists():
        log_path.unlink()
    run_g = work / "run.g"
    driver = (DRIVER_GAP
              .replace("__LOG__", to_cyg(log_path))
              .replace("__M__", str(src_n))
              .replace("__D__", str(dt[0]))
              .replace("__T_ID__", str(dt[1]))
              .replace("__SUBS_CYG__", to_cyg(subs_g)))
    run_g.write_text(driver, encoding="utf-8")

    t0 = time.time()
    try:
        log = run_gap(work, log_path, timeout=timeout)
        elapsed = time.time() - t0
    except subprocess.TimeoutExpired:
        return {"target_n": target_n, "target_combo": list(target_combo),
                "dt": list(dt), "src_n": src_n, "src_combo": list(c_prime),
                "src_file": str(src_file), "error": "timeout"}

    m_pred = re.search(r"PREDICTED_TOTAL:\s*(\d+)", log)
    m_cnt = re.search(r"SUBGROUP_COUNT:\s*(\d+)", log)
    predicted = int(m_pred.group(1)) if m_pred else None
    sub_count = int(m_cnt.group(1)) if m_cnt else len(subs)

    result = {
        "target_n": target_n,
        "target_combo": list(target_combo),
        "dt": list(dt),
        "src_n": src_n,
        "src_combo": list(c_prime),
        "src_file": str(src_file),
        "subgroup_count": sub_count,
        "predicted": predicted,
        "elapsed_s": round(elapsed, 1),
    }
    if predicted is None:
        result["error"] = "GAP did not produce PREDICTED_TOTAL"
        result["log_tail"] = "\n".join(log.splitlines()[-15:])
    rj.write_text(json.dumps(result, indent=2))
    return result


def predict_combo(target_n: int, target_combo: tuple, force: bool = False,
                  timeout: int | None = None,
                  preferred_dt: tuple[int, int] | None = None) -> dict:
    """Predict combo via every distinguished decomposition with available source.

    Single-block combos [[d,t]] are the base case — count is always 1
    (one S_d-conjugacy class of TransitiveGroup(d, t) in S_d). Returned
    as the "base_case" prediction.

    If preferred_dt is given, only run that decomposition (used by reduction-test).
    Returns {'predictions': {dt_str: predicted, ...}, 'consensus': int|None,
             'consistent': bool, 'distinguished_count': int, 'base_case': bool}.
    """
    if len(target_combo) == 1:
        return {
            "target_n": target_n,
            "target_combo": list(target_combo),
            "predictions": {"base_case": 1},
            "errors": {},
            "consensus": 1,
            "consistent": True,
            "distinguished_count": 1,
            "base_case": True,
        }

    species = list(set(target_combo))
    distinguished = [s for s in species if is_distinguished(target_combo, s)]
    preds = {}
    errors = {}

    candidates = [preferred_dt] if preferred_dt else distinguished
    for dt in candidates:
        if dt is None:
            continue
        if not is_distinguished(target_combo, dt):
            continue
        r = predict_decomposition(target_n, target_combo, dt, force=force, timeout=timeout)
        key = f"[{dt[0]},{dt[1]}]"
        if r.get("predicted") is not None:
            preds[key] = r["predicted"]
        else:
            errors[key] = r.get("error", "unknown")

    if preds:
        vals = list(preds.values())
        consensus = vals[0] if all(v == vals[0] for v in vals) else None
        consistent = consensus is not None
    else:
        consensus = None
        consistent = False

    return {
        "target_n": target_n,
        "target_combo": list(target_combo),
        "predictions": preds,
        "errors": errors,
        "consensus": consensus,
        "consistent": consistent,
        "distinguished_count": len(distinguished),
        "base_case": False,
    }


# ---------------------------------------------------------------------------
# Mode: --reduction-test (regression check vs predict_s18_tmp/)
# ---------------------------------------------------------------------------
def mode_reduction_test(timeout: int | None = None, force: bool = False) -> int:
    """For each existing predict_s18_tmp/<lambda>/result.json (which used +[2]),
    re-derive the same prediction with the new species-aware driver and check
    they match exactly.  This is verification step 1 from the plan.
    """
    legacy_dir = ROOT / "predict_s18_tmp"
    if not legacy_dir.is_dir():
        print(f"missing legacy dir: {legacy_dir}")
        return 1

    rows = []
    fails = 0
    for d in sorted(legacy_dir.iterdir()):
        if not d.is_dir():
            continue
        rj = d / "result.json"
        if not rj.exists():
            continue
        try:
            legacy = json.loads(rj.read_text())
        except Exception:
            continue
        s16_part = legacy.get("partition")
        legacy_pred = legacy.get("predicted")
        if not s16_part or legacy_pred is None:
            continue

        # The legacy script aggregates over ALL combos of an S16 partition lambda
        # to predict count(lambda + [2]) summed across all combos of (lambda+[2]).
        # We replicate that by walking each combo of lambda on S16, applying +(2,1),
        # and summing over distinguished decompositions only (legacy did this implicitly
        # because its DRIVER_GAP uses the +[2] formula on every H).
        s16_dir = SN_DIR / "16" / s16_part
        if not s16_dir.is_dir():
            print(f"{s16_part}: skip (no parallel_sn/16/{s16_part})")
            continue

        s18_combos_predicted = 0
        for combo_file in sorted(s16_dir.iterdir()):
            if not (combo_file.is_file() and combo_file.suffix == ".g"):
                continue
            if combo_file.name.startswith("summary"):
                continue
            c_prime = read_combo_header(combo_file)
            if c_prime is None:
                continue
            target_combo = tuple(sorted(list(c_prime) + [(2, 1)]))
            if not is_distinguished(target_combo, (2, 1)):
                # +[2,1] non-distinguished: legacy formula gave an upper bound; we skip.
                continue
            r = predict_decomposition(18, target_combo, (2, 1), timeout=timeout, force=force)
            if r.get("predicted") is None:
                print(f"  FAIL combo={combo_file.name}: {r.get('error')}")
                fails += 1
                continue
            s18_combos_predicted += r["predicted"]

        match = (s18_combos_predicted == legacy_pred)
        rows.append((s16_part, legacy_pred, s18_combos_predicted, match))
        flag = "OK" if match else "MISMATCH"
        print(f"{s16_part:<22} legacy={legacy_pred:>8}  new={s18_combos_predicted:>8}  {flag}")
        if not match:
            fails += 1

    print()
    print(f"Reduction test: {sum(1 for r in rows if r[3])}/{len(rows)} match, {fails} failures.")
    return 0 if fails == 0 else 2


# ---------------------------------------------------------------------------
# Mode: --validate-fpf N
# ---------------------------------------------------------------------------
def iter_target_combos(target_n: int):
    """Iterate every combo of S_target_n that appears in either parallel_sn/<n>/
    (for n <= 17) or parallel_s18/ (for n = 18). Yields (combo_file_path, combo)."""
    if target_n == 18:
        base = S18_DIR
    else:
        base = SN_DIR / str(target_n)
    if not base.is_dir():
        return
    for part_dir in sorted(base.iterdir()):
        if not part_dir.is_dir():
            continue
        for f in sorted(part_dir.iterdir()):
            if not (f.is_file() and f.suffix == ".g"):
                continue
            if f.name.startswith("summary") or "backup" in f.name.lower():
                continue
            c = read_combo_header(f) or parse_combo_str(f.stem)
            if not c:
                continue
            yield f, c


def mode_validate_fpf(target_n: int, timeout: int | None = None, force: bool = False) -> int:
    """Predict every FPF combo of S_target_n from sources S2..S(target_n - 2).
    Compare the sum to FPF(target_n) = OEIS(target_n) - OEIS(target_n - 1).
    """
    target = FPF_TARGET[target_n]
    print(f"=== validate-fpf {target_n}: target FPF = {target} ===")

    total_pred = 0
    n_combos = 0
    n_distinguished = 0
    n_non_pred = 0
    n_under = 0
    n_over = 0
    n_match = 0
    n_inconsistent = 0
    actuals = {}
    discrepancies = []

    for combo_file, combo in iter_target_combos(target_n):
        n_combos += 1
        actual = read_deduped(combo_file)
        if actual is not None:
            actuals[combo_filename(combo)] = actual

        species = list(set(combo))
        distinguished = [s for s in species if is_distinguished(combo, s)]
        if not distinguished and len(combo) > 1:
            n_non_pred += 1
            continue
        n_distinguished += 1

        r = predict_combo(target_n, combo, timeout=timeout, force=force)
        if r["predictions"] and not r["consistent"]:
            n_inconsistent += 1
            discrepancies.append(("INCONSISTENT", combo, r["predictions"], actual))
            print(f"  {combo_filename(combo)}: INCONSISTENT {r['predictions']}")
            continue
        if r["consensus"] is None:
            print(f"  {combo_filename(combo)}: NO PREDICTION (errors={r['errors']})")
            continue
        pred = r["consensus"]
        total_pred += pred

        if actual is not None:
            if pred == actual:
                n_match += 1
            elif pred > actual:
                n_under += 1
                discrepancies.append(("UNDER", combo, pred, actual))
            else:
                n_over += 1
                discrepancies.append(("OVER", combo, pred, actual))

    print(f"\nCombos: {n_combos}")
    print(f"  distinguished:  {n_distinguished}")
    print(f"  non-predictable: {n_non_pred}")
    print(f"Predicted (distinguished only): {total_pred}")
    print(f"Target FPF({target_n}):    {target}")
    if n_non_pred == 0:
        print(f"Delta: {total_pred - target}")
    else:
        print(f"Partial sum: {n_non_pred} non-predictable combos missing — delta vs target not meaningful.")
    print(f"Match/Under/Over/Inconsistent: {n_match}/{n_under}/{n_over}/{n_inconsistent}")

    if discrepancies[:20]:
        print("\nFirst discrepancies:")
        for kind, combo, pred, actual in discrepancies[:20]:
            print(f"  [{kind}] {combo_filename(combo)}: pred={pred} actual={actual}")

    out = TMP_DIR / str(target_n) / "_validation_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "target_n": target_n,
        "target_fpf": target,
        "predicted_total": total_pred,
        "delta": total_pred - target,
        "n_combos": n_combos,
        "n_distinguished": n_distinguished,
        "n_non_predictable": n_non_pred,
        "n_match": n_match,
        "n_under": n_under,
        "n_over": n_over,
        "n_inconsistent": n_inconsistent,
    }, indent=2))
    return 0 if total_pred == target else 3


# ---------------------------------------------------------------------------
# Mode: --target N --partition P / --target N --all
# ---------------------------------------------------------------------------
def collect_decompositions(target_n: int, partition: str | None,
                           cheapest_only: bool = False) -> list[dict]:
    """Walk every combo for target_n (optionally restricted to one partition)
    and emit one job dict per available distinguished decomposition.
    Skips base-case (single-block) combos.

    If cheapest_only is True, emit only ONE distinguished decomposition per
    combo. Heuristic: pick the LARGEST-d species (= smallest m for the
    source). Smaller m typically has dramatically fewer source subgroups,
    which dominates per-H GAP cost; larger T is amortized across the batch.
    Loses cross-source consistency check but typically 5-20x faster for
    partitions with 3+ blocks.
    """
    jobs = []
    for combo_file, combo in iter_target_combos(target_n):
        if partition and combo_partition(combo) != partition:
            continue
        if len(combo) == 1:
            continue
        species = sorted(set(combo))
        candidates = [s for s in species if is_distinguished(combo, s)]
        if cheapest_only and candidates:
            candidates = [max(candidates)]   # largest d = smallest source m
        for dt in candidates:
            c_prime = remove_one(combo, dt)
            src_n = target_n - dt[0]
            src_file = find_source_combo_file(target_n, c_prime, dt[0])
            if src_file is None:
                continue
            target_str = combo_filename(combo)
            dt_str = f"[{dt[0]},{dt[1]}]"
            work = TMP_DIR / str(target_n) / target_str / f"from_{dt_str}"
            work.mkdir(parents=True, exist_ok=True)
            jobs.append({
                "target_n": target_n,
                "target_combo": list(combo),
                "dt": list(dt),
                "src_n": src_n,
                "src_combo": list(c_prime),
                "src_file": src_file,
                "work_dir": work,
                "target_str": target_str,
                "dt_str": dt_str,
                "key": f"{target_str}__{dt_str}".replace("[", "").replace("]", "").replace(",", "_"),
            })
    return jobs


def mode_target_batched(target_n: int, partition: str | None,
                        timeout: int | None = None, force: bool = False,
                        cheapest_only: bool = False) -> int:
    """Batched alternative to mode_target: groups decompositions by (d, t, m)
    and runs each group in one GAP session, amortizing the ~5.5s cold start.
    """
    jobs_all = collect_decompositions(target_n, partition, cheapest_only=cheapest_only)

    # Drop jobs with cached result.json unless --force.
    if not force:
        jobs_all = [j for j in jobs_all if not (j["work_dir"] / "result.json").exists()
                    or json.loads((j["work_dir"] / "result.json").read_text()).get("predicted") is None]

    # Group by (d, t, m) where m = src_n.
    groups = defaultdict(list)
    for j in jobs_all:
        key = (j["dt"][0], j["dt"][1], j["src_n"])
        groups[key].append(j)

    print(f"S{target_n}{' '+partition if partition else ''}: {len(jobs_all)} jobs in {len(groups)} (d,t,m) batches")

    # Namespace batch dirs by target partition to avoid log collisions when
    # multiple workers run different partitions concurrently.
    ns = (partition or f"all_S{target_n}").replace("[", "").replace("]", "").replace(",", "_")

    total_t0 = time.time()
    n_done = 0
    n_err = 0
    for (d, t, m), group_jobs in sorted(groups.items()):
        # subs_g paths inside _batch/<ns>/ dir
        for j in group_jobs:
            j["subs_g"] = TMP_DIR / "_batch" / ns / f"d{d}_t{t}_m{m}" / f"subs_{j['key']}.g"
        info = run_batch(d, t, m, group_jobs, timeout=timeout, namespace=ns)
        n_done += info.get("n_ok", 0)
        n_err += len(group_jobs) - info.get("n_ok", 0)
        # Write per-job result.json
        for j in group_jobs:
            res = {
                "target_n": j["target_n"],
                "target_combo": j["target_combo"],
                "dt": j["dt"],
                "src_n": j["src_n"],
                "src_combo": j["src_combo"],
                "src_file": str(j["src_file"]),
                "subgroup_count": j.get("n_subs"),
                "predicted": j.get("predicted"),
                "elapsed_s": (j["elapsed_ms"] / 1000.0) if "elapsed_ms" in j else None,
                "cache_hit": j.get("cache_hit"),
            }
            if "error" in j:
                res["error"] = j["error"]
                if "log_tail" in j:
                    res["log_tail"] = j["log_tail"]
            (j["work_dir"] / "result.json").write_text(json.dumps(res, indent=2))
        print(f"  d={d} t={t} m={m}: {info.get('n_ok',0)}/{len(group_jobs)} ok, "
              f"{info.get('elapsed_s', 0):.1f}s wall")

    print(f"\nDone: {n_done} ok / {n_err} errors / total {len(jobs_all)} jobs in {time.time()-total_t0:.1f}s")
    return 0 if n_err == 0 else 4


def mode_target(target_n: int, partition: str | None, all_combos: bool,
                timeout: int | None = None, force: bool = False) -> int:
    """Predict every combo for a single S_n partition (or all partitions)."""
    if all_combos and partition:
        print("specify either --partition or --all, not both")
        return 1

    n_done = 0
    for combo_file, combo in iter_target_combos(target_n):
        if partition and combo_partition(combo) != partition:
            continue
        r = predict_combo(target_n, combo, timeout=timeout, force=force)
        actual = read_deduped(combo_file)
        delta = (r["consensus"] - actual) if (r["consensus"] is not None and actual is not None) else None
        n_done += 1
        if r["consensus"] is None:
            print(f"  {combo_filename(combo)}: distinguished={r['distinguished_count']} no_pred")
        else:
            consist = "CONSISTENT" if r["consistent"] else "INCONSISTENT"
            d_str = f"delta={delta:+d}" if delta is not None else "(no actual)"
            print(f"  {combo_filename(combo)}: pred={r['consensus']} actual={actual} {d_str} {consist}")

    print(f"\n{n_done} combos processed for S{target_n}.")
    return 0


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reduction-test", action="store_true")
    ap.add_argument("--validate-fpf", type=int, action="append", default=[],
                    help="Validate predicted FPF total for S_N (sources S2..S(N-2))")
    ap.add_argument("--target", type=int, help="Target S_n (e.g., 18)")
    ap.add_argument("--partition", help="Single partition like '[10,8]'")
    ap.add_argument("--all", action="store_true", help="All partitions for --target")
    ap.add_argument("--batch", action="store_true",
                    help="Batched GAP runner for --target: groups jobs by (d,t,m), "
                         "amortizes ~5.5s GAP cold-start across many predictions.")
    ap.add_argument("--cheapest-only", action="store_true",
                    help="Only run smallest-d distinguished decomposition per combo. "
                         "Faster but loses cross-source consistency check.")
    ap.add_argument("--timeout", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    rc = 0
    if args.reduction_test:
        rc = mode_reduction_test(timeout=args.timeout, force=args.force)
        if rc != 0:
            return rc
    for n in args.validate_fpf:
        sub_rc = mode_validate_fpf(n, timeout=args.timeout, force=args.force)
        if sub_rc != 0:
            rc = sub_rc
    if args.target:
        if args.batch:
            sub_rc = mode_target_batched(args.target, args.partition,
                                         timeout=args.timeout, force=args.force,
                                         cheapest_only=args.cheapest_only)
        else:
            sub_rc = mode_target(args.target, args.partition, args.all,
                                 timeout=args.timeout, force=args.force)
        if sub_rc != 0:
            rc = sub_rc

    if not (args.reduction_test or args.validate_fpf or args.target):
        ap.error("specify --reduction-test, --validate-fpf N, or --target N (--partition P|--all)")

    return rc


if __name__ == "__main__":
    sys.exit(main())
