#!/usr/bin/env python3
"""
predict_2factor.py — Unified 2-factor Goursat predictor.

Combines three previous predictors that all do 2-block Goursat over an
H-cache shared backend:
  - distinguished-species pivot   (was predict_s18_species.py)
  - Holt cluster split            (was predict_holt_split.py)
  - Burnside m=2 (pure pair)      (was predict_burnside_m2.py)

The right side is either a source-file subgroup list (Holt mode) OR a
single TransitiveGroup(d,t) (distinguished + Burnside-m2 modes).  Mode
auto-detected from the combo's species multiplicities, or set explicitly.

Usage:
  python predict_2factor.py --combo "[2,1]_[2,1]_[7,1]_[7,1]"   # auto-detects
  python predict_2factor.py --combo "..." --mode burnside_m2
  python predict_2factor.py --combo "..." --emit-generators

Output: predict_species_tmp/_two_factor/<combo>/result.json
        + (if --emit-generators) predict_species_tmp/_two_factor/<combo>/fps.g
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
SN_DIR = Path(os.environ.get("PREDICT_SN_DIR", str(ROOT / "parallel_sn")))
S18_DIR = ROOT / "parallel_s18"
TMP = Path(os.environ.get("PREDICT_TMP_DIR",
                          str(ROOT / "predict_species_tmp" / "_two_factor")))
TMP.mkdir(parents=True, exist_ok=True)
H_CACHE_DIR = Path(os.environ.get("PREDICT_H_CACHE_DIR",
                                   str(ROOT / "predict_species_tmp" / "_h_cache")))
H_CACHE_DIR.mkdir(parents=True, exist_ok=True)

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"

# Saved GAP workspace: contains lifting_algorithm.g pre-loaded, so each GAP
# invocation skips the ~9-second full library + lifting_algorithm.g load.
LIFTING_WS = ROOT / "lifting.ws"
LIFTING_G = ROOT / "lifting_algorithm.g"


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def ensure_lifting_workspace():
    """Build lifting.ws workspace if it's missing or stale.
    Saves ~9 seconds per GAP invocation (12.9s cold -> 3.6s with `-L ws`)."""
    if (LIFTING_WS.exists() and
            LIFTING_WS.stat().st_mtime >= LIFTING_G.stat().st_mtime):
        return  # up to date
    print(f"Building GAP workspace at {LIFTING_WS} (one-time, ~15s)...",
          flush=True)
    save_g = ROOT / "_build_lifting_workspace.g"
    save_g.write_text(
        f'Read("{str(LIFTING_G).replace(chr(92), chr(47))}");\n'
        f'SaveWorkspace("{to_cyg(LIFTING_WS)}");\n'
        f'QUIT;\n', encoding="utf-8")
    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(save_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    subprocess.run(cmd, env=env, capture_output=True, timeout=120)
    elapsed = time.time() - t0
    if not LIFTING_WS.exists():
        raise RuntimeError(f"workspace build failed (took {elapsed:.1f}s)")
    print(f"  workspace built in {elapsed:.1f}s ({LIFTING_WS.stat().st_size//1024//1024} MB)",
          flush=True)


# Build workspace at module load (cheap if already up to date).
ensure_lifting_workspace()
LIFTING_WS_CYG = to_cyg(LIFTING_WS)


def _gap_run(cmd, env, timeout, diag_dir=None):
    """subprocess.run wrapper that handles "no timeout" mode safely.
    Avoids threading.Lock overflow on Windows for very large timeouts.
    If diag_dir is provided, writes proc.returncode/stderr/stdout to
    diag_dir/_gap_diag.txt for post-mortem inspection."""
    if timeout is None or timeout <= 0 or timeout >= 86400 * 30:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    else:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    if diag_dir is not None:
        try:
            from pathlib import Path as _Path
            d = _Path(diag_dir)
            d.mkdir(parents=True, exist_ok=True)
            (d / "_gap_diag.txt").write_text(
                f"returncode={proc.returncode}\n"
                f"--- stdout (last 5000) ---\n{proc.stdout[-5000:] if proc.stdout else ''}\n"
                f"--- stderr (last 5000) ---\n{proc.stderr[-5000:] if proc.stderr else ''}\n",
                encoding="utf-8")
        except Exception:
            pass
    return proc


def parse_combo_str(s):
    pairs = re.findall(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]", s)
    return tuple(sorted((int(d), int(t)) for d, t in pairs))


def combo_filename(combo):
    return "_".join(f"[{d},{t}]" for d, t in sorted(combo))


def combo_partition(combo):
    return "[" + ",".join(str(d) for d, _ in sorted(combo, reverse=True)) + "]"


def parse_combo_file(path):
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
        out.append(text[i:j+1]); i = j + 1
    return out


def source_path(combo):
    m = sum(d for d, _ in combo)
    return SN_DIR / str(m) / combo_partition(combo) / f"{combo_filename(combo)}.g"


def cache_path_for_source(src_file):
    return H_CACHE_DIR / src_file.relative_to(SN_DIR)


def partition_from_source(combo):
    """Parse the source file's first generator list to determine the
    block partition in EMBEDDING ORDER (i.e., the order blocks appear
    on points 1..M in the source file's subgroups).

    The recursive split-and-recurse logic in predict_2factor.py means the
    embedding of a multi-cluster source depends on which cluster ended up
    as LEFT vs RIGHT at each recursive step.  Rather than reproduce that
    logic, we read the source's first generator list and union the points
    within each cycle to recover the block partition empirically.

    For sources with no file (TG mode), falls back to a single block.
    """
    src = source_path(combo)
    if not src.exists():
        return sorted([d for d, _ in combo], reverse=True)  # safe fallback
    gens_lists = parse_combo_file(src)
    if not gens_lists:
        return sorted([d for d, _ in combo], reverse=True)
    first = gens_lists[0]  # e.g., "[(1,2)(3,4),(5,6,7),(8,9,10)]"
    cycles = re.findall(r'\(([0-9,\s]+)\)', first)
    parent = {}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for cyc in cycles:
        pts = [int(s.strip()) for s in cyc.split(',') if s.strip()]
        if not pts:
            continue
        for p in pts:
            if p not in parent:
                parent[p] = p
        for p in pts[1:]:
            ra, rb = find(p), find(pts[0])
            if ra != rb:
                parent[ra] = rb
    blocks = {}
    for p in parent:
        r = find(p)
        blocks.setdefault(r, []).append(p)
    if not blocks:
        return sorted([d for d, _ in combo], reverse=True)
    return [len(b) for b in sorted(blocks.values(), key=lambda b: min(b))]


# ---- Mode resolution ----------------------------------------------------
def auto_mode(combo):
    """Pick a mode based on combo's species multiplicities."""
    clusters = Counter(combo)
    distinguished = [sp for sp, mult in clusters.items() if mult == 1]
    if distinguished:
        return "distinguished"
    # No distinguished species.  Multi-cluster -> Holt split.
    if len(clusters) >= 2:
        return "holt_split"
    # Single species, all blocks identical.
    sp, mult = next(iter(clusters.items()))
    if mult == 2:
        return "burnside_m2"
    return "unsupported"


def resolve_inputs(combo, mode):
    """Determine (left_combo, right_combo_or_tg, m_left, m_right, swap_fix)
    where right_combo_or_tg is either a tuple-combo (subgroup-list mode) or
    a (d, t) tuple (TG mode)."""
    clusters = Counter(combo)

    if mode == "distinguished":
        # Pick the distinguished species with the smallest available source.
        distinguished = sorted(sp for sp, m in clusters.items() if m == 1)
        if not distinguished:
            raise ValueError("distinguished mode requires a species of multiplicity 1")
        # Try each candidate, prefer the one with the smallest source file.
        best = None
        for dt in distinguished:
            c_prime = tuple(sorted(x for x in combo if x != dt) +
                           [x for x in combo if x == dt][1:])
            # c_prime = combo minus one (d,t)
            c_prime = list(combo); c_prime.remove(dt); c_prime = tuple(sorted(c_prime))
            src = source_path(c_prime)
            if not src.exists(): continue
            n_subs = len(parse_combo_file(src))
            if best is None or n_subs < best[2]:
                best = (dt, c_prime, n_subs)
        if best is None:
            raise FileNotFoundError("no distinguished pivot has a source file")
        dt, c_prime, _ = best
        m_left = sum(d for d, _ in c_prime)
        m_right = dt[0]
        return {
            "left_combo": c_prime,
            "right_combo": None,
            "right_tg": dt,           # (d, t)
            "m_left": m_left,
            "m_right": m_right,
            "burnside_m2": False,
        }

    if mode == "holt_split":
        if len(clusters) < 2:
            raise ValueError("holt_split mode requires >=2 species clusters")
        # Find canonical split: each cluster on one side; pick split minimizing nL*nR.
        species = sorted(clusters.keys())
        k = len(species)
        best = None
        for mask in range(1, 2 ** k - 1):
            if mask >= 2 ** k - 1 - mask: continue   # avoid (mask, complement) duplicates
            left_species = [species[i] for i in range(k) if (mask >> i) & 1]
            right_species = [species[i] for i in range(k) if not ((mask >> i) & 1)]
            left = tuple(sorted(sp for sp in left_species for _ in range(clusters[sp])))
            right = tuple(sorted(sp for sp in right_species for _ in range(clusters[sp])))
            if Counter(left) == Counter(right): continue   # equal-species split: needs Burnside
            sl, sr = source_path(left), source_path(right)
            if not (sl.exists() and sr.exists()): continue
            nl, nr = len(parse_combo_file(sl)), len(parse_combo_file(sr))
            if best is None or nl * nr < best[0]:
                best = (nl * nr, left, right)
        if best is None:
            raise FileNotFoundError("no valid Holt split found")
        _, left, right = best
        return {
            "left_combo": left,
            "right_combo": right,
            "right_tg": None,
            "m_left": sum(d for d, _ in left),
            "m_right": sum(d for d, _ in right),
            "burnside_m2": False,
        }

    if mode == "burnside_m2":
        # Pure m=2 same-species: combo = [(d,t), (d,t)].  Both sides = TG(d,t).
        if len(clusters) != 1:
            raise ValueError("burnside_m2 mode requires single-cluster combo")
        sp, mult = next(iter(clusters.items()))
        if mult != 2:
            raise ValueError(f"burnside_m2 mode requires mult=2; got {mult}")
        d = sp[0]
        return {
            "left_combo": (sp,),     # single (d,t) on first d points -- TG(d,t)
            "right_combo": None,
            "right_tg": sp,
            "m_left": d,
            "m_right": d,
            "burnside_m2": True,
        }

    raise ValueError(f"unknown mode: {mode}")


# ---- GAP driver ---------------------------------------------------------
GAP_DRIVER = r"""
LogTo("__LOG__");

ML            := __M_LEFT__;
MR            := __M_RIGHT__;
TARGET_N      := ML + MR;
LEFT_PARTITION  := __M_LEFT_PARTITION__;   # block sizes desc, e.g. [4,4,4,4]
RIGHT_PARTITION := __M_RIGHT_PARTITION__;
SUBS_LEFT_PATH   := "__SUBS_L__";
SUBS_RIGHT_PATH  := "__SUBS_R__";
CACHE_LEFT_PATH  := "__CACHE_L__";
CACHE_RIGHT_PATH := "__CACHE_R__";
RIGHT_TG_D    := __TG_D__;       # 0 if right side is a source list
RIGHT_TG_T    := __TG_T__;
BURNSIDE_M2   := __BURNSIDE_M2__;   # 0 or 1
EMIT_GENS_PATH := "__GEN_PATH__";

Print("predict_2factor: ml=", ML, " mr=", MR, " target_n=", TARGET_N,
      " burnside_m2=", BURNSIDE_M2, "\n");

# ---- helpers ----
ConjAction := function(K, g) return K^g; end;

SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

InducedAutoGens := function(stab, G, hom)
    return List(GeneratorsOfGroup(stab),
        s -> InducedAutomorphism(hom, ConjugatorAutomorphism(G, s)));
end;

SafeGroup := function(gens, default_amb)
    if Length(gens) = 0 then return TrivialSubgroup(default_amb); fi;
    return Group(gens);
end;

# Subgroup helper that handles empty A_gens (used by opt 6 DoubleCosets path).
SafeSub := function(G, gens)
    if Length(gens) = 0 then return TrivialSubgroup(G); fi;
    return Subgroup(G, gens);
end;

# Goursat fiber product builder (from lifting_algorithm.g).
if not IsBound(_GoursatBuildFiberProduct) then Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g"); fi;

# Reconstruct H-side data with Aut(Q) and induced auto generators from a
# cached entry.  Cache shape: rec(H_gens, N_H_gens, orbits := [rec(K_H_gens,
# Stab_NH_KH_gens, qsize, qid)]).  Adds the trivial-Q (K = H) entry that the
# cache file omits.
ReconstructHData := function(entry, S_M)
    local H, N, res, orbit_data, K, Stab, i, key, hom_triv;
    H := SafeGroup(entry.H_gens, S_M);
    N := SafeGroup(entry.N_H_gens, S_M);
    res := rec(H := H, N := N, orbits := []);
    # Trivial-quotient orbit (always present; hom is fast for H/H).
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N, AutQ := fail, A_gens := [], full_aut := fail,
        H_ref := H));
    # Non-trivial orbits: hom and Q are deferred (computed lazily by EnsureHom).
    # NaturalHomomorphismByNormalSubgroup is the dominant cost for large H,
    # and most orbits never get paired against a matching RIGHT qid, so
    # deferring it is the dominant speed win.
    for orbit_data in entry.orbits do
        K := SafeGroup(orbit_data.K_H_gens, S_M);
        Stab := SafeGroup(orbit_data.Stab_NH_KH_gens, S_M);
        Add(res.orbits, rec(K := K, hom := fail, Q := fail,
            qsize := orbit_data.qsize, qid := orbit_data.qid,
            Stab := Stab, AutQ := fail, A_gens := [], full_aut := fail,
            H_ref := H));
    od;
    res.byqid := rec();
    for i in [1..Length(res.orbits)] do
        key := String(res.orbits[i].qid);
        if not IsBound(res.byqid.(key)) then res.byqid.(key) := []; fi;
        Add(res.byqid.(key), i);
    od;
    return res;
end;

# Lazily compute hom and Q for an orbit record.  Mutates the record.
# Idempotent: safe to call repeatedly.
EnsureHom := function(orb)
    if orb.hom <> fail then return; fi;
    orb.hom := NaturalHomomorphismByNormalSubgroup(orb.H_ref, orb.K);
    orb.Q := Range(orb.hom);
end;

# Lazily compute AutQ + A_gens for an orbit record.  Mutates the record.
EnsureAutQ := function(orb)
    if orb.AutQ <> fail then return; fi;
    if orb.qsize <= 1 then return; fi;   # trivial Q has no auto
    EnsureHom(orb);   # AutQ depends on Q
    orb.AutQ := AutomorphismGroup(orb.Q);
    orb.A_gens := InducedAutoGens(orb.Stab, orb.H_ref, orb.hom);
    # Optimization (3) 2026-04-28: cache full_aut.
    if Length(orb.A_gens) = 0 then
        orb.full_aut := false;
    else
        orb.full_aut := (Size(Subgroup(orb.AutQ, orb.A_gens)) = Size(orb.AutQ));
    fi;
end;

# ---- block-wreath ambient for normalizer computation ------------------
# An FPF subgroup H of S_M with cycle-type [m_1, m_2, ...] preserves its own
# cycle decomposition, so N_{S_M}(H) is contained in the block-stabilizer
# Stab_S_M(blocks) = direct product over distinct sizes m of (S_m wr S_count(m)).
# For [4,4,4,4] this is S_4 wr S_4 (size 7.96M vs |S_16|=20.9T): ~3 billion
# times smaller search space for Schreier-Sims, with mathematically identical
# normalizer.
BlockWreathFromPartition := function(partition)
    local factors, i, j, m, mult;
    factors := [];
    i := 1;
    while i <= Length(partition) do
        m := partition[i];
        mult := 0;
        j := i;
        while j <= Length(partition) and partition[j] = m do
            mult := mult + 1;
            j := j + 1;
        od;
        if mult = 1 then
            Add(factors, SymmetricGroup(m));
        else
            Add(factors, WreathProduct(SymmetricGroup(m), SymmetricGroup(mult)));
        fi;
        i := j;
    od;
    if Length(factors) = 1 then return factors[1]; fi;
    return DirectProduct(factors);
end;

# ---- q-size-filtered H-cache helpers ----------------------------------
# An H-cache entry stores per-subgroup data needed for Goursat fiber-product
# enumeration: H_gens, N_H_gens (= Normalizer(S_M, H)), and a list of orbit
# records (one per N_H-orbit on { K normal in H : K <> H, |H/K| in filter }).
# `computed_q_sizes` tracks which Q-sizes are populated; lazy/incremental
# extension lets subsequent runs at higher target_n add the larger Q-sizes
# they need without rebuilding from scratch.  Sentinel `fail` = "all sizes".

# Q-iso classes (as group reps) the LEFT cache must cover when consumed
# against a RIGHT factor of degree M_R.  Returns list of GROUPS, or `fail`
# meaning "full coverage" (no filter).
#
# For M_R >= 6: the union of subgroup orders of TG(M_R, *) already spans
# most divisors of typical |H|, so the filter buys little and the cache is
# simpler/faster with `fail` (avoids per-Q GQuotients calls during
# enumeration and skips cache extension on later reads).
RequiredQGroups := function(M_R)
    local result, seen, t, T, K, Q, qid;
    if M_R >= 6 then return fail; fi;
    result := [];
    seen := Set([]);
    if M_R = 0 then return result; fi;
    for t in [1..NrTransitiveGroups(M_R)] do
        T := TransitiveGroup(M_R, t);
        for K in NormalSubgroups(T) do
            if Size(K) = Size(T) then continue; fi;
            Q := T / K;
            qid := SafeId(Q);
            if not (qid in seen) then
                AddSet(seen, qid);
                Add(result, Q);
            fi;
        od;
    od;
    return result;
end;

QIdsOfGroups := function(q_groups)
    if q_groups = fail then return fail; fi;
    return Set(List(q_groups, SafeId));
end;

QGroupsMissing := function(have_ids, want_groups)
    # want_groups = fail means "full coverage needed". have_ids = fail
    # means "already full coverage". Return values:
    #   []   -- nothing missing (no extension needed)
    #   fail -- need full extension (caller should extend to fail)
    #   list -- specific Q-groups to add via tiered enumeration
    if want_groups = fail then
        if have_ids = fail then return []; fi;
        return fail;
    fi;
    if have_ids = fail then return []; fi;
    return Filtered(want_groups, Q -> not (SafeId(Q) in have_ids));
end;

NormalizeHCacheEntry := function(entry)
    if not IsBound(entry.computed_q_ids) then
        entry.computed_q_ids := fail;
    fi;
    return entry;
end;

# TIERED-OPT enumeration: shared per-H setup + |Q| | |H| short-circuit.
# Per H: ONE DerivedSubgroup, ONE abel_hom call.  Per Q:
#   - |Q| ∤ |H|        -> skip (no surjection possible)
#   - prime Q          -> abelianization (cached A, MaximalSubgroupClassReps)
#   - abelian non-prime Q -> GQuotients(A, Q) on the smaller A
#   - non-abelian Q    -> GQuotients(H, Q) on H itself
#
# NormalSubgroups fast path: for H with few normal subgroups (e.g. S_n, A_n
# which have only 3 / 2 normals), enumerate all normals at once and filter
# by quotient iso-class.  This avoids expensive GQuotients(H, S_n) calls.
# Use this path for H that is simple-or-near-simple (NormalSubgroups is
# O(small) regardless of |H|), or for moderately-sized H.  For complex H
# like D_8^4 with thousands of normals, the tiered Q-by-Q path is preferred.
_EnumerateNormalsForQGroups := function(H, q_groups)
    local q_size_H, DH, abel_hom, A, result, Q, sz, p, max_subs, epi,
          qids_set, all_normals, K, qid_K, use_direct;
    if q_groups = fail then
        return Filtered(NormalSubgroups(H), K -> K <> H);
    fi;
    if Length(q_groups) = 0 then return []; fi;
    # Direct NormalSubgroups + Q-id filter is only cheaper than the smart
    # per-Q routing below when the largest Q is too big for GQuotients to
    # finish (|Q| > 200 in practice).  For everything else — and especially
    # for prime Q, where the fast path is just MaximalSubgroupClassReps(A)
    # on the abelianization — fall through to the per-Q routing.  This was
    # gated on |H| <= 10^6 by mistake, which silently sent every typical
    # H (|H|=4096, 1536, 768, ...) through the slow NS path.
    use_direct := Maximum(List(q_groups, Size)) > 200;
    if use_direct then
        qids_set := Set(List(q_groups, SafeId));
        all_normals := Filtered(NormalSubgroups(H), K -> K <> H);
        result := [];
        for K in all_normals do
            qid_K := SafeId(H/K);
            if qid_K in qids_set then Add(result, K); fi;
        od;
        return Set(result);
    fi;
    q_size_H := Size(H);
    DH := DerivedSubgroup(H);
    if Size(DH) = q_size_H then
        abel_hom := fail; A := fail;
    else
        abel_hom := NaturalHomomorphismByNormalSubgroup(H, DH);
        A := Range(abel_hom);
    fi;
    result := [];
    for Q in q_groups do
        sz := Size(Q);
        if q_size_H mod sz <> 0 then continue; fi;
        if IsPrimeInt(sz) then
            if abel_hom = fail then continue; fi;
            if Size(A) mod sz <> 0 then continue; fi;
            p := sz;
            max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = p);
            Append(result, List(max_subs, K -> PreImage(abel_hom, K)));
        elif IsAbelian(Q) then
            if abel_hom = fail then continue; fi;
            for epi in GQuotients(A, Q) do
                Add(result, PreImage(abel_hom, Kernel(epi)));
            od;
        else
            Append(result, Set(List(GQuotients(H, Q), Kernel)));
        fi;
    od;
    return Set(result);
end;

_ComputeOrbitRecsFromKs := function(H, N_H, normals_to_orbit)
    local K_orbit, K_H, hom_H, Q_H, Stab_NH_KH, orbits;
    orbits := [];
    for K_orbit in Orbits(N_H, normals_to_orbit, ConjAction) do
        K_H := K_orbit[1];
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
    return orbits;
end;

ComputeHCacheEntry := function(H, S_M, q_groups)
    local N_H, normals;
    N_H := Normalizer(S_M, H);
    normals := _EnumerateNormalsForQGroups(H, q_groups);
    return rec(
        H_gens := GeneratorsOfGroup(H),
        N_H_gens := GeneratorsOfGroup(N_H),
        computed_q_ids := QIdsOfGroups(q_groups),
        orbits := _ComputeOrbitRecsFromKs(H, N_H, normals)
    );
end;

ExtendHCacheEntry := function(entry, S_M, additional_q_groups)
    local H, N_H, current, missing_groups, normals, new_orbits, all_normals;
    if entry.computed_q_ids = fail then return entry; fi;
    H := SafeGroup(entry.H_gens, S_M);
    N_H := SafeGroup(entry.N_H_gens, S_M);
    current := entry.computed_q_ids;
    if additional_q_groups = fail then
        # Extend to FULL coverage: enumerate ALL normals; add only the K's
        # whose quotient iso-class is not already in current.
        all_normals := Filtered(NormalSubgroups(H), K -> K <> H);
        normals := Filtered(all_normals, K -> not (SafeId(H/K) in current));
        new_orbits := _ComputeOrbitRecsFromKs(H, N_H, normals);
        Append(entry.orbits, new_orbits);
        entry.computed_q_ids := fail;
        return entry;
    fi;
    missing_groups := QGroupsMissing(current, additional_q_groups);
    if Length(missing_groups) = 0 then return entry; fi;
    normals := _EnumerateNormalsForQGroups(H, missing_groups);
    new_orbits := _ComputeOrbitRecsFromKs(H, N_H, normals);
    Append(entry.orbits, new_orbits);
    UniteSet(entry.computed_q_ids, QIdsOfGroups(missing_groups));
    return entry;
end;

SaveHCacheList := function(path, h_cache)
    local tmp;
    # Atomic write: PrintTo to a .tmp file, then `mv` to the final path.
    # Prevents corrupt-cache leftovers if the process is killed mid-write.
    # Unique tmp filename per call: prevents two GAP workers from clobbering
    # each other's PrintTo when racing on the same cache file.
    tmp := Concatenation(path, ".tmp.", String(Runtime()), ".",
                          String(Random([1..1000000])));
    PrintTo(tmp, "H_CACHE := ", h_cache, ";\n");
    Exec(Concatenation("mv -f -- '", tmp, "' '", path, "'"));
end;

# Read last ~200 bytes of a file and check it ends with "];" (the H_CACHE
# closing bracket).  Used as a corruption sentinel: if a previous run was
# killed mid-PrintTo, the file is truncated and won't end with "];".
IsValidCacheFile := function(path)
    local f, content, n, i;
    if not IsExistingFile(path) then return false; fi;
    f := InputTextFile(path);
    if f = fail then return false; fi;
    content := ReadAll(f);
    CloseStream(f);
    n := Length(content);
    if n < 20 then return false; fi;
    # Strip trailing whitespace.
    while n > 0 and content[n] in [' ', '\n', '\r', '\t'] do
        n := n - 1;
    od;
    if n < 2 then return false; fi;
    return content[n-1] = ']' and content[n] = ';';
end;

# ---- Load LEFT side ----
S_ML := SymmetricGroup(ML);
W_ML := BlockWreathFromPartition(LEFT_PARTITION);   # block-wreath ambient
LEFT_Q_GROUPS := RequiredQGroups(MR);
# In holt_split mode, RIGHT subgroups are non-transitive subdirect products
# whose quotient iso-classes are NOT covered by RequiredQGroups(MR)
# (which only iterates TG(MR, *) quotients).  E.g., A_4 x A_4 has [9,2]
# = C_3 x C_3 quotient, but no transitive group on 8 points has this quotient.
# Augment LEFT_Q_GROUPS with each RIGHT subgroup's quotient iso-classes
# so that LEFT enumerates K's matching all reachable common Q-iso classes.
# Skip augmentation if LEFT_Q_GROUPS = fail (= already full coverage).
if SUBS_RIGHT_PATH <> "" and LEFT_Q_GROUPS <> fail then
    seen_qid := Set(List(LEFT_Q_GROUPS, SafeId));
    Read(SUBS_RIGHT_PATH);
    SUBGROUPS_RIGHT_RAW := SUBGROUPS;
    for R in SUBGROUPS_RIGHT_RAW do
        for K in NormalSubgroups(R) do
            if Size(K) = Size(R) then continue; fi;
            Q := R/K;
            qid := SafeId(Q);
            if not (qid in seen_qid) then
                AddSet(seen_qid, qid);
                Add(LEFT_Q_GROUPS, Q);
            fi;
        od;
    od;
fi;
if LEFT_Q_GROUPS = fail then
    Print("LEFT Q-groups: full coverage (M_R=", MR, ")\n");
else
    Print("LEFT Q-groups for M_R=", MR, ": ", Length(LEFT_Q_GROUPS),
          " types, max |Q|=",
          Maximum(Concatenation([0], List(LEFT_Q_GROUPS, Size))), "\n");
fi;
Print("LEFT block-wreath W_ML order=", Size(W_ML), " (vs |S_ML|=", Factorial(ML), ")\n");
H_CACHE := fail;
if CACHE_LEFT_PATH <> "" and IsValidCacheFile(CACHE_LEFT_PATH) then
    Read(CACHE_LEFT_PATH);
fi;
if H_CACHE <> fail then
    # Backward compat + check if cached coverage is sufficient
    for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
    extend_needed := false;
    for hi in [1..Length(H_CACHE)] do
        missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
        if missing = fail or Length(missing) > 0 then
            extend_needed := true;
        fi;
    od;
    if extend_needed then
        Print("extending H_CACHE for new Q-sizes...\n");
        for hi in [1..Length(H_CACHE)] do
            missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
            if missing = fail then
                ExtendHCacheEntry(H_CACHE[hi], W_ML, fail);
            elif Length(missing) > 0 then
                ExtendHCacheEntry(H_CACHE[hi], W_ML, missing);
            fi;
        od;
        if CACHE_LEFT_PATH <> "" then
            SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
        fi;
    fi;
fi;
if H_CACHE = fail then
    Read(SUBS_LEFT_PATH);
    SUBGROUPS_LEFT_RAW := SUBGROUPS;
    Print("computing left H_CACHE for ", Length(SUBGROUPS_LEFT_RAW), " subgroups (in W_ML)...\n");
    last_hb := Runtime();
    last_hb_count := 0;
    H_CACHE := [];
    for hi in [1..Length(SUBGROUPS_LEFT_RAW)] do
        if hi = 1 or hi - last_hb_count >= 500
           or Runtime() - last_hb >= 60000 then
            Print("  H_CACHE starting ", hi, "/", Length(SUBGROUPS_LEFT_RAW),
                  " |H|=", Size(SUBGROUPS_LEFT_RAW[hi]), "\n");
            last_hb := Runtime();
            last_hb_count := hi;
        fi;
        Add(H_CACHE, ComputeHCacheEntry(SUBGROUPS_LEFT_RAW[hi], W_ML, LEFT_Q_GROUPS));
    od;
    if CACHE_LEFT_PATH <> "" then
        SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
    fi;
fi;
H_CACHE_L := H_CACHE;
Print("LEFT: ", Length(H_CACHE_L), " entries\n");

# ---- Load RIGHT side ----
S_MR := SymmetricGroup(MR);
H_CACHE_R := fail;
# RIGHT side: |T_RIGHT| is small (typically <=720 even for S_6), so always
# compute the full Q-spectrum.  No q-size filter needed here.
if RIGHT_TG_D > 0 then
    T_orig := TransitiveGroup(RIGHT_TG_D, RIGHT_TG_T);
    H_CACHE_R := [ComputeHCacheEntry(T_orig, S_MR, fail)];
    Print("RIGHT: TG(", RIGHT_TG_D, ",", RIGHT_TG_T, ") on [1..", MR, "]\n");
else
    H_CACHE := fail;
    if CACHE_RIGHT_PATH <> "" and IsValidCacheFile(CACHE_RIGHT_PATH) then
        Read(CACHE_RIGHT_PATH);
        for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
        # Extend RIGHT cache to cover LEFT_Q_GROUPS.  RIGHT side needs orbit
        # data for every Q-iso-class that LEFT may enumerate (otherwise
        # H2data.byqid lookups miss for those qids -> undercounting).
        extend_needed := false;
        for hi in [1..Length(H_CACHE)] do
            missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
            if missing = fail or Length(missing) > 0 then
                extend_needed := true;
            fi;
        od;
        if extend_needed then
            Print("extending RIGHT H_CACHE for new Q-types...\n");
            for hi in [1..Length(H_CACHE)] do
                missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
                if missing = fail then
                    ExtendHCacheEntry(H_CACHE[hi], S_MR, fail);
                elif Length(missing) > 0 then
                    ExtendHCacheEntry(H_CACHE[hi], S_MR, LEFT_Q_GROUPS);
                fi;
            od;
            if CACHE_RIGHT_PATH <> "" then
                SaveHCacheList(CACHE_RIGHT_PATH, H_CACHE);
            fi;
        fi;
    fi;
    if H_CACHE = fail then
        Read(SUBS_RIGHT_PATH);
        SUBGROUPS_RIGHT_RAW := SUBGROUPS;
        Print("computing right H_CACHE for ", Length(SUBGROUPS_RIGHT_RAW), " subgroups...\n");
        H_CACHE := List(SUBGROUPS_RIGHT_RAW, H -> ComputeHCacheEntry(H, S_MR, LEFT_Q_GROUPS));
        if CACHE_RIGHT_PATH <> "" then
            SaveHCacheList(CACHE_RIGHT_PATH, H_CACHE);
        fi;
    fi;
    H_CACHE_R := H_CACHE;
    Print("RIGHT: ", Length(H_CACHE_R), " entries\n");
fi;

# Reconstruct full data on the right side once.
H2DATA := List(H_CACHE_R, e -> ReconstructHData(e, S_MR));

# ---- 2-block Goursat with optional Burnside swap-fix and generator output ----
# Right-side acts on points [ML+1..ML+MR] when materialized.  For pure
# Burnside m=2, both sides have the same structure (TG(d,t)) but on different
# point sets; the swap maps the (K_H_a, K_T_b)-orbit at left.a == right.b
# (= same K-subgroup) to its inverse-iso at the swap.
shift_R := MappingPermListList([1..MR], [ML+1..ML+MR]);

# Open raw-generators temp file (truncate).  Final file with legacy header
# (# combo / # candidates / # deduped / # elapsed_ms) is composed in Python
# after GAP returns.
GEN_FILE_OPEN := false;
if EMIT_GENS_PATH <> "" then
    PrintTo(EMIT_GENS_PATH, "");
    GEN_FILE_OPEN := true;
fi;

# In burnside_m2 mode, ordered-pair iteration would emit both (a,b) and (b,a).
# We avoid post-hoc swap-dedup (fragile under GAP `=` on freshly-built Groups);
# instead, ProcessPair is responsible for emitting only canonical iterations
# (h2idx >= h1_orb_idx, plus within-self-pair canonical via swap_orb_id).
# EmitGenerators is now a pure write — no dedup logic.
EmitGenerators := function(F)
    local gens, s;
    if not GEN_FILE_OPEN then return; fi;
    gens := GeneratorsOfGroup(F);
    if Length(gens) > 0 then
        s := JoinStringsWithSeparator(List(gens, String), ",");
    else
        s := "";
    fi;
    AppendTo(EMIT_GENS_PATH, "[", s, "]\n");
end;

# Build fiber product when emitting generators or doing Burnside swap-fix.
# Right-side group needs to be on [ML+1..ML+MR].
ShiftToRight := function(H) return H^shift_R; end;

# 2-block Goursat counter.
# If EMIT_GENS_PATH: also build fp via _GoursatBuildFiberProduct.
# If BURNSIDE_M2 = 1: track swap-fix orbits separately.
# Returns rec(orbits := total, swap_fixed := count).
ProcessPair := function(H1data, H2data, H2_idx_in_R)
    local total, swap_fixed, h1orb, h2idxs, h2idx, h2orb, key, isoTH,
          iso_count, isos, gensQ, KeyOf, idx, seen, n_orb, queue, j, phi,
          alpha, beta, neighbor, nkey, k, fp, orbit_id, i, swap_phi,
          swap_key, swap_iso_idx, swap_orbit_id, h1, h2, H1, H2, n,
          h1_orb_idx, kh_a_eq_kt_b, gens_for_fp, orbit_reps_phi, h_0, t_0,
          swap_orb_id_arr,
          dcs, A1, A2_in_h1, A2_in_h1_gens, tinv, g_swap;

    H1 := H1data.H;
    H2 := ShiftToRight(H2data.H);   # only used if EMIT_GENS or BURNSIDE_M2

    total := 0;
    swap_fixed := 0;

    # Trivial-Q baseline: 1 orbit per (H1, H2) pair (direct product).
    # (encoded via the qsize=1 entry in each orbits list)

    for h1_orb_idx in [1..Length(H1data.orbits)] do
        h1orb := H1data.orbits[h1_orb_idx];
        key := String(h1orb.qid);
        if not IsBound(H2data.byqid.(key)) then continue; fi;
        h2idxs := H2data.byqid.(key);

        # Trivial-Q (qsize = 1): direct product H1 x H2.
        # Canonical-emission gate: in burnside_m2, only emit when
        # h2idx >= h1_orb_idx (one rep per unordered orbit-pair).
        if h1orb.qsize = 1 then
            for h2idx in h2idxs do
                h2orb := H2data.orbits[h2idx];
                if h2orb.qsize = 1 then
                    total := total + 1;
                    if GEN_FILE_OPEN and (BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx) then
                        fp := Group(Concatenation(GeneratorsOfGroup(H1),
                                                  GeneratorsOfGroup(H2)));
                        EmitGenerators(fp);
                    fi;
                    if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                        swap_fixed := swap_fixed + 1;
                    fi;
                fi;
            od;
            continue;
        fi;

        # |Q| = 2 fast path: |Aut(C_2)|=1 so direct <K1, K2^shift, h_0*t_0^shift>
        # construction works for ANY MR.  Optimization (2) 2026-04-28: generalized
        # from MR=2-only to all MR.
        if h1orb.qsize = 2 then
            for h2idx in h2idxs do
                if H2data.orbits[h2idx].qsize <> 2 then continue; fi;
                total := total + 1;
                h2orb := H2data.orbits[h2idx];
                if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                    if GEN_FILE_OPEN then
                        h_0 := First(GeneratorsOfGroup(H1),
                                     g -> not (g in h1orb.K));
                        t_0 := First(GeneratorsOfGroup(H2data.H),
                                     g -> not (g in h2orb.K));
                        fp := Group(Concatenation(
                            Filtered(GeneratorsOfGroup(h1orb.K), g -> g <> ()),
                            List(Filtered(GeneratorsOfGroup(h2orb.K),
                                          g -> g <> ()),
                                 g -> g^shift_R),
                            [h_0 * t_0^shift_R]));
                        EmitGenerators(fp);
                    fi;
                fi;
                if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                    swap_fixed := swap_fixed + 1;
                fi;
            od;
            continue;
        fi;

        # General path: BFS over Aut(Q)-orbits.
        for h2idx in h2idxs do
            h2orb := H2data.orbits[h2idx];
            if h2orb.qsize <> h1orb.qsize then continue; fi;
            EnsureHom(h1orb); EnsureHom(h2orb);
            isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
            if isoTH = fail then continue; fi;
            # Optimization (5) 2026-04-29: lazy h1.AutQ.  h2 is the RIGHT
            # factor and is pre-warmed at startup; for high-symmetry RIGHTs
            # (e.g. V_4 where N_{S_4}(V_4)/V_4 = S_3 = Aut), h2 saturates
            # for every orbit and forces n_orb=1.  Test h2 first; only build
            # h1.AutQ when h2 does NOT saturate.  ~2.5x on V_4-right combos.
            EnsureAutQ(h2orb);
            if h2orb.full_aut <> true then EnsureAutQ(h1orb); fi;

            # Optimization (1)+(3) 2026-04-28: early Aut-saturation shortcut
            # using cached full_aut flag.  Skip building isos+idx+KeyOf for
            # the saturated case (the common case for high-symmetry RIGHTs).
            if h1orb.full_aut = true or h2orb.full_aut = true then
                n_orb := 1;
                orbit_reps_phi := [isoTH];
                dcs := [];   # placeholder; not used in saturated branch
            else
                # Optimization (6) 2026-04-29: DoubleCosets replaces BFS.
                # Parametrize iso phi: h2.Q -> h1.Q as phi = α' o isoTH (standard
                # math composition), α' in Aut(h1.Q).  The action α o phi o β^-1
                # (α in A1 = <h1.A_gens>, β in A2 = <h2.A_gens>) becomes
                # α' -> α α' β'^-1 with β' = isoTH o β o isoTH^-1 in Aut(h1.Q).
                # Orbits = double cosets A1 \ Aut(h1.Q) / A2_in_h1.
                # Bench-validated 5.4x avg, 22-68x on |Aut|>=1152 buckets, 0
                # mismatches across 21,647 verified pairs.
                A1 := SafeSub(h1orb.AutQ, h1orb.A_gens);
                A2_in_h1_gens := List(h2orb.A_gens,
                    b -> InverseGeneralMapping(isoTH) * b * isoTH);
                A2_in_h1 := SafeSub(h1orb.AutQ, A2_in_h1_gens);
                dcs := DoubleCosets(h1orb.AutQ, A1, A2_in_h1);
                n_orb := Length(dcs);
                # GAP composition: f * g = "apply f first, then g" = standard g o f.
                # Orbit rep phi_i = standard Rep(dcs[i]) o isoTH = GAP isoTH * Rep(dcs[i]).
                orbit_reps_phi := List(dcs, dc -> isoTH * Representative(dc));
            fi;
            total := total + n_orb;

            # Compute swap-orbit-id per orbit rep (used for both within-self-pair
            # canonical emission gate and swap_fixed counter).
            swap_orb_id_arr := ListWithIdenticalEntries(n_orb, -1);
            if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                if h1orb.full_aut = true or h2orb.full_aut = true then
                    # Optimization (1) shortcut: 1 orbit, trivially swap-fixed.
                    swap_orb_id_arr[1] := 1;
                else
                    # Find which double coset contains the swap of each orbit rep.
                    # phi_i^-1 = standard isoTH^-1 o Rep(dcs[i])^-1.  In α'-coords
                    # (where phi = α' o isoTH) this is α'' = isoTH^-1 o Rep(dcs[i])^-1
                    # o isoTH^-1.  In GAP composition: tinv * Rep^-1 * tinv.
                    tinv := InverseGeneralMapping(isoTH);
                    gensQ := GeneratorsOfGroup(h1orb.Q);
                    for i in [1..n_orb] do
                        # g_swap is initially a CompositionMapping which
                        # DoubleCoset.in does not recognize as an h1.AutQ
                        # element.  Reify it as GroupHomomorphismByImagesNC
                        # by evaluating on Q's generators.
                        g_swap := tinv * InverseGeneralMapping(Representative(dcs[i])) * tinv;
                        g_swap := GroupHomomorphismByImagesNC(h1orb.Q, h1orb.Q,
                            gensQ, List(gensQ, q -> Image(g_swap, q)));
                        SetIsBijective(g_swap, true);
                        swap_orb_id_arr[i] :=
                            PositionProperty(dcs, dc -> g_swap in dc);
                    od;
                fi;
            fi;

            # Generator emission per orbit rep, canonical-gated.
            if GEN_FILE_OPEN then
                if BURNSIDE_M2 = 0 or h2idx > h1_orb_idx then
                    # Non-self canonical: emit all orbit reps.
                    for i in [1..n_orb] do
                        fp := _GoursatBuildFiberProduct(
                            H1, H2,
                            h1orb.hom,
                            CompositionMapping(h2orb.hom,
                                ConjugatorIsomorphism(H2, shift_R^-1)),
                            InverseGeneralMapping(orbit_reps_phi[i]),
                            [1..ML], [ML+1..ML+MR]);
                        if fp <> fail then EmitGenerators(fp); fi;
                    od;
                elif BURNSIDE_M2 = 1 and h2idx = h1_orb_idx then
                    # Self-pair: within-pair canonical (i <= swap_orb_id[i]).
                    for i in [1..n_orb] do
                        if swap_orb_id_arr[i] >= i then
                            fp := _GoursatBuildFiberProduct(
                                H1, H2,
                                h1orb.hom,
                                CompositionMapping(h2orb.hom,
                                    ConjugatorIsomorphism(H2, shift_R^-1)),
                                InverseGeneralMapping(orbit_reps_phi[i]),
                                [1..ML], [ML+1..ML+MR]);
                            if fp <> fail then EmitGenerators(fp); fi;
                        fi;
                    od;
                fi;
            fi;

            # Burnside m=2 swap-fix counting (self-pair only).
            if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                for i in [1..n_orb] do
                    if swap_orb_id_arr[i] = i then
                        swap_fixed := swap_fixed + 1;
                    fi;
                od;
            fi;
        od;
    od;
    return rec(orbits := total, swap_fixed := swap_fixed);
end;

# Main loop.
TOTAL_ORB := 0;
TOTAL_FIX := 0;
t0 := Runtime();
n_left := Length(H_CACHE_L);
for i in [1..n_left] do
    H1data := ReconstructHData(H_CACHE_L[i], S_ML);
    # In burnside_m2 mode, LEFT and RIGHT are the same atom but constructed
    # via different code paths (source file vs TransitiveGroup), giving
    # different GAP group objects with mismatched families. The swap-fix
    # counting requires h1orb.Q and h2orb.Q to share families. Override
    # H2DATA[1] with H1data so they reference the same group objects.
    # (For burnside_m2 atoms, H_CACHE_R has exactly one entry and n_left = 1.)
    if BURNSIDE_M2 = 1 then
        H2DATA[1] := H1data;
    fi;
    for j in [1..Length(H2DATA)] do
        res_pair := ProcessPair(H1data, H2DATA[j], j);
        TOTAL_ORB := TOTAL_ORB + res_pair.orbits;
        TOTAL_FIX := TOTAL_FIX + res_pair.swap_fixed;
    od;
od;

if BURNSIDE_M2 = 1 then
    PREDICTED := (TOTAL_ORB + TOTAL_FIX) / 2;
else
    PREDICTED := TOTAL_ORB;
fi;

Print("RESULT predicted=", PREDICTED,
      " orbits=", TOTAL_ORB,
      " swap_fixed=", TOTAL_FIX,
      " elapsed_ms=", Runtime() - t0, "\n");
LogTo();
QUIT;
"""


# ---------------------------------------------------------------------------
# Batched GAP driver: load LEFT once, iterate jobs all sharing that LEFT.
# Each job has its own RIGHT side (TG or source file) and writes its own
# legacy-format output file (composed by GAP via SizeScreen wide enough to
# avoid line wraps).
# ---------------------------------------------------------------------------
BATCH_DRIVER = r"""
LogTo("__LOG__");
SizeScreen([100000, 24]);   # disable line wrapping in output

# Path to lifting_algorithm.g for _GoursatBuildFiberProduct.
if not IsBound(_GoursatBuildFiberProduct) then Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g"); fi;

# Common helpers (same as GAP_DRIVER).
ConjAction := function(K, g) return K^g; end;

SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

InducedAutoGens := function(stab, G, hom)
    return List(GeneratorsOfGroup(stab),
        s -> InducedAutomorphism(hom, ConjugatorAutomorphism(G, s)));
end;

SafeGroup := function(gens, default_amb)
    if Length(gens) = 0 then return TrivialSubgroup(default_amb); fi;
    return Group(gens);
end;

SafeSub := function(G, gens)
    if Length(gens) = 0 then return TrivialSubgroup(G); fi;
    return Subgroup(G, gens);
end;

ReconstructHData := function(entry, S_M)
    local H, N, res, orbit_data, K, Stab, i, key, hom_triv;
    H := SafeGroup(entry.H_gens, S_M);
    N := SafeGroup(entry.N_H_gens, S_M);
    res := rec(H := H, N := N, orbits := []);
    # Trivial-quotient orbit (always present; hom is fast for H/H).
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N, AutQ := fail, A_gens := [], full_aut := fail,
        H_ref := H));
    # Non-trivial orbits: hom and Q are deferred (computed lazily by EnsureHom).
    # NaturalHomomorphismByNormalSubgroup is the dominant cost for large H,
    # and most orbits never get paired against a matching RIGHT qid, so
    # deferring it is the dominant speed win.
    for orbit_data in entry.orbits do
        K := SafeGroup(orbit_data.K_H_gens, S_M);
        Stab := SafeGroup(orbit_data.Stab_NH_KH_gens, S_M);
        Add(res.orbits, rec(K := K, hom := fail, Q := fail,
            qsize := orbit_data.qsize, qid := orbit_data.qid,
            Stab := Stab, AutQ := fail, A_gens := [], full_aut := fail,
            H_ref := H));
    od;
    res.byqid := rec();
    for i in [1..Length(res.orbits)] do
        key := String(res.orbits[i].qid);
        if not IsBound(res.byqid.(key)) then res.byqid.(key) := []; fi;
        Add(res.byqid.(key), i);
    od;
    return res;
end;

# Lazily compute hom and Q for an orbit record.  Mutates the record.
# Idempotent: safe to call repeatedly.
EnsureHom := function(orb)
    if orb.hom <> fail then return; fi;
    orb.hom := NaturalHomomorphismByNormalSubgroup(orb.H_ref, orb.K);
    orb.Q := Range(orb.hom);
end;

# Lazily compute AutQ + A_gens for an orbit record.  Mutates the record.
EnsureAutQ := function(orb)
    if orb.AutQ <> fail then return; fi;
    if orb.qsize <= 1 then return; fi;   # trivial Q has no auto
    EnsureHom(orb);   # AutQ depends on Q
    orb.AutQ := AutomorphismGroup(orb.Q);
    orb.A_gens := InducedAutoGens(orb.Stab, orb.H_ref, orb.hom);
    # Optimization (3) 2026-04-28: cache full_aut.
    if Length(orb.A_gens) = 0 then
        orb.full_aut := false;
    else
        orb.full_aut := (Size(Subgroup(orb.AutQ, orb.A_gens)) = Size(orb.AutQ));
    fi;
end;

# ---- block-wreath ambient for normalizer computation ------------------
# An FPF subgroup H of S_M with cycle-type [m_1, m_2, ...] preserves its own
# cycle decomposition, so N_{S_M}(H) is contained in the block-stabilizer
# Stab_S_M(blocks) = direct product over distinct sizes m of (S_m wr S_count(m)).
# For [4,4,4,4] this is S_4 wr S_4 (size 7.96M vs |S_16|=20.9T): ~3 billion
# times smaller search space for Schreier-Sims, with mathematically identical
# normalizer.
BlockWreathFromPartition := function(partition)
    local factors, i, j, m, mult;
    factors := [];
    i := 1;
    while i <= Length(partition) do
        m := partition[i];
        mult := 0;
        j := i;
        while j <= Length(partition) and partition[j] = m do
            mult := mult + 1;
            j := j + 1;
        od;
        if mult = 1 then
            Add(factors, SymmetricGroup(m));
        else
            Add(factors, WreathProduct(SymmetricGroup(m), SymmetricGroup(mult)));
        fi;
        i := j;
    od;
    if Length(factors) = 1 then return factors[1]; fi;
    return DirectProduct(factors);
end;

# ---- q-size-filtered H-cache helpers ----------------------------------
# An H-cache entry stores per-subgroup data needed for Goursat fiber-product
# enumeration: H_gens, N_H_gens (= Normalizer(S_M, H)), and a list of orbit
# records (one per N_H-orbit on { K normal in H : K <> H, |H/K| in filter }).
# `computed_q_sizes` tracks which Q-sizes are populated; lazy/incremental
# extension lets subsequent runs at higher target_n add the larger Q-sizes
# they need without rebuilding from scratch.  Sentinel `fail` = "all sizes".

# Q-iso classes (as group reps) the LEFT cache must cover when consumed
# against a RIGHT factor of degree M_R.  Returns list of GROUPS, or `fail`
# meaning "full coverage" (no filter).
#
# For M_R >= 6: the union of subgroup orders of TG(M_R, *) already spans
# most divisors of typical |H|, so the filter buys little and the cache is
# simpler/faster with `fail` (avoids per-Q GQuotients calls during
# enumeration and skips cache extension on later reads).
RequiredQGroups := function(M_R)
    local result, seen, t, T, K, Q, qid;
    if M_R >= 6 then return fail; fi;
    result := [];
    seen := Set([]);
    if M_R = 0 then return result; fi;
    for t in [1..NrTransitiveGroups(M_R)] do
        T := TransitiveGroup(M_R, t);
        for K in NormalSubgroups(T) do
            if Size(K) = Size(T) then continue; fi;
            Q := T / K;
            qid := SafeId(Q);
            if not (qid in seen) then
                AddSet(seen, qid);
                Add(result, Q);
            fi;
        od;
    od;
    return result;
end;

QIdsOfGroups := function(q_groups)
    if q_groups = fail then return fail; fi;
    return Set(List(q_groups, SafeId));
end;

QGroupsMissing := function(have_ids, want_groups)
    # want_groups = fail means "full coverage needed". have_ids = fail
    # means "already full coverage". Return values:
    #   []   -- nothing missing (no extension needed)
    #   fail -- need full extension (caller should extend to fail)
    #   list -- specific Q-groups to add via tiered enumeration
    if want_groups = fail then
        if have_ids = fail then return []; fi;
        return fail;
    fi;
    if have_ids = fail then return []; fi;
    return Filtered(want_groups, Q -> not (SafeId(Q) in have_ids));
end;

NormalizeHCacheEntry := function(entry)
    if not IsBound(entry.computed_q_ids) then
        entry.computed_q_ids := fail;
    fi;
    return entry;
end;

# TIERED-OPT enumeration: shared per-H setup + |Q| | |H| short-circuit.
# Per H: ONE DerivedSubgroup, ONE abel_hom call.  Per Q:
#   - |Q| ∤ |H|        -> skip (no surjection possible)
#   - prime Q          -> abelianization (cached A, MaximalSubgroupClassReps)
#   - abelian non-prime Q -> GQuotients(A, Q) on the smaller A
#   - non-abelian Q    -> GQuotients(H, Q) on H itself
#
# NormalSubgroups fast path: for H with few normal subgroups (e.g. S_n, A_n
# which have only 3 / 2 normals), enumerate all normals at once and filter
# by quotient iso-class.  This avoids expensive GQuotients(H, S_n) calls.
# Use this path for H that is simple-or-near-simple (NormalSubgroups is
# O(small) regardless of |H|), or for moderately-sized H.  For complex H
# like D_8^4 with thousands of normals, the tiered Q-by-Q path is preferred.
_EnumerateNormalsForQGroups := function(H, q_groups)
    local q_size_H, DH, abel_hom, A, result, Q, sz, p, max_subs, epi,
          qids_set, all_normals, K, qid_K, use_direct;
    if q_groups = fail then
        return Filtered(NormalSubgroups(H), K -> K <> H);
    fi;
    if Length(q_groups) = 0 then return []; fi;
    # Direct NormalSubgroups + Q-id filter is only cheaper than the smart
    # per-Q routing below when the largest Q is too big for GQuotients to
    # finish (|Q| > 200 in practice).  For everything else — and especially
    # for prime Q, where the fast path is just MaximalSubgroupClassReps(A)
    # on the abelianization — fall through to the per-Q routing.  This was
    # gated on |H| <= 10^6 by mistake, which silently sent every typical
    # H (|H|=4096, 1536, 768, ...) through the slow NS path.
    use_direct := Maximum(List(q_groups, Size)) > 200;
    if use_direct then
        qids_set := Set(List(q_groups, SafeId));
        all_normals := Filtered(NormalSubgroups(H), K -> K <> H);
        result := [];
        for K in all_normals do
            qid_K := SafeId(H/K);
            if qid_K in qids_set then Add(result, K); fi;
        od;
        return Set(result);
    fi;
    q_size_H := Size(H);
    DH := DerivedSubgroup(H);
    if Size(DH) = q_size_H then
        abel_hom := fail; A := fail;
    else
        abel_hom := NaturalHomomorphismByNormalSubgroup(H, DH);
        A := Range(abel_hom);
    fi;
    result := [];
    for Q in q_groups do
        sz := Size(Q);
        if q_size_H mod sz <> 0 then continue; fi;
        if IsPrimeInt(sz) then
            if abel_hom = fail then continue; fi;
            if Size(A) mod sz <> 0 then continue; fi;
            p := sz;
            max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = p);
            Append(result, List(max_subs, K -> PreImage(abel_hom, K)));
        elif IsAbelian(Q) then
            if abel_hom = fail then continue; fi;
            for epi in GQuotients(A, Q) do
                Add(result, PreImage(abel_hom, Kernel(epi)));
            od;
        else
            Append(result, Set(List(GQuotients(H, Q), Kernel)));
        fi;
    od;
    return Set(result);
end;

_ComputeOrbitRecsFromKs := function(H, N_H, normals_to_orbit)
    local K_orbit, K_H, hom_H, Q_H, Stab_NH_KH, orbits;
    orbits := [];
    for K_orbit in Orbits(N_H, normals_to_orbit, ConjAction) do
        K_H := K_orbit[1];
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
    return orbits;
end;

ComputeHCacheEntry := function(H, S_M, q_groups)
    local N_H, normals;
    N_H := Normalizer(S_M, H);
    normals := _EnumerateNormalsForQGroups(H, q_groups);
    return rec(
        H_gens := GeneratorsOfGroup(H),
        N_H_gens := GeneratorsOfGroup(N_H),
        computed_q_ids := QIdsOfGroups(q_groups),
        orbits := _ComputeOrbitRecsFromKs(H, N_H, normals)
    );
end;

ExtendHCacheEntry := function(entry, S_M, additional_q_groups)
    local H, N_H, current, missing_groups, normals, new_orbits, all_normals;
    if entry.computed_q_ids = fail then return entry; fi;
    H := SafeGroup(entry.H_gens, S_M);
    N_H := SafeGroup(entry.N_H_gens, S_M);
    current := entry.computed_q_ids;
    if additional_q_groups = fail then
        # Extend to FULL coverage: enumerate ALL normals; add only the K's
        # whose quotient iso-class is not already in current.
        all_normals := Filtered(NormalSubgroups(H), K -> K <> H);
        normals := Filtered(all_normals, K -> not (SafeId(H/K) in current));
        new_orbits := _ComputeOrbitRecsFromKs(H, N_H, normals);
        Append(entry.orbits, new_orbits);
        entry.computed_q_ids := fail;
        return entry;
    fi;
    missing_groups := QGroupsMissing(current, additional_q_groups);
    if Length(missing_groups) = 0 then return entry; fi;
    normals := _EnumerateNormalsForQGroups(H, missing_groups);
    new_orbits := _ComputeOrbitRecsFromKs(H, N_H, normals);
    Append(entry.orbits, new_orbits);
    UniteSet(entry.computed_q_ids, QIdsOfGroups(missing_groups));
    return entry;
end;

SaveHCacheList := function(path, h_cache)
    local tmp;
    # Atomic write: PrintTo to a .tmp file, then `mv` to the final path.
    # Prevents corrupt-cache leftovers if the process is killed mid-write.
    # Unique tmp filename per call: prevents two GAP workers from clobbering
    # each other's PrintTo when racing on the same cache file.
    tmp := Concatenation(path, ".tmp.", String(Runtime()), ".",
                          String(Random([1..1000000])));
    PrintTo(tmp, "H_CACHE := ", h_cache, ";\n");
    Exec(Concatenation("mv -f -- '", tmp, "' '", path, "'"));
end;

# Read last ~200 bytes of a file and check it ends with "];" (the H_CACHE
# closing bracket).  Used as a corruption sentinel: if a previous run was
# killed mid-PrintTo, the file is truncated and won't end with "];".
IsValidCacheFile := function(path)
    local f, content, n, i;
    if not IsExistingFile(path) then return false; fi;
    f := InputTextFile(path);
    if f = fail then return false; fi;
    content := ReadAll(f);
    CloseStream(f);
    n := Length(content);
    if n < 20 then return false; fi;
    # Strip trailing whitespace.
    while n > 0 and content[n] in [' ', '\n', '\r', '\t'] do
        n := n - 1;
    od;
    if n < 2 then return false; fi;
    return content[n-1] = ']' and content[n] = ';';
end;

# ---- Load LEFT side (shared across all jobs in this batch) ----
ML := __M_LEFT__;
LEFT_PARTITION := __M_LEFT_PARTITION__;
SUBS_LEFT_PATH  := "__SUBS_L__";
CACHE_LEFT_PATH := "__CACHE_L__";

# Load JOBS array first so we can compute the LEFT q-size filter from the
# union of m_right's across all jobs in this batch.
JOBS := __JOBS_ARRAY__;

S_ML := SymmetricGroup(ML);
W_ML := BlockWreathFromPartition(LEFT_PARTITION);
batch_t0 := Runtime();

LEFT_Q_GROUPS := [];
seen_qids := Set([]);
for job_idx in [1..Length(JOBS)] do
    rq := RequiredQGroups(JOBS[job_idx].m_right);
    if rq = fail then
        # Any job with M_R >= 6 forces full coverage for the whole batch.
        LEFT_Q_GROUPS := fail;
        break;
    fi;
    for Q in rq do
        if not (SafeId(Q) in seen_qids) then
            AddSet(seen_qids, SafeId(Q));
            Add(LEFT_Q_GROUPS, Q);
        fi;
    od;
od;
# Holt-split augmentation: also union in Q-iso classes from each RIGHT
# source's subgroups (RIGHTs that aren't TG factors).  RequiredQGroups(MR)
# only covers TG(MR) quotients, but holt_split RIGHTs are non-transitive
# subdirect products with quotient iso-classes outside that universe.
# Skip augmentation if LEFT_Q_GROUPS = fail (full coverage already).
if LEFT_Q_GROUPS <> fail then
    seen_subs_paths := Set([]);
    for job_idx in [1..Length(JOBS)] do
        if JOBS[job_idx].subs_right <> "" and
           not (JOBS[job_idx].subs_right in seen_subs_paths) then
            AddSet(seen_subs_paths, JOBS[job_idx].subs_right);
            Read(JOBS[job_idx].subs_right);
            for R in SUBGROUPS do
                for K in NormalSubgroups(R) do
                    if Size(K) = Size(R) then continue; fi;
                    Q := R/K;
                    qid := SafeId(Q);
                    if not (qid in seen_qids) then
                        AddSet(seen_qids, qid);
                        Add(LEFT_Q_GROUPS, Q);
                    fi;
                od;
            od;
        fi;
    od;
fi;
if LEFT_Q_GROUPS = fail then
    Print("[t+", Runtime() - batch_t0, "ms] LEFT Q-groups: full coverage\n");
else
    Print("[t+", Runtime() - batch_t0, "ms] LEFT Q-groups: ",
          Length(LEFT_Q_GROUPS), " types, max |Q|=",
          Maximum(Concatenation([0], List(LEFT_Q_GROUPS, Size))), "\n");
fi;

H_CACHE := fail;
if CACHE_LEFT_PATH <> "" and IsValidCacheFile(CACHE_LEFT_PATH) then
    Print("[t+", Runtime() - batch_t0, "ms] reading H_CACHE from disk: ",
          CACHE_LEFT_PATH, "\n");
    Read(CACHE_LEFT_PATH);
    Print("[t+", Runtime() - batch_t0, "ms] H_CACHE read complete: ",
          Length(H_CACHE), " entries\n");
fi;
if H_CACHE <> fail then
    for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
    extend_needed := false;
    for hi in [1..Length(H_CACHE)] do
        missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
        if missing = fail or Length(missing) > 0 then
            extend_needed := true;
        fi;
    od;
    if extend_needed then
        Print("[t+", Runtime() - batch_t0,
              "ms] extending H_CACHE for new Q-sizes...\n");
        for hi in [1..Length(H_CACHE)] do
            missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
            if missing = fail then
                ExtendHCacheEntry(H_CACHE[hi], W_ML, fail);
            elif Length(missing) > 0 then
                ExtendHCacheEntry(H_CACHE[hi], W_ML, missing);
            fi;
        od;
        if CACHE_LEFT_PATH <> "" then
            SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
        fi;
        Print("[t+", Runtime() - batch_t0, "ms] extension done\n");
    fi;
fi;
if H_CACHE = fail then
    Print("[t+", Runtime() - batch_t0, "ms] no cache; reading subs\n");
    Read(SUBS_LEFT_PATH);
    SUBGROUPS_LEFT_RAW := SUBGROUPS;
    Print("[t+", Runtime() - batch_t0, "ms] computing left H_CACHE for ",
          Length(SUBGROUPS_LEFT_RAW), " subgroups (in W_ML)...\n");
    last_hb := Runtime();
    last_hb_count := 0;
    H_CACHE := [];
    for hi in [1..Length(SUBGROUPS_LEFT_RAW)] do
        if hi = 1 or hi - last_hb_count >= 500
           or Runtime() - last_hb >= 60000 then
            Print("  [t+", Runtime() - batch_t0, "ms] H_CACHE starting ",
                  hi, "/", Length(SUBGROUPS_LEFT_RAW),
                  " |H|=", Size(SUBGROUPS_LEFT_RAW[hi]), "\n");
            last_hb := Runtime();
            last_hb_count := hi;
        fi;
        Add(H_CACHE, ComputeHCacheEntry(SUBGROUPS_LEFT_RAW[hi], W_ML, LEFT_Q_GROUPS));
    od;
    Print("[t+", Runtime() - batch_t0, "ms] H_CACHE compute done\n");
    if CACHE_LEFT_PATH <> "" then
        SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
    fi;
fi;
H_CACHE_L := H_CACHE;
Print("[t+", Runtime() - batch_t0, "ms] starting ReconstructHData on ",
      Length(H_CACHE_L), " entries...\n");
last_hb := Runtime();
H1DATA_LIST := [];
for hi in [1..Length(H_CACHE_L)] do
    Add(H1DATA_LIST, ReconstructHData(H_CACHE_L[hi], S_ML));
    if Runtime() - last_hb >= 60000 then
        Print("  [t+", Runtime() - batch_t0, "ms] ReconstructHData ",
              hi, "/", Length(H_CACHE_L), "\n");
        last_hb := Runtime();
    fi;
od;
Print("[t+", Runtime() - batch_t0, "ms] ReconstructHData done; LEFT loaded: ",
      Length(H_CACHE_L), " entries\n");

# JOBS array was loaded above the LEFT cache build (we needed m_right's to
# determine the q-size filter).
Print("JOBS: ", Length(JOBS), " jobs to run\n");

# Per-job processing.
for job_idx in [1..Length(JOBS)] do
    JOB := JOBS[job_idx];
    job_t0 := Runtime();

    MR := JOB.m_right;
    BURNSIDE_M2 := JOB.burnside_m2;
    OUTPUT_PATH := JOB.output_path;
    COMBO_HEADER := JOB.combo_header;
    Print("\n>> JOB ", job_idx, "/", Length(JOBS),
          " combo=", JOB.combo_str,
          " mode=", JOB.mode_str, " m_right=", MR,
          " burnside_m2=", BURNSIDE_M2, "\n");

    S_MR := SymmetricGroup(MR);
    shift_R := MappingPermListList([1..MR], [ML+1..ML+MR]);

    # ---- Load RIGHT for this job ----
    # TG factors: small, just compute fresh (no cache file).
    # Source-list RIGHT: read cache, extend to LEFT_Q_GROUPS coverage if needed.
    if JOB.right_tg_d > 0 then
        T_orig_j := TransitiveGroup(JOB.right_tg_d, JOB.right_tg_t);
        H_CACHE_R := [ComputeHCacheEntry(T_orig_j, S_MR, fail)];
    else
        H_CACHE := fail;
        if JOB.cache_right <> "" and IsValidCacheFile(JOB.cache_right) then
            Read(JOB.cache_right);
            for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
            extend_needed := false;
            for hi in [1..Length(H_CACHE)] do
                missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
                if missing = fail or Length(missing) > 0 then
                    extend_needed := true;
                fi;
            od;
            if extend_needed then
                Print("    [t+", Runtime() - job_t0,
                      "ms] extending RIGHT H_CACHE for new Q-types...\n");
                for hi in [1..Length(H_CACHE)] do
                    missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
                    if missing = fail then
                        ExtendHCacheEntry(H_CACHE[hi], S_MR, fail);
                    elif Length(missing) > 0 then
                        ExtendHCacheEntry(H_CACHE[hi], S_MR, LEFT_Q_GROUPS);
                    fi;
                od;
                if JOB.cache_right <> "" then
                    SaveHCacheList(JOB.cache_right, H_CACHE);
                fi;
            fi;
        fi;
        if H_CACHE = fail then
            Read(JOB.subs_right);
            SUBGROUPS_RIGHT_RAW := SUBGROUPS;
            H_CACHE := List(SUBGROUPS_RIGHT_RAW, H -> ComputeHCacheEntry(H, S_MR, LEFT_Q_GROUPS));
            if JOB.cache_right <> "" then
                SaveHCacheList(JOB.cache_right, H_CACHE);
            fi;
        fi;
        H_CACHE_R := H_CACHE;
    fi;
    H2DATA := List(H_CACHE_R, e -> ReconstructHData(e, S_MR));

    # ---- Goursat counting + collect generator lines for emission ----
    fp_lines := [];

    # In burnside_m2 mode, the ordered-pair iteration visits both (a, b) and
    # (b, a) of each non-diagonal orbit-pair.  These produce S_n-conjugate fp's
    # via swap_perm.  Rather than dedup post-hoc (which requires a fragile
    # GAP `=` test on Group objects without StabChain), we emit only the
    # CANONICAL iteration: h2_orb_idx >= h1_orb_idx.  This gives exactly one
    # rep per unordered orbit-pair {a, b}.  The PREDICTED count
    # (TOTAL_ORB + TOTAL_FIX)/2 from Burnside still uses ALL ordered iterations.

    EmitGen := function(F)
        local gens, s;
        gens := GeneratorsOfGroup(F);
        if Length(gens) > 0 then
            s := JoinStringsWithSeparator(List(gens, String), ",");
        else
            s := "";
        fi;
        Add(fp_lines, Concatenation("[", s, "]"));
    end;

    ProcessPairBatch := function(H1data, H2data, H1, H2)
        local total, swap_fixed, h1orb, h2idxs, h2idx, h2orb, key, isoTH,
              isos, n, gensQ, KeyOf, idx, seen, n_orb, queue, j, phi,
              alpha, beta, neighbor, nkey, k, fp, orbit_id, i, swap_phi,
              swap_key, swap_iso_idx, swap_orbit_id,
              h1_orb_idx, orbit_reps_phi, h_0, t_0, swap_orb_id_arr,
              dcs, A1, A2_in_h1, A2_in_h1_gens, tinv, g_swap;
        total := 0; swap_fixed := 0;
        for h1_orb_idx in [1..Length(H1data.orbits)] do
            h1orb := H1data.orbits[h1_orb_idx];
            key := String(h1orb.qid);
            if not IsBound(H2data.byqid.(key)) then continue; fi;
            h2idxs := H2data.byqid.(key);

            # Canonical-emission gate for burnside_m2: only emit when
            # h2idx >= h1_orb_idx so each unordered orbit-pair {a,b} is
            # emitted exactly once.  Counters increment on ALL ordered pairs
            # (so PREDICTED via Burnside formula remains correct).
            if h1orb.qsize = 1 then
                for h2idx in h2idxs do
                    h2orb := H2data.orbits[h2idx];
                    if h2orb.qsize = 1 then
                        total := total + 1;
                        if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                            # direct product output
                            fp := Group(Concatenation(GeneratorsOfGroup(H1),
                                                      GeneratorsOfGroup(H2)));
                            EmitGen(fp);
                        fi;
                        if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                            swap_fixed := swap_fixed + 1;
                        fi;
                    fi;
                od;
                continue;
            fi;

            if h1orb.qsize = 2 then
                # Optimization (2) 2026-04-28: |Aut(C_2)|=1 so the direct
                # <K1, K2^shift, h_0*t_0^shift> construction works for ANY MR
                # (was previously only used for MR=2).
                for h2idx in h2idxs do
                    h2orb := H2data.orbits[h2idx];
                    if h2orb.qsize <> 2 then continue; fi;
                    total := total + 1;
                    if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                        h_0 := First(GeneratorsOfGroup(H1),
                                     g -> not (g in h1orb.K));
                        t_0 := First(GeneratorsOfGroup(H2data.H),
                                     g -> not (g in h2orb.K));
                        fp := Group(Concatenation(
                            Filtered(GeneratorsOfGroup(h1orb.K), g -> g <> ()),
                            List(Filtered(GeneratorsOfGroup(h2orb.K),
                                          g -> g <> ()),
                                 g -> g^shift_R),
                            [h_0 * t_0^shift_R]));
                        EmitGen(fp);
                    fi;
                    if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                        swap_fixed := swap_fixed + 1;
                    fi;
                od;
                continue;
            fi;

            for h2idx in h2idxs do
                h2orb := H2data.orbits[h2idx];
                if h2orb.qsize <> h1orb.qsize then continue; fi;
                EnsureHom(h1orb); EnsureHom(h2orb);
                isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
                if isoTH = fail then continue; fi;
                # Optimization (5) 2026-04-29: lazy h1.AutQ.  h2 is the RIGHT
                # factor and is pre-warmed at startup; for high-symmetry RIGHTs
                # (e.g. V_4 where N_{S_4}(V_4)/V_4 = S_3 = Aut), h2 saturates
                # for every orbit and forces n_orb=1.  Test h2 first; only build
                # h1.AutQ when h2 does NOT saturate.  ~2.5x on V_4-right combos.
                EnsureAutQ(h2orb);
                if h2orb.full_aut <> true then EnsureAutQ(h1orb); fi;

                # Optimization (1)+(3) 2026-04-28: early Aut-saturation shortcut
                # using cached full_aut flag.  Skip building isos+idx for
                # the saturated case (the common case for high-symmetry RIGHTs).
                if h1orb.full_aut = true or h2orb.full_aut = true then
                    n_orb := 1;
                    orbit_reps_phi := [isoTH];
                    dcs := [];   # placeholder; not used in saturated branch
                else
                    # Optimization (6) 2026-04-29: DoubleCosets replaces BFS.
                    # See ProcessPair (GAP_DRIVER) for the derivation.
                    A1 := SafeSub(h1orb.AutQ, h1orb.A_gens);
                    A2_in_h1_gens := List(h2orb.A_gens,
                        b -> InverseGeneralMapping(isoTH) * b * isoTH);
                    A2_in_h1 := SafeSub(h1orb.AutQ, A2_in_h1_gens);
                    dcs := DoubleCosets(h1orb.AutQ, A1, A2_in_h1);
                    n_orb := Length(dcs);
                    orbit_reps_phi := List(dcs, dc -> isoTH * Representative(dc));
                fi;
                total := total + n_orb;

                # Compute swap-orbit-id per orbit rep (used for both within-pair
                # canonical emission gate and swap_fixed counter).
                # In burnside_m2 self-pair, orbit rep i may be swap-paired with
                # rep j (where j = swap_orb_id_arr[i]).  Emit only when i <= j.
                swap_orb_id_arr := ListWithIdenticalEntries(n_orb, -1);
                if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                    if h1orb.full_aut = true or h2orb.full_aut = true then
                        # Optimization (1) shortcut: 1 orbit, trivially swap-fixed.
                        swap_orb_id_arr[1] := 1;
                    else
                        # Find which double coset contains the swap of each orbit rep.
                        # See ProcessPair (GAP_DRIVER) for the derivation.
                        tinv := InverseGeneralMapping(isoTH);
                        gensQ := GeneratorsOfGroup(h1orb.Q);
                        for i in [1..n_orb] do
                            # g_swap is initially a CompositionMapping which
                            # DoubleCoset.in does not recognize as an h1.AutQ
                            # element.  Reify it as GroupHomomorphismByImagesNC
                            # by evaluating on Q's generators.
                            g_swap := tinv * InverseGeneralMapping(Representative(dcs[i])) * tinv;
                            g_swap := GroupHomomorphismByImagesNC(h1orb.Q, h1orb.Q,
                                gensQ, List(gensQ, q -> Image(g_swap, q)));
                            SetIsBijective(g_swap, true);
                            swap_orb_id_arr[i] :=
                                PositionProperty(dcs, dc -> g_swap in dc);
                        od;
                    fi;
                fi;

                # Emit orbit reps (canonical-gated).
                if BURNSIDE_M2 = 0 or h2idx > h1_orb_idx then
                    # Non-self canonical: emit all orbit reps
                    for i in [1..n_orb] do
                        fp := _GoursatBuildFiberProduct(
                            H1, H2, h1orb.hom,
                            CompositionMapping(h2orb.hom,
                                ConjugatorIsomorphism(H2, shift_R^-1)),
                            InverseGeneralMapping(orbit_reps_phi[i]),
                            [1..ML], [ML+1..ML+MR]);
                        if fp <> fail then EmitGen(fp); fi;
                    od;
                elif BURNSIDE_M2 = 1 and h2idx = h1_orb_idx then
                    # Self-pair: within-pair canonical (i <= swap_orb_id[i]).
                    for i in [1..n_orb] do
                        if swap_orb_id_arr[i] >= i then
                            fp := _GoursatBuildFiberProduct(
                                H1, H2, h1orb.hom,
                                CompositionMapping(h2orb.hom,
                                    ConjugatorIsomorphism(H2, shift_R^-1)),
                                InverseGeneralMapping(orbit_reps_phi[i]),
                                [1..ML], [ML+1..ML+MR]);
                            if fp <> fail then EmitGen(fp); fi;
                        fi;
                    od;
                fi;

                # Burnside swap-fix counter (uses precomputed swap_orb_id_arr).
                if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                    for i in [1..n_orb] do
                        if swap_orb_id_arr[i] = i then
                            swap_fixed := swap_fixed + 1;
                        fi;
                    od;
                fi;
            od;
        od;
        return rec(orbits := total, swap_fixed := swap_fixed);
    end;

    TOTAL_ORB := 0;
    TOTAL_FIX := 0;
    last_hb_ms := Runtime() - job_t0;
    n_pairs_done := 0;
    n_pairs_total := Length(H1DATA_LIST) * Length(H2DATA);
    Print("    [t+", Runtime() - job_t0, "ms] starting H1xH2 loop: ",
          Length(H1DATA_LIST), " x ", Length(H2DATA),
          " = ", n_pairs_total, " pairs\n");
    # Optimization (4) 2026-04-28: precompute shifted RIGHT once per j outside
    # the i loop.  For burnside_m2 mode, H2DATA[1] gets overwritten per-i so
    # we must compute per-pair (only 1 entry, so cheap).
    if BURNSIDE_M2 = 0 then
        H2_SHIFTED := List(H2DATA, hd -> hd.H^shift_R);
    fi;
    for i in [1..Length(H1DATA_LIST)] do
        H1data_j := H1DATA_LIST[i];
        H1_j := H1data_j.H;
        # For burnside_m2: override H2DATA[1] with H1data so K = K comparison works.
        if BURNSIDE_M2 = 1 then
            H2DATA[1] := H1data_j;
        fi;
        for j in [1..Length(H2DATA)] do
            H2data_j := H2DATA[j];
            if BURNSIDE_M2 = 0 then
                H2_j := H2_SHIFTED[j];
            else
                H2_j := H2data_j.H^shift_R;
            fi;
            res_pair := ProcessPairBatch(H1data_j, H2data_j, H1_j, H2_j);
            TOTAL_ORB := TOTAL_ORB + res_pair.orbits;
            TOTAL_FIX := TOTAL_FIX + res_pair.swap_fixed;
            n_pairs_done := n_pairs_done + 1;
            if (Runtime() - job_t0) - last_hb_ms >= 30000 then
                Print("    [t+", Runtime() - job_t0, "ms] pair ",
                      n_pairs_done, "/", n_pairs_total,
                      " (i=", i, "/", Length(H1DATA_LIST),
                      ", j=", j, "/", Length(H2DATA), ") ",
                      "orb_so_far=", TOTAL_ORB, "\n");
                last_hb_ms := Runtime() - job_t0;
            fi;
        od;
    od;

    if BURNSIDE_M2 = 1 then
        PREDICTED := (TOTAL_ORB + TOTAL_FIX) / 2;
    else
        PREDICTED := TOTAL_ORB;
    fi;

    elapsed_ms := Runtime() - job_t0;

    # Atomic per-combo write: write to OUTPUT_PATH.tmp, then mv to final path.
    # This prevents partial-file corruption if GAP crashes mid-write; the
    # final file only appears once all gens + sentinel are flushed.
    TMP_OUT := Concatenation(OUTPUT_PATH, ".tmp");
    PrintTo(TMP_OUT, COMBO_HEADER, "\n");
    AppendTo(TMP_OUT, "# candidates: ", PREDICTED, "\n");
    AppendTo(TMP_OUT, "# deduped: ", PREDICTED, "\n");
    AppendTo(TMP_OUT, "# elapsed_ms: ", elapsed_ms, "\n");
    for line in fp_lines do
        AppendTo(TMP_OUT, line, "\n");
    od;
    Exec(Concatenation("mv -f -- '", TMP_OUT, "' '", OUTPUT_PATH, "'"));

    Print("RESULT idx=", job_idx, " predicted=", PREDICTED,
          " orbits=", TOTAL_ORB, " swap_fixed=", TOTAL_FIX,
          " elapsed_ms=", elapsed_ms, "\n");
od;

LogTo();
QUIT;
"""


# ---------------------------------------------------------------------------
# Super-batch driver: process multiple LEFT-source GROUPS in ONE GAP session,
# amortizing the GAP startup + lifting_algorithm.g load across all of them.
# Useful when many groups have only 1-2 jobs each (e.g., n=14 had 1248 groups
# averaging ~1.2 jobs each).
# ---------------------------------------------------------------------------
SUPER_BATCH_DRIVER = r"""
LogTo("__LOG__");
SizeScreen([100000, 24]);

if not IsBound(_GoursatBuildFiberProduct) then Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g"); fi;

ConjAction := function(K, g) return K^g; end;

SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

InducedAutoGens := function(stab, G, hom)
    return List(GeneratorsOfGroup(stab),
        s -> InducedAutomorphism(hom, ConjugatorAutomorphism(G, s)));
end;

SafeGroup := function(gens, default_amb)
    if Length(gens) = 0 then return TrivialSubgroup(default_amb); fi;
    return Group(gens);
end;

SafeSub := function(G, gens)
    if Length(gens) = 0 then return TrivialSubgroup(G); fi;
    return Subgroup(G, gens);
end;

ReconstructHData := function(entry, S_M)
    local H, N, res, orbit_data, K, Stab, i, key, hom_triv;
    H := SafeGroup(entry.H_gens, S_M);
    N := SafeGroup(entry.N_H_gens, S_M);
    res := rec(H := H, N := N, orbits := []);
    # Trivial-quotient orbit (always present; hom is fast for H/H).
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N, AutQ := fail, A_gens := [], full_aut := fail,
        H_ref := H));
    # Non-trivial orbits: hom and Q are deferred (computed lazily by EnsureHom).
    # NaturalHomomorphismByNormalSubgroup is the dominant cost for large H,
    # and most orbits never get paired against a matching RIGHT qid, so
    # deferring it is the dominant speed win.
    for orbit_data in entry.orbits do
        K := SafeGroup(orbit_data.K_H_gens, S_M);
        Stab := SafeGroup(orbit_data.Stab_NH_KH_gens, S_M);
        Add(res.orbits, rec(K := K, hom := fail, Q := fail,
            qsize := orbit_data.qsize, qid := orbit_data.qid,
            Stab := Stab, AutQ := fail, A_gens := [], full_aut := fail,
            H_ref := H));
    od;
    res.byqid := rec();
    for i in [1..Length(res.orbits)] do
        key := String(res.orbits[i].qid);
        if not IsBound(res.byqid.(key)) then res.byqid.(key) := []; fi;
        Add(res.byqid.(key), i);
    od;
    return res;
end;

# Lazily compute hom and Q for an orbit record.  Mutates the record.
# Idempotent: safe to call repeatedly.
EnsureHom := function(orb)
    if orb.hom <> fail then return; fi;
    orb.hom := NaturalHomomorphismByNormalSubgroup(orb.H_ref, orb.K);
    orb.Q := Range(orb.hom);
end;

# Lazily compute AutQ + A_gens for an orbit record.  Mutates the record.
EnsureAutQ := function(orb)
    if orb.AutQ <> fail then return; fi;
    if orb.qsize <= 1 then return; fi;   # trivial Q has no auto
    EnsureHom(orb);   # AutQ depends on Q
    orb.AutQ := AutomorphismGroup(orb.Q);
    orb.A_gens := InducedAutoGens(orb.Stab, orb.H_ref, orb.hom);
    # Optimization (3) 2026-04-28: cache full_aut.
    if Length(orb.A_gens) = 0 then
        orb.full_aut := false;
    else
        orb.full_aut := (Size(Subgroup(orb.AutQ, orb.A_gens)) = Size(orb.AutQ));
    fi;
end;

# ---- block-wreath ambient for normalizer computation ------------------
# An FPF subgroup H of S_M with cycle-type [m_1, m_2, ...] preserves its own
# cycle decomposition, so N_{S_M}(H) is contained in the block-stabilizer
# Stab_S_M(blocks) = direct product over distinct sizes m of (S_m wr S_count(m)).
# For [4,4,4,4] this is S_4 wr S_4 (size 7.96M vs |S_16|=20.9T): ~3 billion
# times smaller search space for Schreier-Sims, with mathematically identical
# normalizer.
BlockWreathFromPartition := function(partition)
    local factors, i, j, m, mult;
    factors := [];
    i := 1;
    while i <= Length(partition) do
        m := partition[i];
        mult := 0;
        j := i;
        while j <= Length(partition) and partition[j] = m do
            mult := mult + 1;
            j := j + 1;
        od;
        if mult = 1 then
            Add(factors, SymmetricGroup(m));
        else
            Add(factors, WreathProduct(SymmetricGroup(m), SymmetricGroup(mult)));
        fi;
        i := j;
    od;
    if Length(factors) = 1 then return factors[1]; fi;
    return DirectProduct(factors);
end;

# ---- q-size-filtered H-cache helpers ----------------------------------
# An H-cache entry stores per-subgroup data needed for Goursat fiber-product
# enumeration: H_gens, N_H_gens (= Normalizer(S_M, H)), and a list of orbit
# records (one per N_H-orbit on { K normal in H : K <> H, |H/K| in filter }).
# `computed_q_sizes` tracks which Q-sizes are populated; lazy/incremental
# extension lets subsequent runs at higher target_n add the larger Q-sizes
# they need without rebuilding from scratch.  Sentinel `fail` = "all sizes".

# Q-iso classes (as group reps) the LEFT cache must cover when consumed
# against a RIGHT factor of degree M_R.  Returns list of GROUPS, or `fail`
# meaning "full coverage" (no filter).
#
# For M_R >= 6: the union of subgroup orders of TG(M_R, *) already spans
# most divisors of typical |H|, so the filter buys little and the cache is
# simpler/faster with `fail` (avoids per-Q GQuotients calls during
# enumeration and skips cache extension on later reads).
RequiredQGroups := function(M_R)
    local result, seen, t, T, K, Q, qid;
    if M_R >= 6 then return fail; fi;
    result := [];
    seen := Set([]);
    if M_R = 0 then return result; fi;
    for t in [1..NrTransitiveGroups(M_R)] do
        T := TransitiveGroup(M_R, t);
        for K in NormalSubgroups(T) do
            if Size(K) = Size(T) then continue; fi;
            Q := T / K;
            qid := SafeId(Q);
            if not (qid in seen) then
                AddSet(seen, qid);
                Add(result, Q);
            fi;
        od;
    od;
    return result;
end;

QIdsOfGroups := function(q_groups)
    if q_groups = fail then return fail; fi;
    return Set(List(q_groups, SafeId));
end;

QGroupsMissing := function(have_ids, want_groups)
    # want_groups = fail means "full coverage needed". have_ids = fail
    # means "already full coverage". Return values:
    #   []   -- nothing missing (no extension needed)
    #   fail -- need full extension (caller should extend to fail)
    #   list -- specific Q-groups to add via tiered enumeration
    if want_groups = fail then
        if have_ids = fail then return []; fi;
        return fail;
    fi;
    if have_ids = fail then return []; fi;
    return Filtered(want_groups, Q -> not (SafeId(Q) in have_ids));
end;

NormalizeHCacheEntry := function(entry)
    if not IsBound(entry.computed_q_ids) then
        entry.computed_q_ids := fail;
    fi;
    return entry;
end;

# TIERED-OPT enumeration: shared per-H setup + |Q| | |H| short-circuit.
# Per H: ONE DerivedSubgroup, ONE abel_hom call.  Per Q:
#   - |Q| ∤ |H|        -> skip (no surjection possible)
#   - prime Q          -> abelianization (cached A, MaximalSubgroupClassReps)
#   - abelian non-prime Q -> GQuotients(A, Q) on the smaller A
#   - non-abelian Q    -> GQuotients(H, Q) on H itself
#
# NormalSubgroups fast path: for H with few normal subgroups (e.g. S_n, A_n
# which have only 3 / 2 normals), enumerate all normals at once and filter
# by quotient iso-class.  This avoids expensive GQuotients(H, S_n) calls.
# Use this path for H that is simple-or-near-simple (NormalSubgroups is
# O(small) regardless of |H|), or for moderately-sized H.  For complex H
# like D_8^4 with thousands of normals, the tiered Q-by-Q path is preferred.
_EnumerateNormalsForQGroups := function(H, q_groups)
    local q_size_H, DH, abel_hom, A, result, Q, sz, p, max_subs, epi,
          qids_set, all_normals, K, qid_K, use_direct;
    if q_groups = fail then
        return Filtered(NormalSubgroups(H), K -> K <> H);
    fi;
    if Length(q_groups) = 0 then return []; fi;
    # Direct NormalSubgroups + Q-id filter is only cheaper than the smart
    # per-Q routing below when the largest Q is too big for GQuotients to
    # finish (|Q| > 200 in practice).  For everything else — and especially
    # for prime Q, where the fast path is just MaximalSubgroupClassReps(A)
    # on the abelianization — fall through to the per-Q routing.  This was
    # gated on |H| <= 10^6 by mistake, which silently sent every typical
    # H (|H|=4096, 1536, 768, ...) through the slow NS path.
    use_direct := Maximum(List(q_groups, Size)) > 200;
    if use_direct then
        qids_set := Set(List(q_groups, SafeId));
        all_normals := Filtered(NormalSubgroups(H), K -> K <> H);
        result := [];
        for K in all_normals do
            qid_K := SafeId(H/K);
            if qid_K in qids_set then Add(result, K); fi;
        od;
        return Set(result);
    fi;
    q_size_H := Size(H);
    DH := DerivedSubgroup(H);
    if Size(DH) = q_size_H then
        abel_hom := fail; A := fail;
    else
        abel_hom := NaturalHomomorphismByNormalSubgroup(H, DH);
        A := Range(abel_hom);
    fi;
    result := [];
    for Q in q_groups do
        sz := Size(Q);
        if q_size_H mod sz <> 0 then continue; fi;
        if IsPrimeInt(sz) then
            if abel_hom = fail then continue; fi;
            if Size(A) mod sz <> 0 then continue; fi;
            p := sz;
            max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = p);
            Append(result, List(max_subs, K -> PreImage(abel_hom, K)));
        elif IsAbelian(Q) then
            if abel_hom = fail then continue; fi;
            for epi in GQuotients(A, Q) do
                Add(result, PreImage(abel_hom, Kernel(epi)));
            od;
        else
            Append(result, Set(List(GQuotients(H, Q), Kernel)));
        fi;
    od;
    return Set(result);
end;

_ComputeOrbitRecsFromKs := function(H, N_H, normals_to_orbit)
    local K_orbit, K_H, hom_H, Q_H, Stab_NH_KH, orbits;
    orbits := [];
    for K_orbit in Orbits(N_H, normals_to_orbit, ConjAction) do
        K_H := K_orbit[1];
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
    return orbits;
end;

ComputeHCacheEntry := function(H, S_M, q_groups)
    local N_H, normals;
    N_H := Normalizer(S_M, H);
    normals := _EnumerateNormalsForQGroups(H, q_groups);
    return rec(
        H_gens := GeneratorsOfGroup(H),
        N_H_gens := GeneratorsOfGroup(N_H),
        computed_q_ids := QIdsOfGroups(q_groups),
        orbits := _ComputeOrbitRecsFromKs(H, N_H, normals)
    );
end;

ExtendHCacheEntry := function(entry, S_M, additional_q_groups)
    local H, N_H, current, missing_groups, normals, new_orbits, all_normals;
    if entry.computed_q_ids = fail then return entry; fi;
    H := SafeGroup(entry.H_gens, S_M);
    N_H := SafeGroup(entry.N_H_gens, S_M);
    current := entry.computed_q_ids;
    if additional_q_groups = fail then
        # Extend to FULL coverage: enumerate ALL normals; add only the K's
        # whose quotient iso-class is not already in current.
        all_normals := Filtered(NormalSubgroups(H), K -> K <> H);
        normals := Filtered(all_normals, K -> not (SafeId(H/K) in current));
        new_orbits := _ComputeOrbitRecsFromKs(H, N_H, normals);
        Append(entry.orbits, new_orbits);
        entry.computed_q_ids := fail;
        return entry;
    fi;
    missing_groups := QGroupsMissing(current, additional_q_groups);
    if Length(missing_groups) = 0 then return entry; fi;
    normals := _EnumerateNormalsForQGroups(H, missing_groups);
    new_orbits := _ComputeOrbitRecsFromKs(H, N_H, normals);
    Append(entry.orbits, new_orbits);
    UniteSet(entry.computed_q_ids, QIdsOfGroups(missing_groups));
    return entry;
end;

SaveHCacheList := function(path, h_cache)
    local tmp;
    # Atomic write: PrintTo to a .tmp file, then `mv` to the final path.
    # Prevents corrupt-cache leftovers if the process is killed mid-write.
    # Unique tmp filename per call: prevents two GAP workers from clobbering
    # each other's PrintTo when racing on the same cache file.
    tmp := Concatenation(path, ".tmp.", String(Runtime()), ".",
                          String(Random([1..1000000])));
    PrintTo(tmp, "H_CACHE := ", h_cache, ";\n");
    Exec(Concatenation("mv -f -- '", tmp, "' '", path, "'"));
end;

# Read last ~200 bytes of a file and check it ends with "];" (the H_CACHE
# closing bracket).  Used as a corruption sentinel: if a previous run was
# killed mid-PrintTo, the file is truncated and won't end with "];".
IsValidCacheFile := function(path)
    local f, content, n, i;
    if not IsExistingFile(path) then return false; fi;
    f := InputTextFile(path);
    if f = fail then return false; fi;
    content := ReadAll(f);
    CloseStream(f);
    n := Length(content);
    if n < 20 then return false; fi;
    # Strip trailing whitespace.
    while n > 0 and content[n] in [' ', '\n', '\r', '\t'] do
        n := n - 1;
    od;
    if n < 2 then return false; fi;
    return content[n-1] = ']' and content[n] = ';';
end;

# ---- GROUPS array (substituted by Python) ----
# Each entry: rec(group_idx, m_left, subs_left, cache_left, jobs := [...])
GROUPS := __GROUPS_ARRAY__;
Print("SUPER_BATCH: ", Length(GROUPS), " groups to process\n");

global_t0 := Runtime();

for group_idx in [1..Length(GROUPS)] do
    GROUP := GROUPS[group_idx];
    Print("\n=== GROUP ", group_idx, "/", Length(GROUPS),
          " ml=", GROUP.m_left, " jobs=", Length(GROUP.jobs),
          " LEFT=", GROUP.left_combo_str, " ===\n");
    group_t0 := Runtime();

    ML := GROUP.m_left;
    SUBS_LEFT_PATH  := GROUP.subs_left;
    CACHE_LEFT_PATH := GROUP.cache_left;
    S_ML := SymmetricGroup(ML);
    # W_ML = block-wreath ambient for normalizer computation; mathematically
    # identical to S_ML for FPF subgroups but vastly faster (e.g. S_4 wr S_4
    # has size 7.96M vs S_16 at 20.9T for partition [4,4,4,4]).
    W_ML := BlockWreathFromPartition(GROUP.m_left_partition);

    # Compute LEFT q-size filter from union of m_right's across this group's jobs
    LEFT_Q_GROUPS := [];
    seen_qids := Set([]);
    for hi in [1..Length(GROUP.jobs)] do
        rq := RequiredQGroups(GROUP.jobs[hi].m_right);
        if rq = fail then
            LEFT_Q_GROUPS := fail;
            break;
        fi;
        for Q in rq do
            if not (SafeId(Q) in seen_qids) then
                AddSet(seen_qids, SafeId(Q));
                Add(LEFT_Q_GROUPS, Q);
            fi;
        od;
    od;
    # Holt-split augmentation: union in Q-iso classes from each source-file
    # RIGHT (non-TG).  Skip if LEFT_Q_GROUPS = fail (full coverage).
    if LEFT_Q_GROUPS <> fail then
        seen_subs_paths := Set([]);
        for hi in [1..Length(GROUP.jobs)] do
            if GROUP.jobs[hi].subs_right <> "" and
               not (GROUP.jobs[hi].subs_right in seen_subs_paths) then
                AddSet(seen_subs_paths, GROUP.jobs[hi].subs_right);
                Read(GROUP.jobs[hi].subs_right);
                for R in SUBGROUPS do
                    for K in NormalSubgroups(R) do
                        if Size(K) = Size(R) then continue; fi;
                        Q := R/K;
                        qid := SafeId(Q);
                        if not (qid in seen_qids) then
                            AddSet(seen_qids, qid);
                            Add(LEFT_Q_GROUPS, Q);
                        fi;
                    od;
                od;
            fi;
        od;
    fi;
    if LEFT_Q_GROUPS = fail then
        Print("  [t+", Runtime() - group_t0, "ms] LEFT Q-groups: full coverage\n");
    else
        Print("  [t+", Runtime() - group_t0, "ms] LEFT Q-groups: ",
              Length(LEFT_Q_GROUPS), " types, max |Q|=",
              Maximum(Concatenation([0], List(LEFT_Q_GROUPS, Size))), "\n");
    fi;

    # ---- Load LEFT side for this group ----
    H_CACHE := fail;
    if CACHE_LEFT_PATH <> "" and IsValidCacheFile(CACHE_LEFT_PATH) then
        Print("  [t+", Runtime() - group_t0, "ms] reading H_CACHE from disk: ",
              CACHE_LEFT_PATH, "\n");
        Read(CACHE_LEFT_PATH);
        Print("  [t+", Runtime() - group_t0, "ms] H_CACHE read complete: ",
              Length(H_CACHE), " entries\n");
    fi;
    if H_CACHE <> fail then
        for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
        extend_needed := false;
        for hi in [1..Length(H_CACHE)] do
            missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
            if missing = fail or Length(missing) > 0 then
                extend_needed := true;
            fi;
        od;
        if extend_needed then
            Print("  [t+", Runtime() - group_t0,
                  "ms] extending H_CACHE for new Q-types...\n");
            for hi in [1..Length(H_CACHE)] do
                missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
                if missing = fail then
                    ExtendHCacheEntry(H_CACHE[hi], W_ML, fail);
                elif Length(missing) > 0 then
                    ExtendHCacheEntry(H_CACHE[hi], W_ML, missing);
                fi;
            od;
            if CACHE_LEFT_PATH <> "" then
                SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
            fi;
            Print("  [t+", Runtime() - group_t0, "ms] extension done\n");
        fi;
    fi;
    if H_CACHE = fail then
        Print("  [t+", Runtime() - group_t0, "ms] no cache; reading subs from ",
              SUBS_LEFT_PATH, "\n");
        Read(SUBS_LEFT_PATH);
        SUBGROUPS_LEFT_RAW := SUBGROUPS;
        Print("  [t+", Runtime() - group_t0, "ms] computing H_CACHE for ",
              Length(SUBGROUPS_LEFT_RAW), " subgroups (in W_ML)...\n");
        last_hb := Runtime();
        last_hb_count := 0;
        H_CACHE := [];
        for hi in [1..Length(SUBGROUPS_LEFT_RAW)] do
            if hi = 1 or hi - last_hb_count >= 500
               or Runtime() - last_hb >= 60000 then
                Print("    [t+", Runtime() - group_t0, "ms] H_CACHE starting ",
                      hi, "/", Length(SUBGROUPS_LEFT_RAW),
                      " |H|=", Size(SUBGROUPS_LEFT_RAW[hi]), "\n");
                last_hb := Runtime();
                last_hb_count := hi;
            fi;
            Add(H_CACHE, ComputeHCacheEntry(SUBGROUPS_LEFT_RAW[hi], W_ML, LEFT_Q_GROUPS));
        od;
        Print("  [t+", Runtime() - group_t0, "ms] H_CACHE compute done\n");
        if CACHE_LEFT_PATH <> "" then
            Print("  [t+", Runtime() - group_t0, "ms] writing H_CACHE to ",
                  CACHE_LEFT_PATH, "\n");
            SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
            Print("  [t+", Runtime() - group_t0, "ms] H_CACHE write done\n");
        fi;
    fi;
    H_CACHE_L := H_CACHE;
    Print("  [t+", Runtime() - group_t0, "ms] starting ReconstructHData on ",
          Length(H_CACHE_L), " entries...\n");
    last_hb := Runtime();
    H1DATA_LIST := [];
    for hi in [1..Length(H_CACHE_L)] do
        Add(H1DATA_LIST, ReconstructHData(H_CACHE_L[hi], S_ML));
        if Runtime() - last_hb >= 60000 then
            Print("    [t+", Runtime() - group_t0, "ms] ReconstructHData ",
                  hi, "/", Length(H_CACHE_L), "\n");
            last_hb := Runtime();
        fi;
    od;
    Print("  [t+", Runtime() - group_t0, "ms] ReconstructHData done\n");

    JOBS := GROUP.jobs;

    # Per-job loop (same as BATCH_DRIVER's body)
    for job_idx in [1..Length(JOBS)] do
        JOB := JOBS[job_idx];
        job_t0 := Runtime();
        MR := JOB.m_right;
        BURNSIDE_M2 := JOB.burnside_m2;
        OUTPUT_PATH := JOB.output_path;
        COMBO_HEADER := JOB.combo_header;
        Print("  >> JOB ", job_idx, "/", Length(JOBS),
              " combo=", JOB.combo_str,
              " mode=", JOB.mode_str, " m_right=", MR,
              " burnside_m2=", BURNSIDE_M2, "\n");

        S_MR := SymmetricGroup(MR);
        shift_R := MappingPermListList([1..MR], [ML+1..ML+MR]);

        if JOB.right_tg_d > 0 then
            T_orig_j := TransitiveGroup(JOB.right_tg_d, JOB.right_tg_t);
            H_CACHE_R := [ComputeHCacheEntry(T_orig_j, S_MR, fail)];
        else
            H_CACHE := fail;
            if JOB.cache_right <> "" and IsValidCacheFile(JOB.cache_right) then
                Read(JOB.cache_right);
                for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
                extend_needed := false;
                for hi in [1..Length(H_CACHE)] do
                    missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
                    if missing = fail or Length(missing) > 0 then
                        extend_needed := true;
                    fi;
                od;
                if extend_needed then
                    Print("    [t+", Runtime() - job_t0,
                          "ms] extending RIGHT H_CACHE for new Q-types...\n");
                    for hi in [1..Length(H_CACHE)] do
                        missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
                        if missing = fail then
                            ExtendHCacheEntry(H_CACHE[hi], S_MR, fail);
                        elif Length(missing) > 0 then
                            ExtendHCacheEntry(H_CACHE[hi], S_MR, LEFT_Q_GROUPS);
                        fi;
                    od;
                    if JOB.cache_right <> "" then
                        SaveHCacheList(JOB.cache_right, H_CACHE);
                    fi;
                fi;
            fi;
            if H_CACHE = fail then
                Read(JOB.subs_right);
                SUBGROUPS_RIGHT_RAW := SUBGROUPS;
                H_CACHE := List(SUBGROUPS_RIGHT_RAW, H -> ComputeHCacheEntry(H, S_MR, LEFT_Q_GROUPS));
                if JOB.cache_right <> "" then
                    SaveHCacheList(JOB.cache_right, H_CACHE);
                fi;
            fi;
            H_CACHE_R := H_CACHE;
        fi;
        Print("    [t+", Runtime() - job_t0, "ms] H_CACHE_R loaded (",
              Length(H_CACHE_R), " entries), reconstructing...\n");
        H2DATA := List(H_CACHE_R, e -> ReconstructHData(e, S_MR));
        Print("    [t+", Runtime() - job_t0, "ms] ReconstructHData done\n");

        # ---- Goursat counting + emission ----
        # In burnside_m2: emit only canonical (h2idx >= h1_orb_idx) iterations
        # so each unordered orbit-pair is emitted once.  No post-hoc swap-dedup.
        fp_lines := [];

        EmitGen := function(F)
            local gens, s;
            gens := GeneratorsOfGroup(F);
            if Length(gens) > 0 then
                s := JoinStringsWithSeparator(List(gens, String), ",");
            else
                s := "";
            fi;
            Add(fp_lines, Concatenation("[", s, "]"));
        end;

        ProcessPairBatch := function(H1data, H2data, H1, H2)
            local total, swap_fixed, h1orb, h2idxs, h2idx, h2orb, key, isoTH,
                  isos, n, gensQ, KeyOf, idx, seen, n_orb, queue, j, phi,
                  alpha, beta, neighbor, nkey, k, fp, orbit_id, i, swap_phi,
                  swap_key, swap_iso_idx, swap_orbit_id,
                  h1_orb_idx, orbit_reps_phi, h_0, t_0, swap_orb_id_arr,
                  dcs, A1, A2_in_h1, A2_in_h1_gens, tinv, g_swap;
            total := 0; swap_fixed := 0;
            for h1_orb_idx in [1..Length(H1data.orbits)] do
                h1orb := H1data.orbits[h1_orb_idx];
                key := String(h1orb.qid);
                if not IsBound(H2data.byqid.(key)) then continue; fi;
                h2idxs := H2data.byqid.(key);

                # Canonical-emission gate: in burnside_m2, only emit when
                # h2idx >= h1_orb_idx (each unordered orbit-pair once).
                if h1orb.qsize = 1 then
                    for h2idx in h2idxs do
                        h2orb := H2data.orbits[h2idx];
                        if h2orb.qsize = 1 then
                            total := total + 1;
                            if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                                fp := Group(Concatenation(GeneratorsOfGroup(H1),
                                                          GeneratorsOfGroup(H2)));
                                EmitGen(fp);
                            fi;
                            if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                                swap_fixed := swap_fixed + 1;
                            fi;
                        fi;
                    od;
                    continue;
                fi;

                if h1orb.qsize = 2 then
                    # Optimization (2) 2026-04-28: |Aut(C_2)|=1 -> direct
                    # construction works for all MR.
                    for h2idx in h2idxs do
                        h2orb := H2data.orbits[h2idx];
                        if h2orb.qsize <> 2 then continue; fi;
                        total := total + 1;
                        if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                            h_0 := First(GeneratorsOfGroup(H1),
                                         g -> not (g in h1orb.K));
                            t_0 := First(GeneratorsOfGroup(H2data.H),
                                         g -> not (g in h2orb.K));
                            fp := Group(Concatenation(
                                Filtered(GeneratorsOfGroup(h1orb.K),
                                         g -> g <> ()),
                                List(Filtered(GeneratorsOfGroup(h2orb.K),
                                              g -> g <> ()),
                                     g -> g^shift_R),
                                [h_0 * t_0^shift_R]));
                            EmitGen(fp);
                        fi;
                        if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                            swap_fixed := swap_fixed + 1;
                        fi;
                    od;
                    continue;
                fi;

                for h2idx in h2idxs do
                    h2orb := H2data.orbits[h2idx];
                    if h2orb.qsize <> h1orb.qsize then continue; fi;
                    EnsureHom(h1orb); EnsureHom(h2orb);
                    isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
                    if isoTH = fail then continue; fi;
                    # Optimization (5) 2026-04-29: lazy h1.AutQ.  h2 is the RIGHT
                    # factor and is pre-warmed at startup; for high-symmetry RIGHTs
                    # (e.g. V_4 where N_{S_4}(V_4)/V_4 = S_3 = Aut), h2 saturates
                    # for every orbit and forces n_orb=1.  Test h2 first; only build
                    # h1.AutQ when h2 does NOT saturate.  ~2.5x on V_4-right combos.
                    EnsureAutQ(h2orb);
                    if h2orb.full_aut <> true then EnsureAutQ(h1orb); fi;

                    # Optimization (1)+(3) 2026-04-28: early Aut-saturation
                    # shortcut using cached full_aut flag.
                    if h1orb.full_aut = true or h2orb.full_aut = true then
                        n_orb := 1;
                        orbit_reps_phi := [isoTH];
                        dcs := [];   # placeholder; not used in saturated branch
                    else
                        # Optimization (6) 2026-04-29: DoubleCosets replaces BFS.
                        # See ProcessPair (GAP_DRIVER) for the derivation.
                        A1 := SafeSub(h1orb.AutQ, h1orb.A_gens);
                        A2_in_h1_gens := List(h2orb.A_gens,
                            b -> InverseGeneralMapping(isoTH) * b * isoTH);
                        A2_in_h1 := SafeSub(h1orb.AutQ, A2_in_h1_gens);
                        dcs := DoubleCosets(h1orb.AutQ, A1, A2_in_h1);
                        n_orb := Length(dcs);
                        orbit_reps_phi := List(dcs, dc -> isoTH * Representative(dc));
                    fi;
                    total := total + n_orb;

                    # Compute swap-orbit-id per orbit rep (for within-self-pair
                    # canonical emission gate AND swap_fixed counter).
                    swap_orb_id_arr := ListWithIdenticalEntries(n_orb, -1);
                    if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                        if h1orb.full_aut = true or h2orb.full_aut = true then
                            # Optimization (1) shortcut: 1 orbit, trivially swap-fixed.
                            swap_orb_id_arr[1] := 1;
                        else
                            # Find which double coset contains the swap of each rep.
                            # See ProcessPair (GAP_DRIVER) for the derivation.
                            tinv := InverseGeneralMapping(isoTH);
                            gensQ := GeneratorsOfGroup(h1orb.Q);
                            for i in [1..n_orb] do
                                # g_swap is initially a CompositionMapping which
                                # DoubleCoset.in does not recognize as an h1.AutQ
                                # element.  Reify it as GroupHomomorphismByImagesNC
                                # by evaluating on Q's generators.
                                g_swap := tinv * InverseGeneralMapping(Representative(dcs[i])) * tinv;
                                g_swap := GroupHomomorphismByImagesNC(h1orb.Q, h1orb.Q,
                                    gensQ, List(gensQ, q -> Image(g_swap, q)));
                                SetIsBijective(g_swap, true);
                                swap_orb_id_arr[i] :=
                                    PositionProperty(dcs, dc -> g_swap in dc);
                            od;
                        fi;
                    fi;

                    if BURNSIDE_M2 = 0 or h2idx > h1_orb_idx then
                        # Non-self canonical: emit all orbit reps.
                        for i in [1..n_orb] do
                            fp := _GoursatBuildFiberProduct(
                                H1, H2, h1orb.hom,
                                CompositionMapping(h2orb.hom,
                                    ConjugatorIsomorphism(H2, shift_R^-1)),
                                InverseGeneralMapping(orbit_reps_phi[i]),
                                [1..ML], [ML+1..ML+MR]);
                            if fp <> fail then EmitGen(fp); fi;
                        od;
                    elif BURNSIDE_M2 = 1 and h2idx = h1_orb_idx then
                        # Self-pair: within-pair canonical (i <= swap_orb_id[i]).
                        for i in [1..n_orb] do
                            if swap_orb_id_arr[i] >= i then
                                fp := _GoursatBuildFiberProduct(
                                    H1, H2, h1orb.hom,
                                    CompositionMapping(h2orb.hom,
                                        ConjugatorIsomorphism(H2, shift_R^-1)),
                                    InverseGeneralMapping(orbit_reps_phi[i]),
                                    [1..ML], [ML+1..ML+MR]);
                                if fp <> fail then EmitGen(fp); fi;
                            fi;
                        od;
                    fi;

                    if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                        for i in [1..n_orb] do
                            if swap_orb_id_arr[i] = i then
                                swap_fixed := swap_fixed + 1;
                            fi;
                        od;
                    fi;
                od;
            od;
            return rec(orbits := total, swap_fixed := swap_fixed);
        end;

        TOTAL_ORB := 0; TOTAL_FIX := 0;
        last_hb_ms := Runtime() - job_t0;
        n_pairs_done := 0;
        n_pairs_total := Length(H1DATA_LIST) * Length(H2DATA);
        Print("    [t+", Runtime() - job_t0, "ms] starting H1xH2 loop: ",
              Length(H1DATA_LIST), " x ", Length(H2DATA),
              " = ", n_pairs_total, " pairs\n");
        # Optimization (4) 2026-04-28: precompute shifted RIGHT once per j.
        if BURNSIDE_M2 = 0 then
            H2_SHIFTED := List(H2DATA, hd -> hd.H^shift_R);
        fi;
        for i in [1..Length(H1DATA_LIST)] do
            H1data_j := H1DATA_LIST[i];
            H1_j := H1data_j.H;
            if BURNSIDE_M2 = 1 then H2DATA[1] := H1data_j; fi;
            for j in [1..Length(H2DATA)] do
                H2data_j := H2DATA[j];
                if BURNSIDE_M2 = 0 then
                    H2_j := H2_SHIFTED[j];
                else
                    H2_j := H2data_j.H^shift_R;
                fi;
                res_pair := ProcessPairBatch(H1data_j, H2data_j, H1_j, H2_j);
                TOTAL_ORB := TOTAL_ORB + res_pair.orbits;
                TOTAL_FIX := TOTAL_FIX + res_pair.swap_fixed;
                n_pairs_done := n_pairs_done + 1;
                # Heartbeat every 30s of wall time inside this job.
                if (Runtime() - job_t0) - last_hb_ms >= 30000 then
                    Print("    [t+", Runtime() - job_t0, "ms] pair ",
                          n_pairs_done, "/", n_pairs_total,
                          " (i=", i, "/", Length(H1DATA_LIST),
                          ", j=", j, "/", Length(H2DATA), ") ",
                          "orb_so_far=", TOTAL_ORB, "\n");
                    last_hb_ms := Runtime() - job_t0;
                fi;
            od;
        od;

        if BURNSIDE_M2 = 1 then PREDICTED := (TOTAL_ORB + TOTAL_FIX) / 2;
        else PREDICTED := TOTAL_ORB; fi;
        elapsed_ms := Runtime() - job_t0;

        # Atomic per-combo write (see notes in BATCH_DRIVER above).
        TMP_OUT := Concatenation(OUTPUT_PATH, ".tmp");
        PrintTo(TMP_OUT, COMBO_HEADER, "\n");
        AppendTo(TMP_OUT, "# candidates: ", PREDICTED, "\n");
        AppendTo(TMP_OUT, "# deduped: ", PREDICTED, "\n");
        AppendTo(TMP_OUT, "# elapsed_ms: ", elapsed_ms, "\n");
        for line in fp_lines do
            AppendTo(TMP_OUT, line, "\n");
        od;
        Exec(Concatenation("mv -f -- '", TMP_OUT, "' '", OUTPUT_PATH, "'"));

        Print("RESULT group=", group_idx, " job=", job_idx,
              " predicted=", PREDICTED, " orbits=", TOTAL_ORB,
              " swap_fixed=", TOTAL_FIX, " elapsed_ms=", elapsed_ms, "\n");
    od;

    Print("GROUP ", group_idx, " done in ", Runtime() - group_t0, "ms\n");
od;

Print("\nSUPER_BATCH_DONE total_elapsed=", Runtime() - global_t0, "ms\n");
LogTo();
QUIT;
"""


def predict_super_batch(groups, force=False, timeout=10800):
    """Run multiple LEFT-source groups in ONE GAP session.
    `groups` = list of {left_combo: tuple, jobs: [{combo, mode, output_path}, ...]}.
    Returns flat list of per-job results (in the same order as groups + jobs)."""
    if not groups:
        return []

    import uuid
    work_root = TMP / "_super_batch" / f"sb_{uuid.uuid4().hex[:12]}"
    work_root.mkdir(parents=True, exist_ok=True)
    log = work_root / "super.log"
    if log.exists(): log.unlink()

    gap_groups = []
    flat_jobs = []
    for g_i, g in enumerate(groups):
        left_combo = g["left_combo"]
        jobs = g["jobs"]
        sl = source_path(left_combo)
        if not sl.exists():
            for j in jobs:
                flat_jobs.append({"error": f"left source not found: {sl}",
                                  "combo": j["combo"]})
            continue
        cache_l = cache_path_for_source(sl)
        cache_l.parent.mkdir(parents=True, exist_ok=True)
        subs_l_g = work_root / f"subs_left_g{g_i}.g"
        subs_l_g.write_text(_subs_g_text(parse_combo_file(sl)), encoding="utf-8")

        job_records = []
        for job in jobs:
            inputs = resolve_inputs(job["combo"], job["mode"])
            rec = {
                "m_right": inputs["m_right"],
                "burnside_m2": 1 if inputs["burnside_m2"] else 0,
                "output_path": to_cyg(Path(job["output_path"])),
                "combo_header": _format_combo_header(job["combo"]),
                "combo_str": combo_filename(job["combo"]),
                "mode_str": job["mode"],
            }
            if inputs["right_tg"] is not None:
                rec["right_tg_d"] = inputs["right_tg"][0]
                rec["right_tg_t"] = inputs["right_tg"][1]
                rec["subs_right"] = ""
                rec["cache_right"] = ""
            else:
                sr = source_path(inputs["right_combo"])
                cr = cache_path_for_source(sr)
                cr.parent.mkdir(parents=True, exist_ok=True)
                subs_r_g = work_root / f"subs_right_g{g_i}_{combo_filename(inputs['right_combo'])}.g"
                subs_r_g.write_text(_subs_g_text(parse_combo_file(sr)), encoding="utf-8")
                rec["right_tg_d"] = 0
                rec["right_tg_t"] = 0
                rec["subs_right"] = to_cyg(subs_r_g)
                rec["cache_right"] = to_cyg(cr)
            job_records.append(rec)
            flat_jobs.append({"combo": combo_filename(job["combo"]),
                              "mode": job["mode"]})

        gap_groups.append({
            "m_left": sum(d for d, _ in left_combo),
            "m_left_partition": partition_from_source(left_combo),
            "left_combo_str": combo_filename(left_combo),
            "subs_left": to_cyg(subs_l_g),
            "cache_left": to_cyg(cache_l),
            "jobs": job_records,
        })

    def _gap_str(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _gap_value(v):
        if isinstance(v, str):
            return _gap_str(v)
        if isinstance(v, dict):
            return _gap_record(v)
        if isinstance(v, list):
            return "[" + ",".join(_gap_value(e) for e in v) + "]"
        return str(v)

    def _gap_record(rec):
        return "rec(" + ", ".join(f"{k} := {_gap_value(v)}" for k, v in rec.items()) + ")"

    groups_array = "[\n  " + ",\n  ".join(_gap_record(g) for g in gap_groups) + "\n]"

    run_g = work_root / "super_run.g"
    run_g.write_text(
        SUPER_BATCH_DRIVER
        .replace("__LOG__", to_cyg(log))
        .replace("__GROUPS_ARRAY__", groups_array),
        encoding="utf-8"
    )

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 -L "{LIFTING_WS_CYG}" "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    try:
        _gap_run(cmd, env, timeout, diag_dir=work_root)
    except subprocess.TimeoutExpired:
        return [{"error": "super_batch timeout"} for _ in flat_jobs]
    elapsed_total = round(time.time() - t0, 1)

    log_text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    result_re = re.compile(
        r"RESULT group=\s*(\d+)\s+job=\s*(\d+)\s+predicted=\s*(\d+)\s+"
        r"orbits=\s*(\d+)\s+swap_fixed=\s*(\d+)\s+elapsed_ms=\s*(\d+)")
    # Map (group_idx, job_idx) -> result
    parsed = {}
    for m in result_re.finditer(log_text):
        g = int(m.group(1))
        j = int(m.group(2))
        parsed[(g, j)] = {
            "predicted": int(m.group(3)),
            "orbits": int(m.group(4)),
            "swap_fixed": int(m.group(5)),
            "elapsed_s": int(m.group(6)) / 1000.0,
        }
    # Re-emit results in flat order
    out = []
    fi = 0
    for g_i, g in enumerate(groups, start=1):
        for j_i, job in enumerate(g["jobs"], start=1):
            entry = {"combo": combo_filename(job["combo"]),
                     "mode": job["mode"],
                     "output_path": job["output_path"]}
            key = (g_i, j_i)
            if key in parsed:
                entry.update(parsed[key])
            else:
                entry["error"] = (
                    f"no RESULT for super-batch job (g={g_i}, j={j_i}, "
                    f"combo={combo_filename(job['combo'])}, "
                    f"left={combo_filename(g['left_combo'])})")
            out.append(entry)
    return out


def predict_batch(jobs, force=False, timeout=7200):
    """Run a batch of jobs all sharing the SAME LEFT source.
    Each job dict: {combo: tuple, mode: str, output_path: str}.
    Returns list of results matching the input order."""
    if not jobs:
        return []

    # Resolve LEFT source from first job (must be same for all).
    first_inputs = resolve_inputs(jobs[0]["combo"], jobs[0]["mode"])
    left_combo = first_inputs["left_combo"]
    sl = source_path(left_combo)
    if not sl.exists():
        return [{"error": f"left source not found: {sl}"}] * len(jobs)
    cache_l = cache_path_for_source(sl)
    cache_l.parent.mkdir(parents=True, exist_ok=True)

    # Validate all jobs have same LEFT.
    for job in jobs[1:]:
        inputs = resolve_inputs(job["combo"], job["mode"])
        if inputs["left_combo"] != left_combo:
            return [{"error": f"jobs disagree on LEFT: {inputs['left_combo']} vs {left_combo}"}] * len(jobs)

    # Build job records.
    job_records = []
    # Unique work_root per call (UUID): prevents concurrent workers calling
    # predict_batch with the same LEFT key from racing on shared files
    # (manifests as `WinError 32: file in use` when two workers try to
    # unlink/write the same batch_run.g concurrently).
    work_root = TMP / "_batch" / f"{combo_filename(left_combo)}_{uuid.uuid4().hex[:12]}"
    work_root.mkdir(parents=True, exist_ok=True)
    subs_l_g = work_root / "subs_left.g"
    subs_l_g.write_text(_subs_g_text(parse_combo_file(sl)), encoding="utf-8")

    for job in jobs:
        inputs = resolve_inputs(job["combo"], job["mode"])
        out_path = Path(job["output_path"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "m_right": inputs["m_right"],
            "burnside_m2": 1 if inputs["burnside_m2"] else 0,
            "output_path": to_cyg(out_path),
            "combo_header": _format_combo_header(job["combo"]),
            "combo_str": combo_filename(job["combo"]),
            "mode_str": job["mode"],
        }
        if inputs["right_tg"] is not None:
            record["right_tg_d"] = inputs["right_tg"][0]
            record["right_tg_t"] = inputs["right_tg"][1]
            record["subs_right"] = ""
            record["cache_right"] = ""
        else:
            sr = source_path(inputs["right_combo"])
            cr = cache_path_for_source(sr)
            cr.parent.mkdir(parents=True, exist_ok=True)
            subs_r_g = work_root / f"subs_right_{combo_filename(inputs['right_combo'])}.g"
            subs_r_g.write_text(_subs_g_text(parse_combo_file(sr)), encoding="utf-8")
            record["right_tg_d"] = 0
            record["right_tg_t"] = 0
            record["subs_right"] = to_cyg(subs_r_g)
            record["cache_right"] = to_cyg(cr)
        job_records.append(record)

    # Build JOBS array as a GAP record literal.
    def _gap_str(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _gap_record(rec):
        items = []
        for k, v in rec.items():
            if isinstance(v, str):
                items.append(f"{k} := {_gap_str(v)}")
            else:
                items.append(f"{k} := {v}")
        return "rec(" + ", ".join(items) + ")"

    jobs_array = "[\n  " + ",\n  ".join(_gap_record(r) for r in job_records) + "\n]"

    log = work_root / "batch.log"
    if log.exists(): log.unlink()
    run_g = work_root / "batch_run.g"
    left_part = partition_from_source(left_combo)
    run_g.write_text(
        BATCH_DRIVER
        .replace("__LOG__", to_cyg(log))
        .replace("__M_LEFT__", str(first_inputs["m_left"]))
        .replace("__M_LEFT_PARTITION__", "[" + ",".join(str(d) for d in left_part) + "]")
        .replace("__SUBS_L__", to_cyg(subs_l_g))
        .replace("__CACHE_L__", to_cyg(cache_l))
        .replace("__JOBS_ARRAY__", jobs_array),
        encoding="utf-8"
    )

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 -L "{LIFTING_WS_CYG}" "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    try:
        _gap_run(cmd, env, timeout, diag_dir=work_root)
    except subprocess.TimeoutExpired:
        return [{"error": "batch timeout", "elapsed_s": time.time() - t0}] * len(jobs)
    elapsed_total = round(time.time() - t0, 1)

    # Parse RESULT lines from log.
    log_text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    result_re = re.compile(
        r"RESULT idx=\s*(\d+)\s+predicted=\s*(\d+)\s+orbits=\s*(\d+)\s+swap_fixed=\s*(\d+)\s+elapsed_ms=\s*(\d+)")
    out_per_job = [None] * len(jobs)
    for m in result_re.finditer(log_text):
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(jobs):
            out_per_job[idx] = {
                "combo": combo_filename(jobs[idx]["combo"]),
                "mode": jobs[idx]["mode"],
                "predicted": int(m.group(2)),
                "orbits": int(m.group(3)),
                "swap_fixed": int(m.group(4)),
                "elapsed_s": int(m.group(5)) / 1000.0,
                "output_path": jobs[idx]["output_path"],
            }
    # Fill in missing entries
    for i, r in enumerate(out_per_job):
        if r is None:
            out_per_job[i] = {"error": "no RESULT for job", "log_tail": log_text[-500:]}
    return out_per_job


def _subs_g_text(subs_list):
    lines = ["SUBGROUPS := ["]
    for i, s in enumerate(subs_list):
        sep = "," if i < len(subs_list) - 1 else ""
        lines.append(f"  Group({s}){sep}")
    lines.append("];")
    return "\n".join(lines) + "\n"


def _format_combo_header(combo):
    """Legacy '# combo:' line: matches `_WriteComboResults` in lifting_method_fast_v2.g.
    Format: '# combo: [ [ d1, t1 ], [ d2, t2 ], ... ]'  (with sorted (d,t) pairs)."""
    pairs = ", ".join(f"[ {d}, {t} ]" for d, t in sorted(combo))
    return f"# combo: [ {pairs} ]"


def _join_gap_continuations(raw_lines):
    """GAP wraps output at ~80 cols with a trailing backslash on continuation
    lines.  Reassemble each logical entry into a single line."""
    joined, buf = [], []
    for ln in raw_lines:
        if ln.endswith("\\"):
            buf.append(ln[:-1])      # drop trailing backslash
        else:
            buf.append(ln)
            joined.append("".join(buf))
            buf = []
    if buf:
        joined.append("".join(buf))
    return [ln for ln in joined if ln.strip()]


def _write_legacy_format(output_path, combo, raw_gens_lines, deduped_count, elapsed_ms):
    """Write combo file with legacy header followed by generator lines.
    Joins GAP line-continuations so each generator is one physical line
    (matching legacy parallel_sn/.../<combo>.g format)."""
    joined_lines = _join_gap_continuations(raw_gens_lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(_format_combo_header(combo) + "\n")
        f.write(f"# candidates: {deduped_count}\n")
        f.write(f"# deduped: {deduped_count}\n")
        f.write(f"# elapsed_ms: {elapsed_ms}\n")
        for line in joined_lines:
            f.write(line + "\n")
    return len(joined_lines)


def predict(combo, mode="auto", emit_generators=False, output_path=None,
            force=False, timeout=3600):
    if isinstance(combo, str):
        combo = parse_combo_str(combo)
    target_n = sum(d for d, _ in combo)

    if mode == "auto":
        mode = auto_mode(combo)
    if mode == "unsupported":
        return {"error": "no 2-factor mode applicable to this combo"}

    inputs = resolve_inputs(combo, mode)
    target_str = combo_filename(combo)
    work = TMP / target_str
    work.mkdir(parents=True, exist_ok=True)
    result_path = work / "result.json"
    if result_path.exists() and not force and not emit_generators:
        return json.loads(result_path.read_text())

    # Resolve LEFT source file + cache.
    sl = source_path(inputs["left_combo"])
    if not sl.exists():
        return {"error": f"left source not found: {sl}"}
    cache_l = cache_path_for_source(sl)
    cache_l.parent.mkdir(parents=True, exist_ok=True)

    # Resolve RIGHT.
    if inputs["right_tg"] is not None:
        d, t = inputs["right_tg"]
        sr = ""
        cache_r = ""
    else:
        sr = source_path(inputs["right_combo"])
        if not sr.exists():
            return {"error": f"right source not found: {sr}"}
        cache_r = cache_path_for_source(sr)
        cache_r.parent.mkdir(parents=True, exist_ok=True)

    # Parse source files (raw generator lists) into proper SUBGROUPS := [...] form.
    def write_subs_g(out_path, subs_list):
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("SUBGROUPS := [\n")
            for i, s in enumerate(subs_list):
                sep = "," if i < len(subs_list) - 1 else ""
                f.write(f"  Group({s}){sep}\n")
            f.write("];\n")
    subs_l_g = work / "subs_left.g"
    write_subs_g(subs_l_g, parse_combo_file(sl))
    subs_r_g = work / "subs_right.g"
    if sr:
        write_subs_g(subs_r_g, parse_combo_file(sr))
    else:
        subs_r_g.write_text("# right side is TG(d,t); SUBS_RIGHT_PATH unused\n",
                            encoding="utf-8")

    log = work / "run.log"
    if log.exists(): log.unlink()
    # If output_path is given, generators are needed.
    if output_path is not None:
        emit_generators = True
    gen_path = (work / "fps.g") if emit_generators else None
    if gen_path is not None and gen_path.exists(): gen_path.unlink()

    left_part = partition_from_source(inputs["left_combo"])
    if inputs["right_tg"] is not None:
        right_part = [inputs["right_tg"][0]]
    elif inputs["right_combo"] is not None:
        right_part = partition_from_source(inputs["right_combo"])
    else:
        right_part = [inputs["m_right"]]

    run_g = work / "run.g"
    run_g.write_text(
        GAP_DRIVER
        .replace("__LOG__", to_cyg(log))
        .replace("__M_LEFT__", str(inputs["m_left"]))
        .replace("__M_RIGHT__", str(inputs["m_right"]))
        .replace("__M_LEFT_PARTITION__", "[" + ",".join(str(d) for d in left_part) + "]")
        .replace("__M_RIGHT_PARTITION__", "[" + ",".join(str(d) for d in right_part) + "]")
        .replace("__SUBS_L__", to_cyg(subs_l_g))
        .replace("__SUBS_R__", to_cyg(subs_r_g) if sr else "")
        .replace("__CACHE_L__", to_cyg(cache_l))
        .replace("__CACHE_R__", to_cyg(cache_r) if cache_r else "")
        .replace("__TG_D__", str(inputs["right_tg"][0]) if inputs["right_tg"] else "0")
        .replace("__TG_T__", str(inputs["right_tg"][1]) if inputs["right_tg"] else "0")
        .replace("__BURNSIDE_M2__", "1" if inputs["burnside_m2"] else "0")
        .replace("__GEN_PATH__", to_cyg(gen_path) if gen_path else ""),
        encoding="utf-8"
    )

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 -L "{LIFTING_WS_CYG}" "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    try:
        _gap_run(cmd, env, timeout, diag_dir=work)
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "elapsed_s": time.time() - t0}
    elapsed = round(time.time() - t0, 1)
    log_text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    m = re.search(r"RESULT predicted=\s*(\d+)\s+orbits=\s*(\d+)\s+swap_fixed=\s*(\d+)", log_text)
    if not m:
        return {"error": "no RESULT", "log_tail": log_text[-2000:], "elapsed_s": elapsed}
    out = {
        "combo": combo_filename(combo),
        "mode": mode,
        "predicted": int(m.group(1)),
        "orbits": int(m.group(2)),
        "swap_fixed": int(m.group(3)),
        "elapsed_s": elapsed,
        "left_combo": combo_filename(inputs["left_combo"]),
        "right": (f"TG({inputs['right_tg'][0]},{inputs['right_tg'][1]})"
                  if inputs["right_tg"] else combo_filename(inputs["right_combo"])),
        "m_left": inputs["m_left"],
        "m_right": inputs["m_right"],
    }
    if emit_generators and gen_path:
        out["generators_file"] = str(gen_path)
    # Compose legacy-format file at output_path if requested.
    if output_path is not None and gen_path is not None and gen_path.exists():
        raw_lines = gen_path.read_text(encoding="utf-8").splitlines(keepends=False)
        elapsed_ms = int(elapsed * 1000)
        n_written = _write_legacy_format(Path(output_path), combo, raw_lines,
                                          out["predicted"], elapsed_ms)
        if n_written != out["predicted"]:
            out["warning_count_mismatch"] = (
                f"wrote {n_written} generator lines but predicted={out['predicted']}")
        out["output_path"] = str(output_path)
    result_path.write_text(json.dumps(out, indent=2))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", help="JSON file with list of jobs sharing LEFT source")
    ap.add_argument("--super-batch",
                    help="JSON file with list of GROUPS, each group has its own LEFT")
    ap.add_argument("--combo")
    ap.add_argument("--mode", default="auto",
                    choices=["auto", "distinguished", "holt_split", "burnside_m2"])
    ap.add_argument("--emit-generators", action="store_true")
    ap.add_argument("--output-path",
                    help="write legacy-format combo file here (implies --emit-generators)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()
    if args.super_batch:
        sb_data = json.load(open(args.super_batch))
        # sb_data: {"groups": [{"left_combo": [...], "jobs": [...]}, ...]}
        groups = []
        for g in sb_data["groups"]:
            jobs = []
            for j in g["jobs"]:
                c = j["combo"]
                if isinstance(c, str): c = parse_combo_str(c)
                else: c = tuple(sorted((int(d), int(t)) for d, t in c))
                jobs.append({"combo": c, "mode": j["mode"],
                             "output_path": j["output_path"]})
            lc = g["left_combo"]
            if isinstance(lc, str): lc = parse_combo_str(lc)
            else: lc = tuple(sorted((int(d), int(t)) for d, t in lc))
            groups.append({"left_combo": lc, "jobs": jobs})
        results = predict_super_batch(groups, force=args.force, timeout=args.timeout)
        print(json.dumps(results, indent=2))
        return
    if args.batch:
        jobs_data = json.load(open(args.batch))
        # Each entry: {combo: str_or_tuple, mode: str, output_path: str}
        jobs = []
        for j in jobs_data:
            c = j["combo"]
            if isinstance(c, str): c = parse_combo_str(c)
            else: c = tuple(sorted((int(d), int(t)) for d, t in c))
            jobs.append({"combo": c, "mode": j["mode"],
                         "output_path": j["output_path"]})
        results = predict_batch(jobs, force=args.force, timeout=args.timeout)
        print(json.dumps(results, indent=2))
        return
    if not args.combo:
        ap.error("--combo required when --batch not given")
    result = predict(args.combo, mode=args.mode,
                     emit_generators=args.emit_generators,
                     output_path=args.output_path,
                     force=args.force, timeout=args.timeout)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
