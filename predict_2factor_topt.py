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

ROOT = Path(__file__).resolve().parent
SN_DIR = Path(os.environ.get("PREDICT_SN_DIR", str(ROOT / "parallel_sn")))
S18_DIR = ROOT / "parallel_s18"
TMP = Path(os.environ.get("PREDICT_TMP_DIR",
                          str(ROOT / "predict_species_tmp" / "_two_factor")))
TMP.mkdir(parents=True, exist_ok=True)
H_CACHE_DIR = Path(os.environ.get("PREDICT_H_CACHE_DIR",
                                   str(ROOT / "predict_species_tmp" / "_h_cache")))
H_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Meta-catalog path (catalog-driven QT discovery; Item 1).  Populated by
# `seed_meta_catalog.py`.  When the file does not exist, the GAP code in
# ComputeOrLoadLeftQGroups falls back to the legacy NormalSubgroups discovery
# path automatically (passing an empty path == "no catalog configured").
META_CATALOG_PATH = H_CACHE_DIR / "_meta_q_catalog" / "q_catalog.g"

# Opt 2 (2026-05-09): persistent SafeId(H) -> qid-list cache.  Master file is
# read by every worker; per-session fragments are written to the fragments/
# subdir and merged into the master by the orchestrator.
H_TO_QS_MASTER_PATH = H_CACHE_DIR / "_meta_q_catalog" / "h_to_qs.g"
H_TO_QS_FRAGMENTS_DIR = H_CACHE_DIR / "_meta_q_catalog" / "fragments"

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


def to_gap(p) -> str:
    """Windows-style path syntax for paths embedded inside GAP source."""
    return str(p).replace("\\", "/")


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
        f'Read("{to_gap(LIFTING_G)}");\n'
        f'SaveWorkspace("{to_gap(LIFTING_WS)}");\n'
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
    if mult >= 3:
        # Single-cluster m>=3: try Holt-style multiplicity split (a + b with a<b).
        # Output of the split is N_LEFT x N_RIGHT-deduped; final count may need
        # an additional dedup pass under the full N_{S_n}(partition).
        return "holt_split"
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
            # Prefer smaller n_subs (cheaper H-cache build).  The per-(d,t)
            # RIGHT-side Q-discovery refactor (one NormalSubgroups call per
            # right TG group) makes Q-discovery cheap regardless of m_right,
            # so n_subs dominates again as in v2.
            m_left = sum(d for d, _ in c_prime)
            if best is None or (n_subs, m_left) < (best[2], best[3]):
                best = (dt, c_prime, n_subs, m_left)
        if best is None:
            raise FileNotFoundError("no distinguished pivot has a source file")
        dt, c_prime, _, _ = best
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
        species = sorted(clusters.keys())
        k = len(species)
        best = None
        # Inter-species splits: each cluster goes entirely to one side.
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
        # Intra-cluster (single-cluster) multiplicity splits: a + b with a<b.
        # Only enabled for k=1 currently; extends Holt's split-and-Goursat to
        # single-species combos that would otherwise route to materialize+RA.
        if k == 1:
            sp = species[0]
            mult = clusters[sp]
            # PREDICT_FORCE_SPLIT_A=N overrides the min-nl*nr selection for
            # single-cluster combos.  Use when an alternate split has
            # workload-shape advantages the cost model doesn't capture
            # (e.g., RIGHT=single-species reuses heavily-extended LEFT cache).
            forced_a = os.environ.get("PREDICT_FORCE_SPLIT_A")
            if forced_a is not None:
                try:
                    a = int(forced_a)
                    if 1 <= a < mult and a != mult - a:
                        b = mult - a
                        left = tuple([sp] * a)
                        right = tuple([sp] * b)
                        sl, sr = source_path(left), source_path(right)
                        if sl.exists() and sr.exists():
                            print(f"[resolve_inputs] PREDICT_FORCE_SPLIT_A={a}: "
                                  f"forcing ({a},{b}) split",
                                  file=sys.stderr)
                            nl, nr = (len(parse_combo_file(sl)),
                                      len(parse_combo_file(sr)))
                            best = (nl * nr, left, right)
                except ValueError:
                    pass
            if best is None:   # no force, or force failed -> pick by min nl*nr
                for a in range(1, mult // 2 + 1):
                    b = mult - a
                    if a == b: continue   # equal split: needs Burnside-on-cluster fix
                    left = tuple([sp] * a)
                    right = tuple([sp] * b)
                    sl, sr = source_path(left), source_path(right)
                    if not (sl.exists() and sr.exists()): continue
                    nl, nr = len(parse_combo_file(sl)), len(parse_combo_file(sr))
                    if best is None or nl * nr < best[0]:
                        best = (nl * nr, left, right)
        if best is None:
            raise FileNotFoundError("no valid Holt split found")
        _, left, right = best
        # Auto-swap LEFT/RIGHT for combos with all parts <= 4.  In that
        # regime the bigger-m side typically has a cached H_CACHE from prior
        # n=14-19 builds, and the smaller-m side's RIGHT-derived Q-set is
        # tiny -- so putting the cached side on LEFT reuses prior work while
        # the cache extension stays cheap.
        # PREDICT_FORCE_SWAP_LR=1 also forces the swap unconditionally.
        partition = sorted([d for d, _ in combo], reverse=True)
        auto_swap = all(d <= 4 for d in partition)
        force_swap = os.environ.get("PREDICT_FORCE_SWAP_LR") == "1"
        if auto_swap or force_swap:
            # Only swap if it would actually move work to a side with a
            # larger source (the cache reuse argument).  If left already has
            # the bigger source, swapping would be a no-op or pessimization.
            left_n_subs = len(parse_combo_file(source_path(left)))
            right_n_subs = len(parse_combo_file(source_path(right)))
            if right_n_subs > left_n_subs:
                left, right = right, left
                reason = "PREDICT_FORCE_SWAP_LR" if force_swap else "auto-swap (all parts <= 4)"
                print(f"[resolve_inputs] {reason}: swapped to "
                      f"LEFT={left} RIGHT={right}", file=sys.stderr)
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
META_CATALOG_PATH := "__META_CATALOG__";
H_TO_QS_MASTER_PATH := "__H_TO_QS_MASTER__";
H_TO_QS_FRAGMENT_PATH := "__H_TO_QS_FRAGMENT__";
H_TO_QS_FRAGMENTS_DIR := "__H_TO_QS_FRAGMENTS_DIR__";
RIGHT_TG_D    := __TG_D__;       # 0 if right side is a source list
RIGHT_TG_T    := __TG_T__;
BURNSIDE_M2   := __BURNSIDE_M2__;   # 0 or 1
EMIT_GENS_PATH := "__GEN_PATH__";
STATE_FILE    := "__STATE_FILE__";   # checkpoint state path; "" disables
CHECKPOINT_INTERVAL_MS := __CHECKPOINT_INTERVAL_MS__;
STATE_SAVE_INTERVAL_MS := __STATE_SAVE_INTERVAL_MS__;
LAST_STATE_SAVE_MS := 0;
EXTEND_ONLY    := __EXTEND_ONLY__;   # 1 = exit after cache extension+save (skip emit)
# Cut 3: when 1, ExtendHCacheEntry / ComputeHCacheEntry / ComputeHDataDirect
# dispatch to LinearOrbitRecsCpa / LinearOrbitRecsD8 (Stage A/B prototypes)
# for qids in {C_2, V_4, D_8}, producing N_H-orbit records directly without
# enumerating-all-kernels-then-orbiting.  Other qids fall back to the legacy
# _EnumerateNormalsForQGroups + _ComputeOrbitRecsFromKs path.  Default ON;
# set env var PRED_USE_LINEAR_ORBITS=0 to force legacy path for a single run.
USE_LINEAR_ORBITS := __USE_LINEAR_ORBITS__;
if USE_LINEAR_ORBITS = 1 then
    Print("[USE_LINEAR_ORBITS=1] loading Stage A/B prototypes...\n");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_a.g");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_b.g");
fi;
BENCH_PHASES   := __BENCH_PHASES__;
BENCH_PHASES_OUT := "__BENCH_PHASES_OUT__";
BENCH_T := rec(t_iso := 0, t_ensure := 0, t_a1a2 := 0, t_dc := 0, t_swap := 0,
               t_emit_qsize1 := 0, t_emit_c2_fast := 0, t_emit_c2_safe := 0,
               t_emit_general := 0, t_shifted_hom := 0,
               t_grp_construct := 0, t_emit_write := 0,
               t_c2safe_shifted_hom := 0, t_c2safe_gbfp := 0,
               t_c2safe_emit_write := 0);
BENCH_N := rec(n_pairs := 0, n_saturated := 0, n_dc_call := 0,
               n_dc_orbits_total := 0, n_emit := 0, n_c2_safe_invocations := 0,
               n_dc_cache_hits := 0, n_dc_cache_misses := 0);
# Opt #5 canonical-Q registry.  qid_str -> rec(Q := canonical_Q,
# AutQ := Aut(Qcan)).  Populated lazily by EnsureAutQ.
QCAN_TABLE := rec();
WORKER_START := Runtime();

# Resume state — set by reading STATE_FILE if it exists.  Python wrapper has
# already truncated EMIT_GENS_PATH to the byte position right after the last
# "# checkpoint" marker line for the (i, j) we're resuming from.
i_resume_start := 1;
j_resume_start := 1;
resume_total_orb := 0;
resume_total_fix := 0;
if STATE_FILE <> "" and IsExistingFile(STATE_FILE) then
    Read(STATE_FILE);
    if IsBound(RESUME_STATE) then
        i_resume_start := RESUME_STATE.i;
        j_resume_start := RESUME_STATE.j;
        if IsBound(RESUME_STATE.total_orb) then
            resume_total_orb := RESUME_STATE.total_orb;
        fi;
        if IsBound(RESUME_STATE.total_fix) then
            resume_total_fix := RESUME_STATE.total_fix;
        fi;
        Print("RESUMING from i=", i_resume_start, " j=", j_resume_start,
              " orb=", resume_total_orb, "\n");
    fi;
fi;

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

# === META catalog + H-iso -> Q-iso cache (Opts 1+2, 2026-05-09) ===========
# Opt 1: avoid re-reading the 6065-entry q_catalog.g per ComputeOrLoadLeftQGroups
#        call within a single GAP session.  _META_CATALOG_LOADED_PATH holds
#        the path that was loaded into the global META_Q_CATALOG; subsequent
#        calls with the same path reuse the in-memory list.
# Opt 2: file-based per-H-iso QT cache.  Master file h_to_qs.g shared across
#        all super-batches and orchestrator runs; workers READ master,
#        accumulate new entries in _META_H_TO_QS_NEW, write per-session
#        fragments, orchestrator merges fragments into master.
#        H_TO_QS lookup is keyed by SafeId(H) string.  Only safe iso-classes
#        (h_id[2] = 0) are cached; unsafe (heuristic SafeId) bypass cache.
if not IsBound(_META_CATALOG_LOADED_PATH) then
    _META_CATALOG_LOADED_PATH := "";
fi;
if not IsBound(_META_H_TO_QS_LOADED_PATH) then
    _META_H_TO_QS_LOADED_PATH := "";
fi;
if not IsBound(_META_H_TO_QS_RECORD) then
    _META_H_TO_QS_RECORD := rec();   # sanitized-key -> qid list
fi;
if not IsBound(_META_H_TO_QS_NEW) then
    _META_H_TO_QS_NEW := [];          # list of [h_id_str, [qid, ...]]
fi;

# Convert SafeId(H) string (e.g. "[ 36, 0, [ 36, 3 ] ]") to a valid GAP
# record-field identifier by stripping spaces/brackets.  Deterministic and
# collision-free for SafeId outputs.
SanitizeHidStr := function(s)
    local out, c;
    out := "h";
    for c in s do
        if c = ' ' or c = ',' then Add(out, '_');
        elif c = '[' or c = ']' then ;
        else Add(out, c);
        fi;
    od;
    return out;
end;

# Load master catalog from path; cache in METAQCATALOG global.  Skip disk
# read if already loaded from same path in this GAP session.
_LoadMasterCatalog := function(path)
    if path = "" then return fail; fi;
    if _META_CATALOG_LOADED_PATH = path and IsBound(META_Q_CATALOG) then
        return META_Q_CATALOG;
    fi;
    if not IsExistingFile(path) then return fail; fi;
    META_Q_CATALOG_SAVED_OK := false;
    Read(path);
    if IsBound(META_Q_CATALOG_SAVED_OK) and META_Q_CATALOG_SAVED_OK = true
       and IsBound(META_Q_CATALOG) then
        _META_CATALOG_LOADED_PATH := path;
        Print("[QGroups] loaded master catalog: ", Length(META_Q_CATALOG),
              " types from ", path, "\n");
        return META_Q_CATALOG;
    fi;
    Print("[QGroups] master catalog file present but invalid sentinel - ignoring\n");
    return fail;
end;

# Load h_to_qs master file (a list of [h_id_str, qid_list] pairs).  Builds
# an in-memory record keyed by SanitizeHidStr(h_id_str) for O(log) lookup.
# Idempotent within a GAP session (only re-reads if path differs).  Also
# loads pending fragments produced by other workers in this run.
_LoadHToQs := function(master_path, fragments_dir)
    local rec_obj, entry, key, fragments, fpath, frag_count, frag_added;
    if _META_H_TO_QS_LOADED_PATH = master_path and master_path <> "" then
        return _META_H_TO_QS_RECORD;
    fi;
    rec_obj := rec();
    if master_path <> "" and IsExistingFile(master_path) then
        META_H_TO_QS_SAVED_OK := false;
        META_H_TO_QS := [];
        Read(master_path);
        if IsBound(META_H_TO_QS_SAVED_OK) and META_H_TO_QS_SAVED_OK = true
           and IsBound(META_H_TO_QS) then
            for entry in META_H_TO_QS do
                key := SanitizeHidStr(entry[1]);
                rec_obj.(key) := entry[2];
            od;
            Print("[QGroups] loaded H_TO_QS master: ",
                  Length(META_H_TO_QS), " entries from ", master_path, "\n");
        fi;
    fi;
    # Also pre-merge any fragments that have not yet been consolidated.
    # Workers in the current run may have written fragments before this
    # worker started; reading them gives in-process cache hits.
    frag_count := 0;
    frag_added := 0;
    if fragments_dir <> "" and IsDirectoryPath(fragments_dir) then
        fragments := DirectoryContents(fragments_dir);
        for fpath in fragments do
            if Length(fpath) >= 2 and fpath{[Length(fpath)-1..Length(fpath)]} = ".g" then
                META_H_TO_QS_NEW_SAVED_OK := false;
                META_H_TO_QS_NEW := [];
                Read(Concatenation(fragments_dir, "/", fpath));
                if IsBound(META_H_TO_QS_NEW_SAVED_OK) and META_H_TO_QS_NEW_SAVED_OK = true then
                    frag_count := frag_count + 1;
                    for entry in META_H_TO_QS_NEW do
                        key := SanitizeHidStr(entry[1]);
                        if not IsBound(rec_obj.(key)) then
                            rec_obj.(key) := entry[2];
                            frag_added := frag_added + 1;
                        fi;
                    od;
                fi;
            fi;
        od;
        if frag_count > 0 then
            Print("[QGroups] absorbed ", frag_count, " fragment(s) -> ",
                  frag_added, " new H entries\n");
        fi;
    fi;
    _META_H_TO_QS_LOADED_PATH := master_path;
    _META_H_TO_QS_RECORD := rec_obj;
    # Reset the new-entries accumulator for THIS session (we never re-emit
    # entries we just absorbed from fragments).
    _META_H_TO_QS_NEW := [];
    return _META_H_TO_QS_RECORD;
end;

# Append _META_H_TO_QS_NEW to a fragment file (atomic tmp+mv).  Caller is
# responsible for clearing _META_H_TO_QS_NEW after a successful write if it
# wants to avoid double-emitting on subsequent calls in the same session.
_SaveHToQsFragment := function(fragment_path)
    local tmp;
    if fragment_path = "" or Length(_META_H_TO_QS_NEW) = 0 then return; fi;
    tmp := Concatenation(fragment_path, ".tmp");
    PrintTo(tmp, "META_H_TO_QS_NEW := ", _META_H_TO_QS_NEW, ";\n",
                 "META_H_TO_QS_NEW_SAVED_OK := true;\n");
    Exec(Concatenation("mv -f -- '", tmp, "' '", fragment_path, "'"));
    Print("[QGroups] saved H_TO_QS fragment: ", Length(_META_H_TO_QS_NEW),
          " new entries -> ", fragment_path, "\n");
end;

# Cache the SUBS_RIGHT walk: walking each R in subs_right.g and enumerating
# `for K in NormalSubgroups(R)` to get the Q-types of the right side.  Cache
# is keyed by cache_right_path (stable across runs).  Sidecar file is
# <cache_right_path>.right_qgroups.g; sentinel RIGHT_QGROUPS_FROM_SUBS_SAVED_OK.
LoadOrComputeRightQGroupsFromSubs := function(subs_right_path, cache_right_path)
    local sidecar, tmp, R, K, Q, qid, seen, result;
    if subs_right_path = "" then return []; fi;
    if cache_right_path <> "" then
        sidecar := Concatenation(cache_right_path, ".right_qgroups.g");
        if IsExistingFile(sidecar) then
            RIGHT_QGROUPS_FROM_SUBS_SAVED_OK := false;
            Read(sidecar);
            if IsBound(RIGHT_QGROUPS_FROM_SUBS_SAVED_OK) and RIGHT_QGROUPS_FROM_SUBS_SAVED_OK = true
               and IsBound(RIGHT_QGROUPS_FROM_SUBS) then
                Print("[QGroups] loaded RIGHT-derived qgroups from cache: ",
                      Length(RIGHT_QGROUPS_FROM_SUBS), " types from ", sidecar, "\n");
                return RIGHT_QGROUPS_FROM_SUBS;
            fi;
        fi;
    else
        sidecar := "";
    fi;
    Read(subs_right_path);
    result := [];
    seen := Set([]);
    for R in SUBGROUPS do
        for K in NormalSubgroups(R) do
            if Size(K) = Size(R) then continue; fi;
            Q := R/K;
            qid := SafeId(Q);
            if not (qid in seen) then
                AddSet(seen, qid);
                Add(result, Q);
            fi;
        od;
    od;
    # Normalize FactorGroup objects (their abstract f1, f2 generator names
    # would not be re-bindable on Read of the cached sidecar).
    result := List(result, function(q)
        local n, q_id;
        n := Size(q);
        if IdGroupsAvailable(n) then
            q_id := IdGroup(q);
            return SmallGroup(n, q_id[2]);
        else
            return Image(IsomorphismPermGroup(q));
        fi;
    end);
    if sidecar <> "" then
        tmp := Concatenation(sidecar, ".tmp");
        PrintTo(tmp, "RIGHT_QGROUPS_FROM_SUBS := ", result, ";\n",
                     "RIGHT_QGROUPS_FROM_SUBS_SAVED_OK := true;\n");
        Exec(Concatenation("mv -f -- '", tmp, "' '", sidecar, "'"));
        Print("[QGroups] saved RIGHT-derived qgroups: ", Length(result),
              " types -> ", sidecar, "\n");
    fi;
    return result;
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
if not IsBound(_GoursatBuildFiberProduct) then Read("__LIFTING_G__"); fi;

# Reconstruct H-side data with Aut(Q) and induced auto generators from a
# cached entry.  Cache shape: rec(H_gens, N_H_gens, orbits := [rec(K_H_gens,
# Stab_NH_KH_gens, qsize, qid)]).  Adds the trivial-Q (K = H) entry that the
# cache file omits.
ReconstructHData := function(entry, S_M)
    local H, N, res, orbit_data, K, Stab, i, key, hom_triv;
    H := SafeGroup(entry.H_gens, S_M);
    N := SafeGroup(entry.N_H_gens, S_M);
    res := rec(H := H, N := N,
        H_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_H := fail, shifted_H_gens_noid := fail,
        orbits := []);
    # Trivial-quotient orbit (always present; hom is fast for H/H).
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N, AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
        K_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_K_gens_noid := fail, c2_rep := fail, shifted_c2_rep := fail,
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
            Stab := Stab, AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
            K_gens_noid := Filtered(GeneratorsOfGroup(K), g -> g <> ()),
            shifted_K_gens_noid := fail, c2_rep := fail, shifted_c2_rep := fail,
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
    local qid_str, can_entry, raw_a_gens;
    if orb.AutQ <> fail then return; fi;
    if orb.qsize <= 1 then return; fi;   # trivial Q has no auto
    EnsureHom(orb);   # AutQ depends on Q
    # Opt #5: canonical Q registry.  First orbit with a given qid registers
    # its Q + AutQ as canonical.  Subsequent orbits compute iso_to_can and
    # share the canonical AutQ.  A_gens are transported to canonical Aut(Q).
    qid_str := String(orb.qid);
    if not IsBound(QCAN_TABLE.(qid_str)) then
        QCAN_TABLE.(qid_str) := rec(Q := orb.Q, AutQ := AutomorphismGroup(orb.Q));
        orb.iso_to_can := IdentityMapping(orb.Q);
    else
        can_entry := QCAN_TABLE.(qid_str);
        orb.iso_to_can := IsomorphismGroups(orb.Q, can_entry.Q);
        if orb.iso_to_can = fail then
            # Should not happen: matching qid implies iso classes match.  Fall
            # back to fresh AutQ + identity to avoid runtime error; A_gens
            # below stay in orb.Q's Aut, so canonical sharing won't apply.
            QCAN_TABLE.(qid_str) := rec(Q := orb.Q, AutQ := AutomorphismGroup(orb.Q));
            orb.iso_to_can := IdentityMapping(orb.Q);
        fi;
    fi;
    can_entry := QCAN_TABLE.(qid_str);
    orb.AutQ := can_entry.AutQ;
    raw_a_gens := InducedAutoGens(orb.Stab, orb.H_ref, orb.hom);
    orb.A_gens := List(raw_a_gens, a -> InducedAutomorphism(orb.iso_to_can, a));
    # Optimization (3) 2026-04-28: cache full_aut.
    if Length(orb.A_gens) = 0 then
        orb.full_aut := false;
    else
        orb.full_aut := (Size(Subgroup(orb.AutQ, orb.A_gens)) = Size(orb.AutQ));
    fi;
end;

# Opt #1: lazily compute and cache the shifted-right quotient hom
# on h2orb.shifted_hom.  Used by C2-safe and general emit paths to
# skip rebuilding CompositionMapping(orb.hom, ConjugatorIsomorphism(
# H2_shifted, shift_R^-1)) on every emission.  Within one predict()
# call, H2_shifted is fixed for a given h2orb (parent H2data.H +
# file-global shift_R), so safe to reuse.
EnsureShiftedHom := function(orb, H2_shifted)
    if orb.shifted_hom <> fail then return; fi;
    EnsureHom(orb);
    orb.shifted_hom := CompositionMapping(orb.hom,
        ConjugatorIsomorphism(H2_shifted, shift_R^-1));
end;

EnsureShiftedHData := function(Hdata)
    if Hdata.shifted_H <> fail then return; fi;
    Hdata.shifted_H := Hdata.H^shift_R;
    Hdata.shifted_H_gens_noid := List(Hdata.H_gens_noid, g -> g^shift_R);
end;

EnsureShiftedKGenerators := function(orb)
    if orb.shifted_K_gens_noid <> fail then return; fi;
    orb.shifted_K_gens_noid := List(orb.K_gens_noid, g -> g^shift_R);
end;

EnsureC2Representative := function(orb)
    if orb.c2_rep <> fail then return; fi;
    orb.c2_rep := First(GeneratorsOfGroup(orb.H_ref),
                         g -> not (g in orb.K));
end;

EnsureShiftedC2Representative := function(orb)
    if orb.shifted_c2_rep <> fail then return; fi;
    EnsureC2Representative(orb);
    orb.shifted_c2_rep := orb.c2_rep^shift_R;
end;

# Opt #4: cache DoubleCosets results per h1orb keyed by the A2_in_h1
# subgroup.  Linear-list lookup; comparison via group equality.  Cache
# grows with distinct A2_in_h1 subgroups seen for this h1orb (bounded
# by the number of distinct quotient/iso classes among matching h2orbs).
LookupOrComputeDC := function(h1orb, A1, A2_in_h1)
    local entry, dcs;
    if h1orb.dc_cache = fail then h1orb.dc_cache := []; fi;
    for entry in h1orb.dc_cache do
        if entry[1] = A2_in_h1 then
            if BENCH_PHASES = 1 then BENCH_N.n_dc_cache_hits := BENCH_N.n_dc_cache_hits + 1; fi;
            return entry[2];
        fi;
    od;
    if BENCH_PHASES = 1 then BENCH_N.n_dc_cache_misses := BENCH_N.n_dc_cache_misses + 1; fi;
    dcs := DoubleCosets(h1orb.AutQ, A2_in_h1, A1);
    Add(h1orb.dc_cache, [A2_in_h1, dcs]);
    return dcs;
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
    local result, seen, t, T, K, Q, qid, key, cache_path, slash, i, t0;
    # Two-tier cache: in-memory (per-GAP-session) + file (across sessions).
    # Without caching, NrTransitiveGroups(MR)=301 at MR=12 forces a ~hour-long
    # walk on every call, multiplied by hundreds of per-job invocations.
    if not IsBound(_REQUIRED_QGROUPS_CACHE) then _REQUIRED_QGROUPS_CACHE := rec(); fi;
    key := Concatenation("m", String(M_R));
    if IsBound(_REQUIRED_QGROUPS_CACHE.(key)) then
        return _REQUIRED_QGROUPS_CACHE.(key);
    fi;
    # File cache: <META_CATALOG_PATH-dir>/required_qgroups_m<MR>.g
    cache_path := "";
    if IsBound(META_CATALOG_PATH) and META_CATALOG_PATH <> "" then
        slash := 0;
        for i in [Length(META_CATALOG_PATH), Length(META_CATALOG_PATH)-1..1] do
            if META_CATALOG_PATH[i] = '/' then slash := i; break; fi;
        od;
        if slash > 0 then
            cache_path := Concatenation(
                META_CATALOG_PATH{[1..slash]},
                "required_qgroups_m", String(M_R), ".g");
        fi;
    fi;
    if cache_path <> "" and IsExistingFile(cache_path) then
        REQUIRED_QGROUPS_CACHED_SAVED_OK := false;
        Read(cache_path);
        if IsBound(REQUIRED_QGROUPS_CACHED_SAVED_OK) and REQUIRED_QGROUPS_CACHED_SAVED_OK = true
           and IsBound(REQUIRED_QGROUPS_CACHED) then
            _REQUIRED_QGROUPS_CACHE.(key) := REQUIRED_QGROUPS_CACHED;
            Print("[RequiredQGroups] loaded from file cache: ",
                  Length(REQUIRED_QGROUPS_CACHED), " types for M_R=", M_R, "\n");
            return REQUIRED_QGROUPS_CACHED;
        fi;
    fi;
    # Compute
    result := [];
    seen := Set([]);
    if M_R = 0 then
        _REQUIRED_QGROUPS_CACHE.(key) := result;
        return result;
    fi;
    t0 := Runtime();
    Print("[RequiredQGroups] computing for M_R=", M_R, " (",
          NrTransitiveGroups(M_R), " transitive groups)...\n");
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
    # Normalize for safe re-Read (FactorGroup uses unbound generator names).
    result := List(result, function(q)
        local n, q_id;
        n := Size(q);
        if IdGroupsAvailable(n) then
            q_id := IdGroup(q);
            return SmallGroup(n, q_id[2]);
        else
            return Image(IsomorphismPermGroup(q));
        fi;
    end);
    Print("[RequiredQGroups] computed M_R=", M_R, ": ", Length(result),
          " types in ", Runtime() - t0, "ms\n");
    if cache_path <> "" then
        PrintTo(Concatenation(cache_path, ".tmp"),
                "REQUIRED_QGROUPS_CACHED := ", result, ";\n",
                "REQUIRED_QGROUPS_CACHED_SAVED_OK := true;\n");
        Exec(Concatenation("mv -f -- '", cache_path, ".tmp' '", cache_path, "'"));
        Print("[RequiredQGroups] saved file cache for M_R=", M_R, "\n");
    fi;
    _REQUIRED_QGROUPS_CACHE.(key) := result;
    return result;
end;

# Q-iso classes attainable as nontrivial quotients of any group in `groups`.
# Used to derive a TIGHT LEFT_Q_GROUPS filter: in Goursat's theorem the common
# quotient Q must be a quotient of BOTH factors, so deriving Q-types from the
# LEFT subgroup list is at least as tight as RequiredQGroups(M_R) and is
# DRAMATICALLY tighter when M_R >= 6 (where RequiredQGroups returns `fail` =
# full coverage, forcing NormalSubgroups(H) on every right-side H).
QuotientTypesOfGroups := function(arg)
    # Discovers Q-types achievable as H/K for some H in `groups`.
    #
    # When called with one argument (legacy): runs `for K in NormalSubgroups(H)`
    # discovery with iso-class dedup.  Can hang for hours on hostile H entries
    # (observed in S20 production).
    #
    # When called with two arguments (catalog-driven): iterates the master
    # catalog and uses `HasQuotientType(H, Q)` as a sound prefilter.  Never
    # calls `NormalSubgroups(H)` -- bounded runtime.  Result is a SUPERSET of
    # actually-achievable Q's (false positives from HasQuotientType returning
    # true for non-pgroup Q are filtered out at cache-build time by
    # `_EnumerateNormalsForQGroups`).
    #
    # When called with three arguments: third arg is a SafeId-keyed record of
    # already-known H-iso -> qid-list mappings (the META_H_TO_QS cache).  On
    # cache hit for a safe H, skips the catalog sweep and uses cached qids.
    # On miss, runs the sweep and appends the new entry to _META_H_TO_QS_NEW.
    #
    # Iso-class dedup is gated on SafeId(H)[2] = 0 in all paths.
    local groups, master_catalog, h_to_qs, result, seen_qids, seen_h_ids,
          n_total, idx, last_qt_hb, H, h_id, h_id_str, h_id_san, K, Q, q,
          qid, n_skipped, n_safe, master_qids, q_idx, h_size, q_size,
          cached_qids, hit_qids, n_cache_hit, n_cache_miss, qid_to_pos,
          pos;
    groups := arg[1];
    if Length(arg) >= 2 then master_catalog := arg[2]; else master_catalog := fail; fi;
    if Length(arg) >= 3 then h_to_qs := arg[3]; else h_to_qs := fail; fi;
    result := [];
    seen_qids := Set([]);
    seen_h_ids := Set([]);
    n_total := Length(groups);
    last_qt_hb := Runtime();
    idx := 0;
    n_skipped := 0;
    n_safe := 0;
    n_cache_hit := 0;
    n_cache_miss := 0;

    if master_catalog <> fail and Length(master_catalog) > 0 then
        # Catalog-driven path.  Iterates each H against master_catalog using
        # the cheap HasQuotientType structural check.  master_catalog is
        # expected in ascending size order (as seeded by seed_meta_catalog.py),
        # which lets us break the inner loop once Size(Q) > Size(H).
        Print("    [QuotientTypesOfGroups] catalog-driven: |catalog|=",
              Length(master_catalog), " |groups|=", n_total, "\n");
        master_qids := List(master_catalog, SafeId);
        # Index from String(qid) to position in master_catalog for O(1)
        # cache-hit lookup (avoids linear search per cached qid).
        qid_to_pos := rec();
        for q_idx in [1..Length(master_qids)] do
            qid_to_pos.(SanitizeHidStr(String(master_qids[q_idx]))) := q_idx;
        od;
        for H in groups do
            idx := idx + 1;
            if Runtime() - last_qt_hb >= 60000 then
                Print("    [QuotientTypesOfGroups] progress ", idx, "/", n_total,
                      " types=", Length(result),
                      " H_iso=", Length(seen_h_ids),
                      " safe_dedup=", n_skipped,
                      " unsafe=", n_safe,
                      " cache_hit=", n_cache_hit,
                      " cache_miss=", n_cache_miss, "\n");
                last_qt_hb := Runtime();
            fi;
            h_id := SafeId(H);
            h_id_san := "";
            if h_id[2] = 0 then
                h_id_str := String(h_id);
                if h_id_str in seen_h_ids then
                    n_skipped := n_skipped + 1;
                    continue;
                fi;
                AddSet(seen_h_ids, h_id_str);
                h_id_san := SanitizeHidStr(h_id_str);
                # Opt 2: cache hit on H iso-class
                if h_to_qs <> fail and IsBound(h_to_qs.(h_id_san)) then
                    cached_qids := h_to_qs.(h_id_san);
                    n_cache_hit := n_cache_hit + 1;
                    for qid in cached_qids do
                        if qid in seen_qids then continue; fi;
                        AddSet(seen_qids, qid);
                        pos := 0;
                        if IsBound(qid_to_pos.(SanitizeHidStr(String(qid)))) then
                            pos := qid_to_pos.(SanitizeHidStr(String(qid)));
                        fi;
                        if pos > 0 then Add(result, master_catalog[pos]); fi;
                    od;
                    continue;
                fi;
                n_cache_miss := n_cache_miss + 1;
            else
                n_safe := n_safe + 1;
            fi;
            hit_qids := [];
            h_size := Size(H);
            for q_idx in [1..Length(master_catalog)] do
                q_size := Size(master_catalog[q_idx]);
                if q_size = 1 then continue; fi;              # legacy excludes K=H (trivial Q)
                if q_size > h_size then break; fi;            # ascending-order early exit
                if h_size mod q_size <> 0 then continue; fi;  # Lagrange divides filter
                qid := master_qids[q_idx];
                if HasQuotientType(H, master_catalog[q_idx]) then
                    Add(hit_qids, qid);
                    if not (qid in seen_qids) then
                        AddSet(seen_qids, qid);
                        Add(result, master_catalog[q_idx]);
                    fi;
                fi;
            od;
            # Opt 2: record this H's qid list for future runs (only if safe).
            # Update in-memory cache so subsequent QuotientTypesOfGroups calls
            # in this session hit the cache, and append to NEW list for the
            # next fragment write.
            if h_id[2] = 0 and h_to_qs <> fail then
                h_to_qs.(h_id_san) := hit_qids;
                Add(_META_H_TO_QS_NEW, [h_id_str, hit_qids]);
            fi;
            if Length(result) >= Length(master_catalog) then break; fi;
        od;
        Print("    [QuotientTypesOfGroups] catalog-driven done: ",
              Length(result), " types (subset of |catalog|=",
              Length(master_catalog), ")  cache_hit=", n_cache_hit,
              "  cache_miss=", n_cache_miss, "\n");
        return result;
    fi;

    # Legacy NormalSubgroups path (used when master_catalog not supplied).
    for H in groups do
        idx := idx + 1;
        if Runtime() - last_qt_hb >= 60000 then
            Print("    [QuotientTypesOfGroups] progress ", idx, "/", n_total,
                  " types_so_far=", Length(result),
                  " H_iso_classes_safe=", Length(seen_h_ids),
                  " H_safe_dedup=", n_skipped,
                  " H_unsafe_processed=", n_safe, "\n");
            last_qt_hb := Runtime();
        fi;
        h_id := SafeId(H);
        if h_id[2] = 0 then
            h_id_str := String(h_id);
            if h_id_str in seen_h_ids then
                n_skipped := n_skipped + 1;
                continue;
            fi;
            AddSet(seen_h_ids, h_id_str);
        else
            n_safe := n_safe + 1;
        fi;
        for K in NormalSubgroups(H) do
            if Size(K) = Size(H) then continue; fi;
            Q := H/K;
            qid := SafeId(Q);
            if not (qid in seen_qids) then
                AddSet(seen_qids, qid);
                Add(result, Q);
            fi;
        od;
    od;
    return result;
end;

ComputeOrLoadLeftQGroups := function(arg)
    # Three-lane Q-discovery for LEFT subgroups:
    #   Lane 1 (small): catalog-driven HasQuotientType sweep against
    #     META_Q_CATALOG (cap MAX_Q_SIZE; bounded per H iso-class).
    #   Lane 2 (forced-large): walk each right cache (already-built or
    #     loaded from prior runs); for each Q-iso of size > cap, run
    #     TargetedQuotientExists on left subgroups.  Per-Q early exit.
    #   Lane 3 (unknown-large promotion): for each order > cap dividing
    #     some |H_left| and not yet covered by lanes 1+2, enumerate
    #     SmallGroup(n, *) candidates and test via TargetedQuotientExists.
    #     FATAL if any order has too many SmallGroups (catalog must extend).
    #
    # Args:
    #   arg[1] = groups (LEFT subgroup list)
    #   arg[2] = qgroups_path (sidecar; "" disables persistence)
    #   arg[3] = master_catalog_path (lane 1 catalog; "" => legacy
    #            NormalSubgroups path -- DEPRECATED, may hang)
    #   arg[4] = right_cache_paths (list of paths; [] disables lane 2)
    #   arg[5] = h_to_qs_master_path (Opt 2 master cache; "" disables)
    #   arg[6] = h_to_qs_fragment_path (Opt 2 per-session fragment; "" disables)
    #   arg[7] = h_to_qs_fragments_dir (Opt 2 sibling fragments dir; "" disables)
    #
    # Validation: sidecar ends with `LEFT_Q_GROUPS_SAVED_OK := true;` sentinel.
    # If missing/false after Read, treat as corrupt and recompute.
    local groups, qgroups_path, master_catalog_path, right_cache_paths,
          h_to_qs_master_path, h_to_qs_fragment_path, h_to_qs_fragments_dir,
          h_to_qs, result, tmp, master_catalog, small_qgroups, forced_qrecs,
          forced_qrecs_dedup, seen_qid_strs, qr, key, forced_qgroups,
          covered_qids, promoted_qgroups, path, MANAGEABLE_THRESHOLD,
          QT_CAP;
    groups := arg[1];
    qgroups_path := arg[2];
    if Length(arg) >= 3 then master_catalog_path := arg[3]; else master_catalog_path := ""; fi;
    if Length(arg) >= 4 then right_cache_paths := arg[4]; else right_cache_paths := []; fi;
    if Length(arg) >= 5 then h_to_qs_master_path := arg[5]; else h_to_qs_master_path := ""; fi;
    if Length(arg) >= 6 then h_to_qs_fragment_path := arg[6]; else h_to_qs_fragment_path := ""; fi;
    if Length(arg) >= 7 then h_to_qs_fragments_dir := arg[7]; else h_to_qs_fragments_dir := ""; fi;

    QT_CAP := 200;
    MANAGEABLE_THRESHOLD := 1000;

    LEFT_Q_GROUPS_SAVED_OK := false;
    if qgroups_path <> "" and IsExistingFile(qgroups_path) then
        Read(qgroups_path);
        if IsBound(LEFT_Q_GROUPS_SAVED_OK) and LEFT_Q_GROUPS_SAVED_OK = true
           and IsBound(LEFT_Q_GROUPS) then
            Print("[QGroups] loaded from cache: ", Length(LEFT_Q_GROUPS),
                  " types from ", qgroups_path, "\n");
            return LEFT_Q_GROUPS;
        fi;
        Print("[QGroups] cache file present but invalid sentinel - recomputing\n");
    fi;

    # Opt 1: cached master-catalog load (skips disk re-read within session)
    master_catalog := _LoadMasterCatalog(master_catalog_path);
    # Opt 2: cached H-iso -> Q-iso lookup record (cross-super-batch)
    h_to_qs := _LoadHToQs(h_to_qs_master_path, h_to_qs_fragments_dir);

    # Lane 1: small-catalog discovery
    if master_catalog <> fail then
        small_qgroups := QuotientTypesOfGroups(groups, master_catalog, h_to_qs);
    else
        small_qgroups := QuotientTypesOfGroups(groups);
    fi;
    Print("[QGroups] lane 1 (small): ", Length(small_qgroups), " types\n");

    # Opt 2: persist new H-iso entries discovered during this lane-1 sweep.
    # Do NOT reset _META_H_TO_QS_NEW -- it accumulates across all calls in
    # this GAP session, and each save overwrites the fragment with the
    # cumulative new entries (write-once-per-session-end semantics).
    _SaveHToQsFragment(h_to_qs_fragment_path);

    # Lane 2: forced-large from right caches
    forced_qrecs := [];
    for path in right_cache_paths do
        Append(forced_qrecs, ForcedQRepsFromHCache(path, QT_CAP));
    od;
    # Dedup by qid string across all right caches.
    seen_qid_strs := Set([]);
    forced_qrecs_dedup := [];
    for qr in forced_qrecs do
        key := String(qr.qid);
        if key in seen_qid_strs then continue; fi;
        AddSet(seen_qid_strs, key);
        Add(forced_qrecs_dedup, qr);
    od;
    if Length(forced_qrecs_dedup) > 0 then
        Print("[QGroups] lane 2 (forced-large): ", Length(forced_qrecs_dedup),
              " unique Q-iso candidates from ", Length(right_cache_paths),
              " right cache(s)\n");
        forced_qgroups := ProcessForcedLargeQTypes(groups, forced_qrecs_dedup);
        Print("[QGroups] lane 2 (forced-large): ", Length(forced_qgroups),
              " types accepted\n");
    else
        forced_qgroups := [];
    fi;

    # Lane 3: unknown-large promotion
    covered_qids := Set(Concatenation(
        List(small_qgroups, SafeId),
        List(forced_qgroups, SafeId)));
    promoted_qgroups := PromoteUnknownLargeOrders(
        groups, covered_qids, QT_CAP, MANAGEABLE_THRESHOLD);
    if Length(promoted_qgroups) > 0 then
        Print("[QGroups] lane 3 (promoted): ", Length(promoted_qgroups),
              " types accepted\n");
    fi;

    result := Concatenation(small_qgroups, forced_qgroups, promoted_qgroups);
    Print("[QGroups] union: ", Length(result), " types\n");

    # Normalize for serialization: FactorGroup objects (H/K) print with
    # abstract generator names (f1, f2, ...) that aren't bound at re-Read
    # time, so PrintTo(file, factorgroup) writes unreadable code.
    result := List(result, function(q)
        local n, q_id;
        n := Size(q);
        if IdGroupsAvailable(n) then
            q_id := IdGroup(q);
            return SmallGroup(n, q_id[2]);
        else
            return Image(IsomorphismPermGroup(q));
        fi;
    end);
    if qgroups_path <> "" then
        tmp := Concatenation(qgroups_path, ".tmp");
        PrintTo(tmp, "LEFT_Q_GROUPS := ", result, ";\n",
                "LEFT_Q_GROUPS_SAVED_OK := true;\n");
        Exec(Concatenation("mv -f -- '", tmp, "' '", qgroups_path, "'"));
        Print("[QGroups] saved to cache: ", Length(result),
              " types -> ", qgroups_path, "\n");
    fi;
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
# --- Quotient-free 2-group small-quotient enumeration for {C_2, V_4, D_8} ---
# Profiling on |H|=1024 entries showed the BFS-then-classify approach spent
# 42-52% in H/K NaturalHom calls (3-5ms each x ~12k calls) and 32% in
# Index2-via-abelianization, total ~106-130s per entry.  The targets
# {C_2, V_4, D_8} are structurally specific enough that we can enumerate
# the kernels DIRECTLY without ever building H/K.

Index2SubgroupsViaAbelianization := function(M)
    local D, hom, A, maxs;
    D := DerivedSubgroup(M);
    if Size(D) = Size(M) then return []; fi;
    hom := NaturalHomomorphismByNormalSubgroup(M, D);
    A := Range(hom);
    maxs := Filtered(MaximalSubgroupClassReps(A), U -> Index(A, U) = 2);
    return Set(List(maxs, U -> PreImage(hom, U)));
end;

# N_L := [H,L] · L^p.  Every K with H/K a central-C_p extension of H/L
# must contain N_L (forces K normal in H, L/K central, L/K elem-ab of
# exponent p).  Specialized to p=2 for D_8 enumeration; general p is
# used by PGroupQuotientKernels for odd-prime Q.
RelativePhiSubgroup := function(H, L, p)
    local commHL, pgens, N;
    commHL := CommutatorSubgroup(H, L);
    pgens := List(GeneratorsOfGroup(L), x -> x^p);
    N := SubgroupNC(L, Concatenation(GeneratorsOfGroup(commHL),
                                     Filtered(pgens, x -> x <> ())));
    if not IsNormal(L, N) then N := NormalClosure(L, N); fi;
    return N;
end;

# D_8 kernel enumeration with two early-skip filters per V_4 layer L:
#  - if D = [H,H] ⊆ N_L, every K refining L is abelian (= no D_8 possible)
#  - if Index(L, N_L) ∈ {1, 2}, no hyperplane enumeration is needed
# Both filters cut directly into the per-layer cost dominating |H|=1024
# entries (651 layers, most "dead" or trivial-refinement).
D8KernelsFromV4Layer := function(H, v4s)
    local D, result, L, N, idxLN, hom, A, maxs, U, K, reps, x, sq_in_K;
    D := DerivedSubgroup(H);
    result := [];
    for L in v4s do
        N := RelativePhiSubgroup(H, L, 2);
        # If D ⊆ N then K ⊇ N ⊃ D forces H/K abelian.  Skip the layer.
        if IsSubset(N, D) then continue; fi;
        idxLN := Index(L, N);
        if idxLN = 1 then continue; fi;     # N = L, no refinement
        reps := Filtered(RightTransversal(H, L), x -> not (x in L));
        if idxLN = 2 then
            # Unique K = N at index 2 in L.  D ⊄ N already established.
            sq_in_K := false;
            for x in reps do
                if x^2 in N then sq_in_K := true; break; fi;
            od;
            if sq_in_K then AddSet(result, N); fi;
            continue;
        fi;
        # idxLN >= 4: enumerate index-2 subgroups of L containing N
        # via L/N's abelianization.  K's are automatically H-normal.
        hom := NaturalHomomorphismByNormalSubgroup(L, N);
        A := Range(hom);
        maxs := Filtered(MaximalSubgroupClassReps(A), U -> Index(A, U) = 2);
        for U in maxs do
            K := PreImage(hom, U);
            if IsSubset(K, D) then continue; fi;
            sq_in_K := false;
            for x in reps do
                if x^2 in K then sq_in_K := true; break; fi;
            od;
            if sq_in_K then AddSet(result, K); fi;
        od;
    od;
    return result;
end;

Small2QuotientKernels := function(H, q_groups)
    local has_C2, has_V4, has_D8, result, c2s, v4s, d8s, i, j, L,
          c2_qid, v4_qid, d8_qid;
    has_C2 := ForAny(q_groups, Q -> Size(Q) = 2);
    has_V4 := ForAny(q_groups, Q -> Size(Q) = 4 and not IsCyclic(Q));
    has_D8 := ForAny(q_groups, Q -> Size(Q) = 8 and not IsAbelian(Q));
    result := [];
    # SafeId hardcoded: C_2 = SmallGroup(2,1), V_4 = (4,2), D_8 = (8,3).
    c2_qid := [2, 0, [2, 1]];
    v4_qid := [4, 0, [4, 2]];
    d8_qid := [8, 0, [8, 3]];

    c2s := Index2SubgroupsViaAbelianization(H);
    if has_C2 then
        Append(result, List(c2s, K -> rec(K := K, qsize := 2, qid := c2_qid)));
    fi;

    v4s := [];
    if has_V4 or has_D8 then
        for i in [1..Length(c2s)] do
            for j in [i+1..Length(c2s)] do
                L := Intersection(c2s[i], c2s[j]);
                if Index(H, L) = 4 then AddSet(v4s, L); fi;
            od;
        od;
        if has_V4 then
            Append(result, List(v4s, K -> rec(K := K, qsize := 4, qid := v4_qid)));
        fi;
    fi;

    if has_D8 then
        d8s := D8KernelsFromV4Layer(H, v4s);
        Append(result, List(d8s, K -> rec(K := K, qsize := 8, qid := d8_qid)));
    fi;

    return result;
end;

# Generalizes Index2SubgroupsViaAbelianization to arbitrary prime p.
# Returns the index-p normal subgroups of M, computed via M / [M,M].
Index_p_SubgroupsViaAbelianization := function(M, p)
    local D, hom, A, maxs;
    D := DerivedSubgroup(M);
    if Size(D) = Size(M) then return []; fi;
    if (Size(M) / Size(D)) mod p <> 0 then return []; fi;
    hom := NaturalHomomorphismByNormalSubgroup(M, D);
    A := Range(hom);
    maxs := Filtered(MaximalSubgroupClassReps(A), U -> Index(A, U) = p);
    return Set(List(maxs, U -> PreImage(hom, U)));
end;

# PGroupQuotientKernels(H, Q): returns Set of K ⊆ H with H/K ≅ Q, when Q is
# a p-group.  Generalizes D8KernelsFromV4Layer: pick a central A ≤ Q with
# |A|=p, recurse on Q/A, then enumerate central C_p refinements via the
# [H,K0]·K0^p floor.  Returns `fail` for non-p-group Q.
#
# Correctness: every K with H/K ≅ Q and central A ⊴ Q lifts to K ⊆ K0 ⊆ H
# with H/K0 ≅ Q/A and K0/K ≅ A.  K0/K central in H/K forces [H,K0] ⊆ K, so
# K must contain NK0 := [H,K0]·K0^p.  Conversely, every index-p subgroup K
# of K0 containing NK0 is automatically H-normal AND gives K0/K central, so
# we filter only by SafeId(H/K) = SafeId(Q) (distinguishes D_8 from Q_8 etc).

# HasQuotientType(H, Q): cheap necessary-condition check for "H surjects onto Q".
# Returns false → no Q-quotient exists (sound, no kernels lost).
# Returns true → might have kernels; do full enumeration.
#
# For p-group Q, two structural checks:
#  (1) Abelianization compatibility — H/[H,H] must surject onto Q/[Q,Q].
#      Necessary because every quotient surjects on its abelianization.
#  (2) Derived-subgroup compatibility — for non-abelian Q (i.e. [Q,Q] = D_Q
#      non-trivial), [H,H] must have an H-equivariant elementary-abelian
#      p-quotient of rank >= rank(D_Q^ab).  The maximum such quotient is
#      D_H / Phi_H(D_H) where Phi_H(D_H) := [D_H,H]·D_H^p (relative Frattini
#      under the H-action).  If Phi_H(D_H) = D_H, no non-trivial elementary
#      abelian H-image of D_H exists, so no non-abelian Q-quotient exists.
#
# Cost: O(1 RelativePhiSubgroup call) ≈ 10-30ms.  Matches GQuotients' speed
# on the no-quotient-exists case.
HasQuotientType := function(H, Q)
    local primes, p, D_H, D_Q, A_inv_p, Q_ab_inv, Phi_DH,
          DQ_inv, phidh_rank, dq_rank;
    if Size(Q) = 1 then return true; fi;
    primes := Set(FactorsInt(Size(Q)));
    if Length(primes) <> 1 then return true; fi;  # not p-group; defer
    p := primes[1];
    D_H := DerivedSubgroup(H);
    if Size(D_H) = Size(H) then return false; fi;  # H perfect
    A_inv_p := Filtered(AbelianInvariants(H / D_H), x -> x mod p = 0);
    Q_ab_inv := AbelianInvariants(Q / DerivedSubgroup(Q));
    if Length(Q_ab_inv) > 0 then
        if Length(A_inv_p) < Length(Q_ab_inv) then return false; fi;
        if Maximum(A_inv_p) < Maximum(Q_ab_inv) then return false; fi;
    fi;
    D_Q := DerivedSubgroup(Q);
    if Size(D_Q) > 1 then
        if Size(D_H) < Size(D_Q) then return false; fi;
        Phi_DH := RelativePhiSubgroup(H, D_H, p);
        if Size(Phi_DH) = Size(D_H) then return false; fi;
        phidh_rank := LogInt(Size(D_H) / Size(Phi_DH), p);
        DQ_inv := AbelianInvariants(D_Q / DerivedSubgroup(D_Q));
        dq_rank := Length(Filtered(DQ_inv, x -> x mod p = 0));
        if phidh_rank < dq_rank then return false; fi;
    fi;
    return true;
end;

PPrimaryExponentsOfAbelianInvariants := function(inv, p)
    local exps, n, e;
    exps := [];
    for n in inv do
        e := 0;
        while n mod p = 0 do
            e := e + 1;
            n := n / p;
        od;
        if e > 0 then Add(exps, e); fi;
    od;
    Sort(exps);
    return Reversed(exps);
end;

AbelianInvariantsCanSurject := function(src_inv, dst_inv)
    local primes, n, p, src_e, dst_e, i;
    primes := Set([]);
    for n in dst_inv do
        for p in Set(FactorsInt(n)) do AddSet(primes, p); od;
    od;
    for p in primes do
        src_e := PPrimaryExponentsOfAbelianInvariants(src_inv, p);
        dst_e := PPrimaryExponentsOfAbelianInvariants(dst_inv, p);
        if Length(src_e) < Length(dst_e) then return false; fi;
        for i in [1..Length(dst_e)] do
            if src_e[i] < dst_e[i] then return false; fi;
        od;
    od;
    return true;
end;

CanSurjectOnAbelianization := function(A, Q)
    local DQ, q_ab_inv;
    DQ := DerivedSubgroup(Q);
    if Size(DQ) = Size(Q) then return true; fi;
    if A = fail then return false; fi;
    q_ab_inv := AbelianInvariants(Q / DQ);
    return AbelianInvariantsCanSurject(AbelianInvariants(A), q_ab_inv);
end;

DerivedSeriesOrderCompatibleFromDH := function(H, Q, DH)
    local Hcur, Qcur, nextH, nextQ, first;
    Hcur := H;
    Qcur := Q;
    first := true;
    while Size(Qcur) > 1 do
        if Size(Hcur) mod Size(Qcur) <> 0 then return false; fi;
        if Size(Hcur) = 1 then return false; fi;
        if first then
            nextH := DH;
            first := false;
        else
            nextH := DerivedSubgroup(Hcur);
        fi;
        nextQ := DerivedSubgroup(Qcur);
        if Size(nextQ) = Size(Qcur) then
            return Size(nextH) mod Size(Qcur) = 0;
        fi;
        Hcur := nextH;
        Qcur := nextQ;
    od;
    return true;
end;

CheapQuotientPossiblePrepared := function(H, Q, DH, A)
    if Size(H) mod Size(Q) <> 0 then return false; fi;
    if not CanSurjectOnAbelianization(A, Q) then return false; fi;
    if not DerivedSeriesOrderCompatibleFromDH(H, Q, DH) then return false; fi;
    return true;
end;

SameOrderQuotientKernelRecord := function(H, Q, q_qid)
    local h_id, iso;
    if Size(H) <> Size(Q) then return fail; fi;
    h_id := SafeId(H);
    if h_id[2] = 0 and q_qid[2] = 0 then
        if h_id = q_qid then
            return rec(K := TrivialSubgroup(H), qsize := Size(Q), qid := q_qid);
        fi;
        return false;
    fi;
    iso := IsomorphismGroups(H, Q);
    if iso <> fail then
        return rec(K := TrivialSubgroup(H), qsize := Size(Q), qid := q_qid);
    fi;
    return false;
end;

PrimeKernelQuotientRecords := function(H, Q, q_qid)
    local ksize, result, K;
    ksize := Size(H) / Size(Q);
    if not IsPrimeInt(ksize) then return fail; fi;
    result := [];
    for K in MinimalNormalSubgroups(H) do
        if Size(K) = ksize and SafeId(H / K) = q_qid then
            AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
        fi;
    od;
    return result;
end;

PGroupQuotientKernelsCached := function(H, Q, cache)
    local primes, p, A, hom_QQbar, Qbar, K0_recs, K0_rec, K0, NK0, hom, F,
          maxs, U, K, target_id, target_qsize, result, gens_A,
          p_kernels, key, idx;
    # Memoized PGroupQuotientKernels.  cache is rec(keys := [], vals := []).
    # Hits on shared Qbar (e.g., D_8/Z and Q_8/Z both reduce to V_4) avoid
    # recomputing K0_set across multiple Q-types in one _EnumerateNormalsForQGroups call.
    if Size(Q) = 1 then
        return [rec(K := H, qsize := 1, qid := [1, 0, [1, 1]])];
    fi;
    primes := Set(FactorsInt(Size(Q)));
    if Length(primes) <> 1 then return fail; fi;
    p := primes[1];
    target_id := SafeId(Q);
    target_qsize := Size(Q);
    key := target_id;
    idx := Position(cache.keys, key);
    if idx <> fail then return cache.vals[idx]; fi;
    if not HasQuotientType(H, Q) then
        Add(cache.keys, key); Add(cache.vals, []);
        return [];
    fi;
    if Size(Q) = p then
        p_kernels := Index_p_SubgroupsViaAbelianization(H, p);
        result := List(p_kernels,
                       K -> rec(K := K, qsize := target_qsize, qid := target_id));
        Add(cache.keys, key); Add(cache.vals, result);
        return result;
    fi;
    A := MinimalNormalSubgroups(Q)[1];
    if Size(A) > p then
        gens_A := GeneratorsOfGroup(A);
        A := SubgroupNC(Q, [gens_A[1]]);
    fi;
    hom_QQbar := NaturalHomomorphismByNormalSubgroup(Q, A);
    Qbar := Range(hom_QQbar);
    K0_recs := PGroupQuotientKernelsCached(H, Qbar, cache);
    if K0_recs = fail then return fail; fi;
    result := [];
    for K0_rec in K0_recs do
        K0 := K0_rec.K;
        NK0 := RelativePhiSubgroup(H, K0, p);
        if Index(K0, NK0) < p then continue; fi;
        if Index(K0, NK0) = p then
            if SafeId(H / NK0) = target_id then
                AddSet(result, rec(K := NK0, qsize := target_qsize, qid := target_id));
            fi;
            continue;
        fi;
        hom := NaturalHomomorphismByNormalSubgroup(K0, NK0);
        F := Range(hom);
        maxs := Filtered(MaximalSubgroupClassReps(F), U -> Index(F, U) = p);
        for U in maxs do
            K := PreImage(hom, U);
            if SafeId(H / K) = target_id then
                AddSet(result, rec(K := K, qsize := target_qsize, qid := target_id));
            fi;
        od;
    od;
    Add(cache.keys, key); Add(cache.vals, result);
    return result;
end;

PGroupQuotientKernels := function(H, Q)
    # Backward-compat wrapper: creates a fresh cache for a single call.  The
    # production path in _EnumerateNormalsForQGroups uses
    # PGroupQuotientKernelsCached directly with a cache shared across all
    # Q-types for a given H.
    return PGroupQuotientKernelsCached(H, Q, rec(keys := [], vals := []));
end;

NonAbelianSimpleQuotientKernelRecords := function(H, Q, q_qid)
    local result, K;
    if not (IsSimpleGroup(Q) and not IsAbelian(Q)) then return fail; fi;
    if Size(H) mod Size(Q) <> 0 then return []; fi;
    result := [];
    for K in MaximalNormalSubgroups(H) do
        if Size(H) / Size(K) = Size(Q) and SafeId(H / K) = q_qid then
            AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
        fi;
    od;
    return result;
end;

# Self-centralizing almost-simple quotient shortcut.
# If Q' is non-abelian simple and C_Q(Q') = 1, then for any epi H -> Q
# the kernel is the full preimage of C_{H/L}(H'/L), where L is the kernel
# of the induced simple quotient H' -> Q'.  This avoids enumerating every
# outer abelian quotient (e.g. all C2 quotients of S5 x 2^r).
AlmostSimpleQuotientKernelRecords := function(H, Q, q_qid)
    local DQ, CQ, DH, dq_id, simple_recs, result, L_rec, L,
          hom, Hbar, Dbar, Cbar, K;
    if IsSolvable(Q) then return fail; fi;
    DQ := DerivedSubgroup(Q);
    if not (IsSimpleGroup(DQ) and not IsAbelian(DQ)) then return fail; fi;
    CQ := Centralizer(Q, DQ);
    if Size(CQ) <> 1 then return fail; fi;
    DH := DerivedSubgroup(H);
    if Size(DH) mod Size(DQ) <> 0 then return []; fi;
    dq_id := SafeId(DQ);
    simple_recs := NonAbelianSimpleQuotientKernelRecords(DH, DQ, dq_id);
    if simple_recs = fail then return fail; fi;
    result := [];
    for L_rec in simple_recs do
        L := L_rec.K;
        if not IsNormal(H, L) then continue; fi;
        hom := NaturalHomomorphismByNormalSubgroup(H, L);
        Hbar := Range(hom);
        Dbar := Image(hom, DH);
        Cbar := Centralizer(Hbar, Dbar);
        if Size(Cbar) <> Size(Hbar) / Size(Q) then continue; fi;
        K := PreImage(hom, Cbar);
        if IsNormal(H, K) and SafeId(H / K) = q_qid then
            AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
        fi;
    od;
    return result;
end;

# Bounded direct exact path for small H or tiny kernel.  Enumerates
# NormalSubgroups(H) and filters to those whose index gives Q.  Much faster
# than recursive solvable-quotient enumeration when |H| is small enough that
# NormalSubgroups(H) is cheap, OR when the kernel is small enough that there
# are very few candidates.
SmallKernelQuotientKernelRecords := function(H, Q, q_qid)
    local ksize, result, K;
    if Size(H) mod Size(Q) <> 0 then return []; fi;
    ksize := Size(H) / Size(Q);
    # Thresholds tuned empirically (n=15 [12,3] benchmark): |H|=2304 with
    # ksize=16 hit a 66s SolvableQuotientKernelRecords ladder, so widen to
    # |H|<=4096 or ksize<=16.
    if not (Size(H) <= 4096 or ksize <= 16) then return fail; fi;
    result := [];
    for K in NormalSubgroups(H) do
        if Size(K) = ksize and SafeId(H / K) = q_qid then
            AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
        fi;
    od;
    return result;
end;

# Direct GQuotients(H, Q) wrapper for small mixed-solvable Q.  Used in place
# of recursive SolvableQuotientKernelRecords when |H| and |Q| are small
# enough that GAP's native quotient enumeration is the right tool.
DirectGQuotientsKernelRecords := function(H, Q, q_qid)
    local result, epi, K;
    result := [];
    for epi in GQuotients(H, Q) do
        K := Kernel(epi);
        AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
    od;
    return result;
end;

SolvableQuotientKernelRecords := function(H, Q, pg_cache)
    local sz, target_id, DH, hom, A, same_rec, prime_recs, p, max_subs,
          result, epi, pg_recs, max_normals, M, Qbar, K0_recs, K0_rec,
          K0, M_recs, K_rec, K, simple_recs, almost_recs, candidates,
          branch_result, branch_ok, handled;
    sz := Size(Q);
    target_id := SafeId(Q);
    if sz = 1 then
        return [rec(K := H, qsize := 1, qid := target_id)];
    fi;
    if Size(H) mod sz <> 0 then return []; fi;
    DH := DerivedSubgroup(H);
    if Size(DH) = Size(H) then
        hom := fail; A := fail;
    else
        hom := NaturalHomomorphismByNormalSubgroup(H, DH);
        A := Range(hom);
    fi;
    if not CheapQuotientPossiblePrepared(H, Q, DH, A) then return []; fi;
    same_rec := SameOrderQuotientKernelRecord(H, Q, target_id);
    if same_rec <> fail then
        if same_rec = false then return []; fi;
        return [same_rec];
    fi;
    prime_recs := PrimeKernelQuotientRecords(H, Q, target_id);
    if prime_recs <> fail then return prime_recs; fi;
    if IsPrimeInt(sz) then
        if A = fail then return []; fi;
        if Size(A) mod sz <> 0 then return []; fi;
        p := sz;
        max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = p);
        return List(max_subs,
            K -> rec(K := PreImage(hom, K), qsize := sz, qid := target_id));
    fi;
    if IsPGroup(Q) and sz <= 256 then
        pg_recs := PGroupQuotientKernelsCached(H, Q, pg_cache);
        if pg_recs <> fail then return pg_recs; fi;
    fi;
    if IsAbelian(Q) then
        if A = fail then return []; fi;
        result := [];
        for epi in GQuotients(A, Q) do
            Add(result, rec(K := PreImage(hom, Kernel(epi)),
                            qsize := sz, qid := target_id));
        od;
        return result;
    fi;
    almost_recs := AlmostSimpleQuotientKernelRecords(H, Q, target_id);
    if almost_recs <> fail then return almost_recs; fi;
    simple_recs := NonAbelianSimpleQuotientKernelRecords(H, Q, target_id);
    if simple_recs <> fail then return simple_recs; fi;
    max_normals := Filtered(MaximalNormalSubgroups(Q),
                            M -> Size(M) > 1 and Size(M) < Size(Q));
    if Length(max_normals) = 0 then return fail; fi;
    result := [];
    handled := false;
    if IsSolvable(Q) then candidates := [max_normals[1]];
    else candidates := max_normals; fi;
    for M in candidates do
        Qbar := Range(NaturalHomomorphismByNormalSubgroup(Q, M));
        K0_recs := SolvableQuotientKernelRecords(H, Qbar, pg_cache);
        if K0_recs = fail then continue; fi;
        branch_result := [];
        branch_ok := true;
        for K0_rec in K0_recs do
            K0 := K0_rec.K;
            M_recs := SolvableQuotientKernelRecords(K0, M, rec(keys := [], vals := []));
            if M_recs = fail then
                branch_ok := false;
                break;
            fi;
            for K_rec in M_recs do
                K := K_rec.K;
                if IsNormal(H, K) and SafeId(H / K) = target_id then
                    AddSet(branch_result, rec(K := K, qsize := sz, qid := target_id));
                fi;
            od;
        od;
        if branch_ok then
            handled := true;
            for K_rec in branch_result do AddSet(result, K_rec); od;
        fi;
    od;
    if handled then return result; fi;
    return fail;
end;

# ------------------------------------------------------------------
# Stage C: forced-large discovery from a trusted opposite-side H-cache.
# ------------------------------------------------------------------
#
# Given a concrete Q (typically extracted from the right cache), test
# whether some H_left actually surjects onto Q -- WITHOUT calling
# NormalSubgroups(H).  Returns true|false.
#
# Three branches:
#   1. p-group Q: use PGroupQuotientKernelsCached (bounded recursion).
#   2. abelian Q: lift via H/[H,H] = A and call GQuotients(A, Q) (cheap;
#      A is small).
#   3. non-abelian non-p-group Q: GQuotients(H, Q) directly.  Can be slow
#      for hostile H but is bounded per (H, Q) pair, unlike NormalSubgroups
#      which enumerates the entire normal lattice.
TargetedQuotientExists := function(H, Q, pg_cache)
    local sz, DH, hom, A, recs, q_qid, same_rec, prime_recs;
    sz := Size(Q);
    if sz = 1 then return true; fi;
    if Size(H) mod sz <> 0 then return false; fi;
    DH := DerivedSubgroup(H);
    if Size(DH) = Size(H) then
        hom := fail; A := fail;
    else
        hom := NaturalHomomorphismByNormalSubgroup(H, DH);
        A := Range(hom);
    fi;
    if not CheapQuotientPossiblePrepared(H, Q, DH, A) then return false; fi;
    q_qid := SafeId(Q);
    same_rec := SameOrderQuotientKernelRecord(H, Q, q_qid);
    if same_rec <> fail then return same_rec <> false; fi;
    prime_recs := PrimeKernelQuotientRecords(H, Q, q_qid);
    if prime_recs <> fail then return Length(prime_recs) > 0; fi;
    if IsPGroup(Q) then
        recs := PGroupQuotientKernelsCached(H, Q, pg_cache);
        if recs <> fail then return Length(recs) > 0; fi;
        # PGroupQuotientKernelsCached may return fail when its preconditions
        # aren't met; fall through to the abelian/general path below.
    fi;
    if IsAbelian(Q) then
        if A = fail then return false; fi;
        return Length(GQuotients(A, Q)) > 0;
    fi;
    recs := SolvableQuotientKernelRecords(H, Q, pg_cache);
    if recs <> fail then return Length(recs) > 0; fi;
    return Length(GQuotients(H, Q)) > 0;
end;

# Walk a previously-built right H-cache file and extract the set of distinct
# Q-iso-classes of size > cap as concrete group representatives.  Each entry
# carries: rec(Q, qsize, qid, source).  The qid[2]=0 case uses SmallGroup
# directly; the heuristic-fallback case (qid[2]=1) reconstructs Q := H/K
# and normalizes via IsomorphismPermGroup.
#
# Saves & restores any pre-existing global H_CACHE so this can run before
# the LEFT cache is loaded.
ForcedQRepsFromHCache := function(cache_path, cap)
    local out, seen, entry, orb, Q, key, saved_H_CACHE, right_cache, H, K;
    out := [];
    seen := Set([]);
    if cache_path = "" or not IsExistingFile(cache_path) then return out; fi;
    saved_H_CACHE := fail;
    if IsBound(H_CACHE) then
        saved_H_CACHE := H_CACHE;
        Unbind(H_CACHE);
    fi;
    Read(cache_path);
    if not IsBound(H_CACHE) or not IsList(H_CACHE) then
        if saved_H_CACHE <> fail then H_CACHE := saved_H_CACHE; fi;
        return out;
    fi;
    right_cache := H_CACHE;
    Unbind(H_CACHE);
    if saved_H_CACHE <> fail then H_CACHE := saved_H_CACHE; fi;
    for entry in right_cache do
        for orb in entry.orbits do
            if orb.qsize <= cap then continue; fi;
            key := String(orb.qid);
            if key in seen then continue; fi;
            AddSet(seen, key);
            if orb.qid[2] = 0 then
                Q := SmallGroup(orb.qid[3]);
            else
                # Fallback: reconstruct via H/K.  H from this right-cache entry.
                H := Group(entry.H_gens);
                K := Subgroup(H, orb.K_H_gens);
                Q := Image(IsomorphismPermGroup(
                    Range(NaturalHomomorphismByNormalSubgroup(H, K))));
            fi;
            Add(out, rec(Q := Q, qsize := orb.qsize, qid := orb.qid,
                        source := "right-cache"));
        od;
    od;
    return out;
end;

# Test each forced-large Q against LEFT subgroups via TargetedQuotientExists.
# Per-Q early exit on first H that succeeds (we only need to know membership
# in LEFT_Q_GROUPS, not enumerate all kernels here).
ProcessForcedLargeQTypes := function(left_groups, forced_qrecs)
    local result, qr, H, pg_cache, t_q;
    result := [];
    for qr in forced_qrecs do
        Print("    [forced-large] testing Q=[", qr.qsize, ",",
              qr.qid, "]\n");
        t_q := Runtime();
        for H in left_groups do
            if Size(H) mod qr.qsize <> 0 then continue; fi;
            pg_cache := rec(keys := [], vals := []);
            if TargetedQuotientExists(H, qr.Q, pg_cache) then
                Add(result, qr.Q);
                Print("    [forced-large] FOUND Q=[", qr.qsize, ",",
                      qr.qid, "] in |H|=", Size(H), " (",
                      Runtime() - t_q, "ms)\n");
                break;
            fi;
        od;
    od;
    return result;
end;

# Stage D: for each order n > cap appearing as a divisor of some |H_left|,
# enumerate all SmallGroup(n, *) candidates and test via
# TargetedQuotientExists.  FATAL if any required order has unmanageably
# many SmallGroups (in which case the catalog cap must be raised or a
# chunking strategy implemented).
PromoteUnknownLargeOrders := function(left_groups, covered_qids, cap, max_per_order)
    local left_orders, n, i, qrecs_to_test, covered_orders, candidate_Q,
          qid, H, d;
    qrecs_to_test := [];
    left_orders := Set([]);
    for H in left_groups do
        for d in DivisorsInt(Size(H)) do
            if d > cap then AddSet(left_orders, d); fi;
        od;
    od;
    covered_orders := Set(List(covered_qids, q -> q[1]));
    for n in left_orders do
        if not IdGroupsAvailable(n) then
            # SmallGroups database does not include this order (e.g., 2160).
            # Skip: the forced-large lane already covers any Q of this order
            # that actually appears on the right side, which is the only case
            # that contributes orbits under Goursat.
            Print("    [promote] WARNING: order ", n,
                  " has no SmallGroups database; skipping ",
                  "(forced-large lane covers right-side Q's).\n");
            continue;
        fi;
        if NumberSmallGroups(n) > max_per_order then
            Print("    [promote] WARNING: order ", n, " has ",
                  NumberSmallGroups(n),
                  " SmallGroups (> max_per_order=", max_per_order,
                  "); skipping (forced-large lane covers right-side Q's).\n");
            continue;
        fi;
        for i in [1..NumberSmallGroups(n)] do
            candidate_Q := SmallGroup(n, i);
            qid := SafeId(candidate_Q);
            if qid in covered_qids then continue; fi;
            Add(qrecs_to_test, rec(Q := candidate_Q, qsize := n, qid := qid,
                                    source := "promoted"));
        od;
    od;
    if Length(qrecs_to_test) = 0 then return []; fi;
    Print("    [promote] testing ", Length(qrecs_to_test),
          " unknown-large candidates across ", Length(left_orders),
          " orders > cap=", cap, "\n");
    return ProcessForcedLargeQTypes(left_groups, qrecs_to_test);
end;

_EnumerateNormalsForQGroups := function(H, q_groups)
    local q_size_H, DH, abel_hom, A, result, Q, sz, p, max_subs, epi,
          qids_set, all_normals, K, qid_K, t_q,
          h_is_2group, small_qs, other_qs, pg_kernels, q_qid, q_size,
          c2_qid, pg_cache, same_rec, prime_recs, solv_kernels,
          small_recs, direct_recs;
    # Returns a list of records: rec(K := <kernel>, qsize := |H/K|, qid := SafeId(H/K)).
    # qid is propagated from each enumeration branch so that the downstream
    # orbit construction (_ComputeOrbitRecsFromKs) can skip the per-orbit
    # NaturalHomomorphismByNormalSubgroup + SafeId reconstruction.
    #
    # As of Stage B (2026-05-08): never calls NormalSubgroups(H).  The legacy
    # `q_groups = fail` (full enumeration) and `use_direct` (max(|Q|)>200)
    # branches are removed -- callers must always pass a concrete Q list, and
    # large Q's are routed per-Q via the existing PGroupQuotientKernelsCached
    # / abelianization / GQuotients paths below.
    if q_groups = fail then
        Error("EnumerateNormalsForQGroups requires non-fail q_groups; ",
              "the legacy NormalSubgroups discovery path has been removed. ",
              "|H|=", Size(H));
    fi;
    if Length(q_groups) = 0 then return []; fi;
    h_is_2group := ForAll(FactorsInt(Size(H)), p -> p = 2);
    if h_is_2group then
        small_qs := Filtered(q_groups, Q ->
            Size(Q) = 2
            or (Size(Q) = 4 and not IsCyclic(Q))
            or (Size(Q) = 8 and not IsAbelian(Q) and IdGroup(Q) = [8, 3]));
    else
        small_qs := Filtered(q_groups, Q -> Size(Q) = 2);
    fi;
    other_qs := Filtered(q_groups, Q -> not (Q in small_qs));
    result := [];
    if Length(small_qs) > 0 then
        Print("    [enum/L0/small] BEGIN |H|=", Size(H),
              " n_small=", Length(small_qs), "\n");
        t_q := Runtime();
        if h_is_2group then
            Append(result, Small2QuotientKernels(H, small_qs));
        else
            c2_qid := [2, 0, [2, 1]];
            Append(result, List(Index2SubgroupsViaAbelianization(H),
                                K -> rec(K := K, qsize := 2, qid := c2_qid)));
        fi;
        Print("    [enum/L0/small] END   |H|=", Size(H),
              " -> ", Length(result), " kernels in ", Runtime() - t_q, "ms\n");
    fi;
    if Length(other_qs) = 0 then return result; fi;
    q_size_H := Size(H);
    DH := DerivedSubgroup(H);
    if Size(DH) = q_size_H then
        abel_hom := fail; A := fail;
    else
        abel_hom := NaturalHomomorphismByNormalSubgroup(H, DH);
        A := Range(abel_hom);
    fi;
    pg_cache := rec(keys := [], vals := []);   # shared across all Q in other_qs
    for Q in other_qs do
        sz := Size(Q);
        if q_size_H mod sz <> 0 then continue; fi;
        q_qid := SafeId(Q);
        q_size := sz;
        t_q := Runtime();
        if not CheapQuotientPossiblePrepared(H, Q, DH, A) then
            if Runtime() - t_q >= 100 then
                Print("    [enum/cheap_skip] |H|=", Size(H), " Q=", q_qid,
                      " in ", Runtime() - t_q, "ms\n");
            fi;
            continue;
        fi;
        same_rec := SameOrderQuotientKernelRecord(H, Q, q_qid);
        if same_rec <> fail then
            if same_rec <> false then Add(result, same_rec); fi;
            if Runtime() - t_q >= 100 then
                Print("    [enum/same_order] |H|=", Size(H), " Q=", q_qid,
                      " in ", Runtime() - t_q, "ms\n");
            fi;
            continue;
        fi;
        prime_recs := PrimeKernelQuotientRecords(H, Q, q_qid);
        if prime_recs <> fail then
            Append(result, prime_recs);
            if Runtime() - t_q >= 100 then
                Print("    [enum/prime_kernel] |H|=", Size(H), " Q=", q_qid,
                      " -> ", Length(prime_recs), " kernels in ",
                      Runtime() - t_q, "ms\n");
            fi;
            continue;
        fi;
        # Small-H or tiny-kernel direct path: NormalSubgroups(H) bounded.
        small_recs := SmallKernelQuotientKernelRecords(H, Q, q_qid);
        if small_recs <> fail then
            Append(result, small_recs);
            if Runtime() - t_q >= 100 then
                Print("    [enum/small_kernel] |H|=", Size(H), " Q=", q_qid,
                      " -> ", Length(small_recs), " kernels in ",
                      Runtime() - t_q, "ms\n");
            fi;
            continue;
        fi;
        if IsPrimeInt(sz) then
            if abel_hom = fail then continue; fi;
            if Size(A) mod sz <> 0 then continue; fi;
            p := sz;
            max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = p);
            Append(result, List(max_subs,
                K -> rec(K := PreImage(abel_hom, K), qsize := q_size, qid := q_qid)));
            if Runtime() - t_q >= 100 then
                Print("    [enum/prime_abel] |H|=", Size(H), " Q=", q_qid,
                      " -> ", Length(max_subs), " kernels in ",
                      Runtime() - t_q, "ms\n");
            fi;
        elif IsPGroup(Q) and sz <= 256 then
            # Level 1: p-group Q (abelian or non-abelian) via memoized
            # PGroupQuotientKernelsCached.  HasQuotientType inside that
            # function gives a cheap top-level feasibility check (O(1
            # RelativePhi call) ≈ 10-30ms) that matches GQuotients' speed
            # on the no-quotient case, so non-abelian Q is now safe to
            # route here even when many H entries don't admit such a
            # quotient.  Memoization (#3) shares K0_set across siblings.
            Print("    [enum/L1/pgroup] BEGIN |H|=", Size(H),
                  " Q=[", sz, ",", IdGroup(Q)[2], "]\n");
            t_q := Runtime();
            pg_kernels := PGroupQuotientKernelsCached(H, Q, pg_cache);
            if pg_kernels <> fail then
                Append(result, pg_kernels);
                Print("    [enum/L1/pgroup] END   |H|=", Size(H),
                      " Q=[", sz, ",", IdGroup(Q)[2], "] -> ",
                      Length(pg_kernels), " kernels in ",
                      Runtime() - t_q, "ms\n");
            else
                Print("    [enum/L1/pgroup] FALLBACK |H|=", Size(H),
                      " Q=[", sz, ",", IdGroup(Q)[2], "]\n");
                if abel_hom <> fail then
                    for epi in GQuotients(A, Q) do
                        Add(result, rec(K := PreImage(abel_hom, Kernel(epi)),
                                        qsize := q_size, qid := q_qid));
                    od;
                fi;
            fi;
        elif IsAbelian(Q) then
            if abel_hom = fail then continue; fi;
            for epi in GQuotients(A, Q) do
                Add(result, rec(K := PreImage(abel_hom, Kernel(epi)),
                                qsize := q_size, qid := q_qid));
            od;
            if Runtime() - t_q >= 100 then
                Print("    [enum/abelian] |H|=", Size(H), " Q=", q_qid,
                      " in ", Runtime() - t_q, "ms\n");
            fi;
        else
            # Small mixed-solvable Q: GQuotients(H, Q) is the right tool.
            # Avoids the recursive SolvableQuotientKernelRecords ladder that
            # can hit pathological cases (e.g. Q=SmallGroup(48,50) on
            # H=TG[12,90] taking 130s).
            if IsSolvable(Q) and not IsPGroup(Q) and not IsAbelian(Q)
               and Size(H) <= 4096 and Size(Q) <= 1024 then
                direct_recs := DirectGQuotientsKernelRecords(H, Q, q_qid);
                Append(result, direct_recs);
                if Runtime() - t_q >= 100 then
                    Print("    [enum/direct_gq] |H|=", Size(H), " Q=", q_qid,
                          " -> ", Length(direct_recs), " kernels in ",
                          Runtime() - t_q, "ms\n");
                fi;
                continue;
            fi;
            solv_kernels := SolvableQuotientKernelRecords(H, Q, pg_cache);
            if solv_kernels <> fail then
                Append(result, solv_kernels);
                if Runtime() - t_q >= 100 then
                    Print("    [enum/solvable] |H|=", Size(H), " Q=", q_qid,
                          " -> ", Length(solv_kernels), " kernels in ",
                          Runtime() - t_q, "ms\n");
                fi;
                continue;
            fi;
            Print("    [enum/fallback/GQuot] BEGIN |H|=", Size(H),
                  " Q=[", sz, ",", IdGroup(Q)[2], "]\n");
            Append(result, List(Set(List(GQuotients(H, Q), Kernel)),
                                K -> rec(K := K, qsize := q_size, qid := q_qid)));
            Print("    [enum/fallback/GQuot] END   |H|=", Size(H),
                  " Q=[", sz, ",", IdGroup(Q)[2], "] in ",
                  Runtime() - t_q, "ms\n");
        fi;
    od;
    return result;
end;

# Cut 3 dispatcher: splits q_groups into linear-supported and legacy.
# For supported qids (C_2, V_4, D_8), calls Stage A/B prototypes directly
# (produces orbit recs in the right format with K_H_gens + Stab_NH_KH_gens).
# Returns the LINEAR orbit-recs as a list; caller is responsible for running
# the legacy path on the remaining q_groups.
_LinearOrbitsForSupportedQids := function(H, N_H, q_groups)
    local supported_qids, orbits, legacy_qs, Q, qid, sz, recs;
    # Fail-safe: if USE_LINEAR_ORBITS isn't defined in this driver template
    # (only GAP_DRIVER has it currently), default to legacy.
    if not IsBound(USE_LINEAR_ORBITS) or USE_LINEAR_ORBITS <> 1 then
        return rec(linear := [], legacy := q_groups);
    fi;
    supported_qids := [[2,0,[2,1]], [4,0,[4,2]], [8,0,[8,3]]];
    orbits := [];
    legacy_qs := [];
    for Q in q_groups do
        qid := SafeId(Q);
        sz := Size(Q);
        if qid = [2,0,[2,1]] then
            Append(orbits, LinearOrbitRecsCpa(H, N_H, 2, 1));
        elif qid = [4,0,[4,2]] then
            Append(orbits, LinearOrbitRecsCpa(H, N_H, 2, 2));
        elif qid = [8,0,[8,3]] then
            Append(orbits, LinearOrbitRecsD8(H, N_H));
        else
            Add(legacy_qs, Q);
        fi;
    od;
    return rec(linear := orbits, legacy := legacy_qs);
end;


_ComputeOrbitRecsFromKs := function(H, N_H, k_recs)
    local kbyqid, qid_str, key, bucket, normals, K_orbit, K_H, Stab_NH_KH,
          orbits, kr, q_size_v, q_qid_v;
    # k_recs is a list of rec(K, qsize, qid).  Bucket by qid (kernels with
    # different qids cannot be N_H-conjugate), orbit per bucket, and skip
    # the per-orbit NaturalHomomorphismByNormalSubgroup + SafeId rebuild —
    # the qid is propagated from the enumeration step.
    orbits := [];
    kbyqid := rec();
    for kr in k_recs do
        qid_str := String(kr.qid);
        if not IsBound(kbyqid.(qid_str)) then
            kbyqid.(qid_str) := rec(qsize := kr.qsize, qid := kr.qid, recs := []);
        fi;
        Add(kbyqid.(qid_str).recs, kr);
    od;
    for key in RecNames(kbyqid) do
        bucket := kbyqid.(key);
        normals := List(bucket.recs, kr -> kr.K);
        q_size_v := bucket.qsize;
        q_qid_v := bucket.qid;
        for K_orbit in Orbits(N_H, normals, ConjAction) do
            K_H := K_orbit[1];
            Stab_NH_KH := Stabilizer(N_H, K_H, ConjAction);
            Add(orbits, rec(
                K_H_gens := GeneratorsOfGroup(K_H),
                Stab_NH_KH_gens := GeneratorsOfGroup(Stab_NH_KH),
                qsize := q_size_v,
                qid := q_qid_v
            ));
        od;
    od;
    return orbits;
end;

ComputeHCacheEntry := function(H, S_M, q_groups)
    local N_H, k_recs, t0, t_norm, t_enum, t_orbit, result_orbits;
    t0 := Runtime();
    N_H := Normalizer(S_M, H);
    t_norm := Runtime() - t0;
    t0 := Runtime();
    k_recs := _EnumerateNormalsForQGroups(H, q_groups);
    t_enum := Runtime() - t0;
    t0 := Runtime();
    result_orbits := _ComputeOrbitRecsFromKs(H, N_H, k_recs);
    t_orbit := Runtime() - t0;
    if t_norm + t_enum + t_orbit >= 1000 then
        Print("    [ComputeHCacheEntry] |H|=", Size(H),
              " norm=", t_norm, "ms enum=", t_enum,
              "ms orbit=", t_orbit, "ms (n_kernels=",
              Length(k_recs), ")\n");
    fi;
    return rec(
        H_gens := GeneratorsOfGroup(H),
        N_H_gens := GeneratorsOfGroup(N_H),
        computed_q_ids := QIdsOfGroups(q_groups),
        orbits := result_orbits
    );
end;

ComputeHDataDirect := function(H, S_M, q_groups)
    local N_H, k_recs, t0, t_norm, t_enum, t_orbit, res, hom_triv,
          kbyqid, kr, qid_str, key, bucket, normals, K_orbit, K_H,
          Stab, i;
    t0 := Runtime();
    N_H := Normalizer(S_M, H);
    t_norm := Runtime() - t0;
    t0 := Runtime();
    k_recs := _EnumerateNormalsForQGroups(H, q_groups);
    t_enum := Runtime() - t0;

    res := rec(H := H, N := N_H,
        H_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_H := fail, shifted_H_gens_noid := fail,
        orbits := []);
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N_H, AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
        K_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_K_gens_noid := fail, c2_rep := fail, shifted_c2_rep := fail,
        H_ref := H));

    t0 := Runtime();
    kbyqid := rec();
    for kr in k_recs do
        qid_str := String(kr.qid);
        if not IsBound(kbyqid.(qid_str)) then
            kbyqid.(qid_str) := rec(qsize := kr.qsize, qid := kr.qid, recs := []);
        fi;
        Add(kbyqid.(qid_str).recs, kr);
    od;
    for key in RecNames(kbyqid) do
        bucket := kbyqid.(key);
        normals := List(bucket.recs, kr -> kr.K);
        for K_orbit in Orbits(N_H, normals, ConjAction) do
            K_H := K_orbit[1];
            Stab := Stabilizer(N_H, K_H, ConjAction);
            Add(res.orbits, rec(K := K_H, hom := fail, Q := fail,
                qsize := bucket.qsize, qid := bucket.qid,
                Stab := Stab, AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
                K_gens_noid := Filtered(GeneratorsOfGroup(K_H), g -> g <> ()),
                shifted_K_gens_noid := fail, c2_rep := fail, shifted_c2_rep := fail,
                H_ref := H));
        od;
    od;
    res.byqid := rec();
    for i in [1..Length(res.orbits)] do
        key := String(res.orbits[i].qid);
        if not IsBound(res.byqid.(key)) then res.byqid.(key) := []; fi;
        Add(res.byqid.(key), i);
    od;
    t_orbit := Runtime() - t0;
    if t_norm + t_enum + t_orbit >= 1000 then
        Print("    [ComputeHDataDirect] |H|=", Size(H),
              " norm=", t_norm, "ms enum=", t_enum,
              "ms orbit=", t_orbit, "ms (n_kernels=",
              Length(k_recs), ")\n");
    fi;
    return res;
end;

ExtendHCacheEntry := function(entry, S_M, additional_q_groups)
    local H, N_H, current, missing_groups, k_recs, new_orbits, all_normals,
          K, qid_K, _linear_split, _linear_t0, _linear_t1;
    if entry.computed_q_ids = fail then return entry; fi;
    H := SafeGroup(entry.H_gens, S_M);
    N_H := SafeGroup(entry.N_H_gens, S_M);
    current := entry.computed_q_ids;
    if additional_q_groups = fail then
        # Extend to FULL coverage: enumerate ALL normals; add only the K's
        # whose quotient iso-class is not already in current.
        all_normals := Filtered(NormalSubgroups(H), K -> K <> H);
        k_recs := [];
        for K in all_normals do
            qid_K := SafeId(H/K);
            if not (qid_K in current) then
                Add(k_recs, rec(K := K, qsize := Size(H)/Size(K), qid := qid_K));
            fi;
        od;
        new_orbits := _ComputeOrbitRecsFromKs(H, N_H, k_recs);
        Append(entry.orbits, new_orbits);
        entry.computed_q_ids := fail;
        return entry;
    fi;
    missing_groups := QGroupsMissing(current, additional_q_groups);
    if Length(missing_groups) = 0 then return entry; fi;
    # Cut 3: route supported qids ({C_2, V_4, D_8}) through Stage A/B (linear
    # orbit math; orbit recs returned directly).  Remaining qids go through
    # the legacy enumerate-then-orbit path.  When USE_LINEAR_ORBITS=0, all
    # qids go to legacy (no behavior change).
    _linear_t0 := Runtime();
    _linear_split := _LinearOrbitsForSupportedQids(H, N_H, missing_groups);
    _linear_t1 := Runtime();
    if Length(_linear_split.linear) > 0 then
        Append(entry.orbits, _linear_split.linear);
    fi;
    if Length(_linear_split.legacy) > 0 then
        k_recs := _EnumerateNormalsForQGroups(H, _linear_split.legacy);
        new_orbits := _ComputeOrbitRecsFromKs(H, N_H, k_recs);
        Append(entry.orbits, new_orbits);
    fi;
    UniteSet(entry.computed_q_ids, QIdsOfGroups(missing_groups));
    if IsBound(USE_LINEAR_ORBITS) and USE_LINEAR_ORBITS = 1
       and (_linear_t1 - _linear_t0) >= 1000 then
        Print("    [cut3/linear] |H|=", Size(H),
              " n_orbits=", Length(_linear_split.linear),
              " time=", _linear_t1 - _linear_t0, "ms\n");
    fi;
    return entry;
end;

# File-level coverage tag: union of computed_q_ids across all H_CACHE
# entries.  An m_r=2 build only covers the q-types of TG(2,*) plus the
# subgroups thereof; an extension to m_r=3,4,... unions in extra qids.
# Saving compares this tag against the on-disk one and only overwrites if
# our in-memory cache covers at least as much as the file does.
ComputeCoverageTag := function(h_cache)
    local tag, e;
    tag := Set([]);
    for e in h_cache do
        # Treat unbound and the `fail` sentinel (set by ExtendHCacheEntry
        # when full coverage was requested) as full coverage.  UniteSet on
        # `fail` would crash GAP, killing the worker silently.
        if not IsBound(e.computed_q_ids) or e.computed_q_ids = fail then
            return fail;
        fi;
        UniteSet(tag, e.computed_q_ids);
    od;
    return tag;
end;

# Read just the first line of a cache file to extract its coverage tag.
# Format: "# coverage_qids: <set>;\n" (or "# coverage_qids: fail;\n" for
# full coverage).  Returns:
#   "missing" - file does not exist
#   "unknown" - file has no header (legacy file written before this opt)
#   fail      - file marked as full coverage
#   <list>    - parsed coverage tag (a Set of qids)
ReadCoverageTagFromFile := function(path)
    local f, line, prefix, payload, n;
    if not IsExistingFile(path) then return "missing"; fi;
    f := InputTextFile(path);
    if f = fail then return "missing"; fi;
    line := ReadLine(f);
    CloseStream(f);
    if line = fail then return "unknown"; fi;
    n := Length(line);
    while n > 0 and line[n] in [' ', '\n', '\r', '\t'] do n := n - 1; od;
    line := line{[1..n]};
    prefix := "# coverage_qids: ";
    if Length(line) < Length(prefix) then return "unknown"; fi;
    if line{[1..Length(prefix)]} <> prefix then return "unknown"; fi;
    payload := line{[Length(prefix)+1..Length(line)]};
    if Length(payload) >= 1 and payload[Length(payload)] = ';' then
        payload := payload{[1..Length(payload)-1]};
    fi;
    if payload = "fail" then return fail; fi;
    return EvalString(payload);
end;

SaveHCacheList := function(path, h_cache)
    local tmp, mem_tag, disk_tag, header, header_stream;
    # Coverage-tagged save: overwrite iff in-memory cache strictly extends
    # (or equals) the on-disk coverage.  Header line is parsed without
    # touching the body, so the check is cheap on multi-MB files.  Files
    # without a header (legacy) always trigger overwrite, which gives them
    # a header on first save.  IsValidCacheFile guards against skipping
    # when the on-disk file is corrupt: we'd otherwise refuse to overwrite
    # a truncated cache and leave readers crashing forever.
    mem_tag := ComputeCoverageTag(h_cache);
    disk_tag := ReadCoverageTagFromFile(path);
    if disk_tag = fail and IsValidCacheFile(path) then
        return;  # on-disk has full coverage and is intact
    fi;
    if disk_tag <> "missing" and disk_tag <> "unknown" and disk_tag <> fail
       and mem_tag <> fail and IsSubset(disk_tag, mem_tag)
       and not IsSubset(mem_tag, disk_tag)
       and IsValidCacheFile(path) then
        # disk_tag STRICTLY dominates mem_tag (disk has q-types we don't).
        # Equal tags are NOT a skip case: during EXTEND, individual entries
        # gain q-ids even when the cross-entry UNION is unchanged (because
        # some other entry already had that q-id).  Skipping the save in
        # that case loses the per-entry progress, so the next epoch loads
        # the same stale cache and re-runs the same slow entry forever.
        return;
    fi;
    if mem_tag = fail then
        header := "# coverage_qids: fail;\n";
    else
        header := Concatenation("# coverage_qids: ", String(mem_tag), ";\n");
    fi;
    # Atomic write: PrintTo to a unique .tmp file, then `mv` to final path.
    # Unique tmp prevents two GAP workers from clobbering each other's
    # PrintTo when racing on the same cache file.
    tmp := Concatenation(path, ".tmp.", String(Runtime()), ".",
                          String(Random([1..1000000])));
    # Header via WriteAll (verbatim, no auto-wrap).  PrintTo would wrap the
    # `# coverage_qids: ...` comment at SizeScreen() chars with backslash-
    # newline, but GAP comments don't honor `\` continuation -- the wrapped
    # comment turns into invalid code on the next line and crashes Read on
    # the next worker spawn.  Body uses default PrintTo wrapping, which is
    # fine since wrapping happens inside expressions (parses correctly).
    header_stream := OutputTextFile(tmp, false);
    WriteAll(header_stream, header);
    CloseStream(header_stream);
    AppendTo(tmp, "H_CACHE := ", h_cache, ";\n");
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

# Read LEFT subgroup list eagerly; it is always needed to build/load H_CACHE.
Print("reading subs_left.g: ", SUBS_LEFT_PATH, "\n");
Read(SUBS_LEFT_PATH);
SUBGROUPS_LEFT_RAW := SUBGROUPS;
Print("subs_left.g loaded: ", Length(SUBGROUPS_LEFT_RAW), " entries\n");

RIGHT_Q_GROUPS := [];
seen_qid := Set([]);
# Per-(d,t) Q-discovery: avoid the slow RequiredQGroups(MR) union.
if RIGHT_TG_D > 0 then
    T_for_qg := TransitiveGroup(RIGHT_TG_D, RIGHT_TG_T);
    for K in NormalSubgroups(T_for_qg) do
        if Size(K) = Size(T_for_qg) then continue; fi;
        Q := T_for_qg/K;
        qid := SafeId(Q);
        if not (qid in seen_qid) then
            AddSet(seen_qid, qid);
            if IdGroupsAvailable(Size(Q)) then
                Add(RIGHT_Q_GROUPS, SmallGroup(Size(Q), IdGroup(Q)[2]));
            else
                Add(RIGHT_Q_GROUPS, Image(IsomorphismPermGroup(Q)));
            fi;
        fi;
    od;
fi;
if SUBS_RIGHT_PATH <> "" then
    for Q in LoadOrComputeRightQGroupsFromSubs(SUBS_RIGHT_PATH, CACHE_RIGHT_PATH) do
        qid := SafeId(Q);
        if not (qid in seen_qid) then
            AddSet(seen_qid, qid);
            Add(RIGHT_Q_GROUPS, Q);
        fi;
    od;
fi;

if Length(RIGHT_Q_GROUPS) = 0 then
    LEFT_Q_GROUPS := ComputeOrLoadLeftQGroups(
        SUBGROUPS_LEFT_RAW,
        Concatenation(CACHE_LEFT_PATH, ".qgroups.g"),
        META_CATALOG_PATH,
        Filtered([CACHE_RIGHT_PATH], p -> p <> ""),
        H_TO_QS_MASTER_PATH,
        H_TO_QS_FRAGMENT_PATH,
        H_TO_QS_FRAGMENTS_DIR);
    Print("LEFT-derived Q-groups for M_R=", MR, ": ", Length(LEFT_Q_GROUPS),
          " types, max |Q|=",
          Maximum(Concatenation([0], List(LEFT_Q_GROUPS, Size))), "\n");
else
    LEFT_Q_GROUPS := RIGHT_Q_GROUPS;
    Print("RIGHT-bounded Q-groups for M_R=", MR, ": ", Length(LEFT_Q_GROUPS),
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
        last_hb := Runtime();
        last_hb_count := 0;
        for hi in [1..Length(H_CACHE)] do
            missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
            if hi = 1 or hi - last_hb_count >= 500
               or Runtime() - last_hb >= 60000 then
                if missing = fail then
                    Print("  H_CACHE EXTEND ", hi, "/", Length(H_CACHE),
                          " n_missing=fail\n");
                else
                    Print("  H_CACHE EXTEND ", hi, "/", Length(H_CACHE),
                          " n_missing=", Length(missing), "\n");
                fi;
                last_hb := Runtime();
                last_hb_count := hi;
            fi;
            if missing = fail then
                ExtendHCacheEntry(H_CACHE[hi], W_ML, LEFT_Q_GROUPS);
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
    # SUBGROUPS_LEFT_RAW already loaded above for Q-type derivation.
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
# Extend-only mode: cache is now extended/built and saved to disk.
# Exit before loading RIGHT side or running emit.  Caller (preflight script)
# typically iterates this over multiple RIGHTs serially to cover all Q-types
# expected at a given partition slot without race risk between workers.
if EXTEND_ONLY = 1 then
    Print("[extend_only] cache extension+save complete, exiting\n");
    LogTo();
    QuitGap();
fi;
H_CACHE_L := H_CACHE;
Print("LEFT: ", Length(H_CACHE_L), " entries\n");

# ---- Load RIGHT side ----
S_MR := SymmetricGroup(MR);
# Block-wreath ambient for RIGHT.  Mirrors W_ML on the LEFT side: normalizer
# and orbit computations during cache build/extend are dramatically cheaper
# in W_MR than in S_MR when RIGHT_PARTITION has >=2 blocks, while preserving
# the same normalizer mathematically (every H ⊆ N_T1×…×N_Tk is W_MR-normal
# iff S_MR-normal).  E.g. [4,4,4,4]: |W_MR|=7,962,624 vs |S_MR|=20,922,789,888,000.
W_MR := BlockWreathFromPartition(RIGHT_PARTITION);
Print("RIGHT block-wreath W_MR order=", Size(W_MR), " (vs |S_MR|=", Factorial(MR), ")\n");
H_CACHE_R := fail;
H2DATA_DIRECT := fail;
# RIGHT side: |T_RIGHT| is small (typically <=720 even for S_6), so always
# compute the full Q-spectrum.  No q-size filter needed here.
if RIGHT_TG_D > 0 then
    T_orig := TransitiveGroup(RIGHT_TG_D, RIGHT_TG_T);
    H2DATA_DIRECT := [ComputeHDataDirect(T_orig, W_MR, LEFT_Q_GROUPS)];
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
            Print("extending RIGHT H_CACHE for new Q-types... (",
                  Length(H_CACHE), " entries)\n");
            n_ext_done := 0;
            n_skip := 0;
            n_slow := 0;
            extend_t0 := Runtime();
            last_hb := Runtime();
            last_hb_count := 0;
            for hi in [1..Length(H_CACHE)] do
                missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
                entry_t0 := Runtime();
                if missing = fail then
                    ExtendHCacheEntry(H_CACHE[hi], W_MR, LEFT_Q_GROUPS);
                    n_ext_done := n_ext_done + 1;
                elif Length(missing) > 0 then
                    ExtendHCacheEntry(H_CACHE[hi], W_MR, LEFT_Q_GROUPS);
                    n_ext_done := n_ext_done + 1;
                else
                    n_skip := n_skip + 1;
                fi;
                entry_dt := Runtime() - entry_t0;
                if entry_dt >= 5000 then
                    n_slow := n_slow + 1;
                    Print("  [slow] hi=", hi,
                          " |H|=", Size(SafeGroup(H_CACHE[hi].H_gens, W_MR)),
                          " miss=", missing, " t=", entry_dt, "ms\n");
                fi;
                if hi - last_hb_count >= 100 or Runtime() - last_hb >= 30000 then
                    Print("  [ext] ", hi, "/", Length(H_CACHE),
                          " (", QuoInt(hi*100, Length(H_CACHE)), "%)",
                          " ext=", n_ext_done, " skip=", n_skip, " slow=", n_slow,
                          " elapsed=", QuoInt(Runtime()-extend_t0, 1000), "s",
                          " rate=", QuoInt(hi*1000, Maximum(Runtime()-extend_t0, 1)), "/s\n");
                    last_hb := Runtime();
                    last_hb_count := hi;
                fi;
            od;
            Print("[ext DONE] ", Length(H_CACHE), " entries in ",
                  QuoInt(Runtime()-extend_t0, 1000), "s",
                  " (ext=", n_ext_done, " skip=", n_skip,
                  " slow=", n_slow, ")\n");
            if CACHE_RIGHT_PATH <> "" then
                SaveHCacheList(CACHE_RIGHT_PATH, H_CACHE);
            fi;
        fi;
    fi;
    if H_CACHE = fail then
        Read(SUBS_RIGHT_PATH);
        SUBGROUPS_RIGHT_RAW := SUBGROUPS;
        Print("computing right H_CACHE for ", Length(SUBGROUPS_RIGHT_RAW), " subgroups...\n");
        H_CACHE := List(SUBGROUPS_RIGHT_RAW, H -> ComputeHCacheEntry(H, W_MR, LEFT_Q_GROUPS));
        if CACHE_RIGHT_PATH <> "" then
            SaveHCacheList(CACHE_RIGHT_PATH, H_CACHE);
        fi;
    fi;
    H_CACHE_R := H_CACHE;
    Print("RIGHT: ", Length(H_CACHE_R), " entries\n");
fi;

# Reconstruct full data on the right side once.  Materialization uses S_MR
# (full symmetric) since downstream H1xH2 fiber products live in S_n.
if H2DATA_DIRECT <> fail then
    H2DATA := H2DATA_DIRECT;
else
    H2DATA := List(H_CACHE_R, e -> ReconstructHData(e, S_MR));
fi;

# ---- 2-block Goursat with optional Burnside swap-fix and generator output ----
# Right-side acts on points [ML+1..ML+MR] when materialized.  For pure
# Burnside m=2, both sides have the same structure (TG(d,t)) but on different
# point sets; the swap maps the (K_H_a, K_T_b)-orbit at left.a == right.b
# (= same K-subgroup) to its inverse-iso at the swap.
shift_R := MappingPermListList([1..MR], [ML+1..ML+MR]);

# Open raw-generators stream ONCE for the lifetime of this GAP run.
# Stream-based writes are 100x+ faster than per-call AppendTo on Cygwin
# because AppendTo opens/closes the file every call (~3-5 ms each).
#
# On fresh start (i_resume_start = 1 and j_resume_start = 1), open in
# truncate mode.  On resume, open in append mode — Python wrapper has
# already truncated EMIT_GENS_PATH to the byte position right after the
# last "# checkpoint" marker, so we just append from there.
#
# CloseStream(GEN_STREAM) is called below at checkpoint exit AND at
# normal completion to flush.
GEN_FILE_OPEN := false;
GEN_STREAM := fail;
if EMIT_GENS_PATH <> "" then
    if i_resume_start = 1 and j_resume_start = 1 then
        # Truncate by opening with append=false.
        GEN_STREAM := OutputTextFile(EMIT_GENS_PATH, false);
    else
        # Append mode (resume).
        GEN_STREAM := OutputTextFile(EMIT_GENS_PATH, true);
    fi;
    SetPrintFormattingStatus(GEN_STREAM, false);
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
    WriteAll(GEN_STREAM, Concatenation("[", s, "]\n"));
end;

# Opt #2: write a generator list directly, skipping Group(...) wrap
# and the subsequent GeneratorsOfGroup() call.  Used when the gen
# list is already known (qsize=1 direct product, qsize=2 fast).
EmitGenList := function(gens)
    local s;
    if not GEN_FILE_OPEN then return; fi;
    if Length(gens) > 0 then
        s := JoinStringsWithSeparator(List(gens, String), ",");
    else
        s := "";
    fi;
    WriteAll(GEN_STREAM, Concatenation("[", s, "]\n"));
end;

FiberProductGeneratorList := function(H1data, h1orb, h2orb, phi)
    local gens, g, img_q, preimg, gen, n;
    gens := [];
    for g in GeneratorsOfGroup(h1orb.H_ref) do
        img_q := Image(phi, Image(h1orb.hom, g));
        preimg := PreImagesRepresentative(h2orb.shifted_hom, img_q);
        gen := g * preimg;
        if gen <> () then Add(gens, gen); fi;
    od;
    for n in GeneratorsOfGroup(Kernel(h2orb.shifted_hom)) do
        if n <> () then Add(gens, n); fi;
    od;
    return gens;
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
          dcs, A1, A2_in_h1, A2_in_h1_gens, tinv, g_swap,
          bench_t0, bench_t1, h2_shifted_hom;

    H1 := H1data.H;
    H2 := fail;
    if GEN_FILE_OPEN then
        EnsureShiftedHData(H2data);
        H2 := H2data.shifted_H;
    fi;

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
                    if BENCH_PHASES = 1 then BENCH_N.n_pairs := BENCH_N.n_pairs + 1; fi;
                    if GEN_FILE_OPEN and (BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx) then
                        if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                        EmitGenList(Concatenation(H1data.H_gens_noid,
                                                  H2data.shifted_H_gens_noid));
                        if BENCH_PHASES = 1 then
                            BENCH_T.t_emit_qsize1 := BENCH_T.t_emit_qsize1 + (Runtime() - bench_t0);
                            BENCH_N.n_emit := BENCH_N.n_emit + 1;
                        fi;
                    fi;
                    if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                        swap_fixed := swap_fixed + 1;
                    fi;
                fi;
            od;
            continue;
        fi;

        # |Q| = 2 fast path: RIGHT is C_2 directly.  For larger RIGHT
        # degrees, build through the quotient homomorphisms; the direct
        # generator shortcut can collapse distinct MR>2 quotient pairs.
        if h1orb.qsize = 2 then
            if true then   # opt #3: direct construction for any MR (was: MR = 2)
                for h2idx in h2idxs do
                    if H2data.orbits[h2idx].qsize <> 2 then continue; fi;
                    total := total + 1;
                    if BENCH_PHASES = 1 then BENCH_N.n_pairs := BENCH_N.n_pairs + 1; fi;
                    h2orb := H2data.orbits[h2idx];
                    if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                        if GEN_FILE_OPEN then
                            if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                            EnsureC2Representative(h1orb);
                            EnsureShiftedKGenerators(h2orb);
                            EnsureShiftedC2Representative(h2orb);
                            EmitGenList(Concatenation(
                                h1orb.K_gens_noid,
                                h2orb.shifted_K_gens_noid,
                                [h1orb.c2_rep * h2orb.shifted_c2_rep]));
                            if BENCH_PHASES = 1 then
                                BENCH_T.t_emit_write := BENCH_T.t_emit_write + (Runtime() - bench_t0);
                                BENCH_T.t_emit_c2_fast := BENCH_T.t_emit_c2_fast + (Runtime() - bench_t0);
                                BENCH_N.n_emit := BENCH_N.n_emit + 1;
                            fi;
                        fi;
                    fi;
                    if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                        swap_fixed := swap_fixed + 1;
                    fi;
                od;
            else
                for h2idx in h2idxs do
                    if H2data.orbits[h2idx].qsize <> 2 then continue; fi;
                    total := total + 1;
                    if BENCH_PHASES = 1 then
                        BENCH_N.n_pairs := BENCH_N.n_pairs + 1;
                        BENCH_N.n_c2_safe_invocations := BENCH_N.n_c2_safe_invocations + 1;
                    fi;
                    h2orb := H2data.orbits[h2idx];
                    if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                        if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                        EnsureHom(h1orb); EnsureHom(h2orb);
                        if BENCH_PHASES = 1 then BENCH_T.t_ensure := BENCH_T.t_ensure + (Runtime() - bench_t0); fi;
                        if GEN_FILE_OPEN then
                            if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                            isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
                            if BENCH_PHASES = 1 then BENCH_T.t_iso := BENCH_T.t_iso + (Runtime() - bench_t0); fi;
                            if isoTH <> fail then
                                # Opt #1: cache shifted_hom on h2orb.  In opt1
                                # t_c2safe_shifted_hom stays 0 (no inline rebuild).
                                # Savings = baseline t_c2safe_shifted_hom - opt1 t_shifted_hom.
                                if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                                EnsureShiftedHom(h2orb, H2);
                                if BENCH_PHASES = 1 then BENCH_T.t_shifted_hom := BENCH_T.t_shifted_hom + (Runtime() - bench_t0); fi;
                                if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                                if BENCH_PHASES = 1 then bench_t1 := Runtime(); fi;
                                fp := _GoursatBuildFiberProduct(
                                    H1, H2,
                                    h1orb.hom,
                                    h2orb.shifted_hom,
                                    InverseGeneralMapping(isoTH),
                                    [1..ML], [ML+1..ML+MR]);
                                if BENCH_PHASES = 1 then
                                    BENCH_T.t_c2safe_gbfp := BENCH_T.t_c2safe_gbfp + (Runtime() - bench_t1);
                                    bench_t1 := Runtime();
                                fi;
                                if fp <> fail then EmitGenerators(fp); fi;
                                if BENCH_PHASES = 1 then
                                    BENCH_T.t_c2safe_emit_write := BENCH_T.t_c2safe_emit_write + (Runtime() - bench_t1);
                                    BENCH_T.t_emit_c2_safe := BENCH_T.t_emit_c2_safe + (Runtime() - bench_t0);
                                    if fp <> fail then BENCH_N.n_emit := BENCH_N.n_emit + 1; fi;
                                fi;
                            fi;
                        fi;
                    fi;
                    if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                        swap_fixed := swap_fixed + 1;
                    fi;
                od;
            fi;
            continue;
        fi;

        # General path: BFS over Aut(Q)-orbits.
        for h2idx in h2idxs do
            h2orb := H2data.orbits[h2idx];
            if h2orb.qsize <> h1orb.qsize then continue; fi;
            if BENCH_PHASES = 1 then BENCH_N.n_pairs := BENCH_N.n_pairs + 1; fi;
            if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
            EnsureHom(h1orb); EnsureHom(h2orb);
            if BENCH_PHASES = 1 then BENCH_T.t_ensure := BENCH_T.t_ensure + (Runtime() - bench_t0); fi;
            if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
            isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
            if BENCH_PHASES = 1 then BENCH_T.t_iso := BENCH_T.t_iso + (Runtime() - bench_t0); fi;
            if isoTH = fail then continue; fi;
            # Optimization (5) 2026-04-29: lazy h1.AutQ.  h2 is the RIGHT
            # factor and is pre-warmed at startup; for high-symmetry RIGHTs
            # (e.g. V_4 where N_{S_4}(V_4)/V_4 = S_3 = Aut), h2 saturates
            # for every orbit and forces n_orb=1.  Test h2 first; only build
            # h1.AutQ when h2 does NOT saturate.  ~2.5x on V_4-right combos.
            if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
            EnsureAutQ(h2orb);
            if h2orb.full_aut <> true then EnsureAutQ(h1orb); fi;
            if BENCH_PHASES = 1 then BENCH_T.t_ensure := BENCH_T.t_ensure + (Runtime() - bench_t0); fi;

            # Optimization (1)+(3) 2026-04-28: early Aut-saturation shortcut
            # using cached full_aut flag.  Skip building isos+idx+KeyOf for
            # the saturated case (the common case for high-symmetry RIGHTs).
            if h1orb.full_aut = true or h2orb.full_aut = true then
                if BENCH_PHASES = 1 then BENCH_N.n_saturated := BENCH_N.n_saturated + 1; fi;
                n_orb := 1;
                orbit_reps_phi := [isoTH];
                dcs := [];   # placeholder; not used in saturated branch
            else
                # Optimization (6) 2026-04-29: DoubleCosets replaces BFS.
                # Parametrize iso phi: h2.Q -> h1.Q as phi = α' o isoTH (standard
                # math composition), α' in Aut(h1.Q).  The action α o phi o β^-1
                # (α in A1 = <h1.A_gens>, β in A2 = <h2.A_gens>) becomes
                # α' -> α α' β'^-1 with β' = isoTH o β o isoTH^-1 in Aut(h1.Q).
                # GAP mapping multiplication applies the left map first, so
                # target-side automorphisms act on r from the right and
                # source-side automorphisms act from the left after transport.
                # Orbits = double cosets A2_in_h1 \ Aut(h1.Q) / A1.
                # Bench-validated 5.4x avg, 22-68x on |Aut|>=1152 buckets, 0
                # mismatches across 21,647 verified pairs.
                if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                A1 := SafeSub(h1orb.AutQ, h1orb.A_gens);
                # Reify A2_in_h1 generators: the natural construction
                # `InverseGeneralMapping(isoTH) * b * isoTH` produces CompositionMapping
                # objects which DoubleCosets / Subgroup may not normalize, leading
                # to over-counted orbits.  Convert each to a direct
                # GroupHomomorphismByImagesNC by evaluating on Q's generators.
                # Use GAP's InducedAutomorphism to transport b ∈ Aut(h2.Q)
                # to Aut(h1.Q) via isoTH.  Returns a native group automorphism
                # of h1.Q (not a CompositionMapping or generic homomorphism),
                # which Subgroup() and DoubleCosets() recognize correctly.
                # Opt #5: A_gens already in canonical Aut(Q); skip isoTH transport.
                A2_in_h1 := SafeSub(h1orb.AutQ, h2orb.A_gens);
                if BENCH_PHASES = 1 then BENCH_T.t_a1a2 := BENCH_T.t_a1a2 + (Runtime() - bench_t0); fi;
                if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                dcs := LookupOrComputeDC(h1orb, A1, A2_in_h1);
                n_orb := Length(dcs);
                # GAP composition: f * g = "apply f first, then g" = standard g o f.
                # Orbit rep phi_i = standard Rep(dcs[i]) o isoTH = GAP isoTH * Rep(dcs[i]).
                orbit_reps_phi := List(dcs, dc ->
                    h2orb.iso_to_can * Representative(dc) * InverseGeneralMapping(h1orb.iso_to_can));
                if BENCH_PHASES = 1 then
                    BENCH_T.t_dc := BENCH_T.t_dc + (Runtime() - bench_t0);
                    BENCH_N.n_dc_call := BENCH_N.n_dc_call + 1;
                    BENCH_N.n_dc_orbits_total := BENCH_N.n_dc_orbits_total + n_orb;
                fi;
            fi;
            total := total + n_orb;

            # Compute swap-orbit-id per orbit rep (used for both within-self-pair
            # canonical emission gate and swap_fixed counter).
            if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
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

            if BENCH_PHASES = 1 then BENCH_T.t_swap := BENCH_T.t_swap + (Runtime() - bench_t0); fi;

            # Generator emission per orbit rep, canonical-gated.
            if GEN_FILE_OPEN then
                if BURNSIDE_M2 = 0 or h2idx > h1_orb_idx then
                    # Non-self canonical: emit all orbit reps.
                    if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                    EnsureShiftedHom(h2orb, H2);
                    if BENCH_PHASES = 1 then BENCH_T.t_shifted_hom := BENCH_T.t_shifted_hom + (Runtime() - bench_t0); fi;
                    for i in [1..n_orb] do
                        if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                        gens_for_fp := FiberProductGeneratorList(
                            H1data, h1orb, h2orb,
                            InverseGeneralMapping(orbit_reps_phi[i]));
                        EmitGenList(gens_for_fp);
                        if BENCH_PHASES = 1 then
                            BENCH_T.t_emit_general := BENCH_T.t_emit_general + (Runtime() - bench_t0);
                            BENCH_N.n_emit := BENCH_N.n_emit + 1;
                        fi;
                    od;
                elif BURNSIDE_M2 = 1 and h2idx = h1_orb_idx then
                    # Self-pair: within-pair canonical (i <= swap_orb_id[i]).
                    if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                    EnsureShiftedHom(h2orb, H2);
                    if BENCH_PHASES = 1 then BENCH_T.t_shifted_hom := BENCH_T.t_shifted_hom + (Runtime() - bench_t0); fi;
                    for i in [1..n_orb] do
                        if swap_orb_id_arr[i] >= i then
                            if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                            gens_for_fp := FiberProductGeneratorList(
                                H1data, h1orb, h2orb,
                                InverseGeneralMapping(orbit_reps_phi[i]));
                            EmitGenList(gens_for_fp);
                            if BENCH_PHASES = 1 then
                                BENCH_T.t_emit_general := BENCH_T.t_emit_general + (Runtime() - bench_t0);
                                BENCH_N.n_emit := BENCH_N.n_emit + 1;
                            fi;
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

# Main loop.  Supports checkpoint/resume: write a "# checkpoint i=I j=J\n"
# marker line to fps.g after each completed pair, and an updated state.g
# with the next-pair (i, j) coordinates.  After each pair, check if 30 min
# elapsed; if so, save state and QuitGap.  Python wrapper restarts; on
# resume, Python truncates fps.g to right after the last marker, GAP reads
# state.g and continues from (i_resume_start, j_resume_start).
#
# Resume in BURNSIDE_M2 mode is not supported (rare/cheap path); always
# starts fresh.
if BURNSIDE_M2 = 1 then
    i_resume_start := 1;
    j_resume_start := 1;
fi;
TOTAL_ORB := resume_total_orb;
TOTAL_FIX := resume_total_fix;
t0 := Runtime();
n_left := Length(H_CACHE_L);
for i in [i_resume_start..n_left] do
    H1data := ReconstructHData(H_CACHE_L[i], S_ML);
    if BURNSIDE_M2 = 1 then
        H2DATA[1] := H1data;
    fi;
    j_lo := 1;
    if i = i_resume_start then j_lo := j_resume_start; fi;
    for j in [j_lo..Length(H2DATA)] do
        res_pair := ProcessPair(H1data, H2DATA[j], j);
        TOTAL_ORB := TOTAL_ORB + res_pair.orbits;
        TOTAL_FIX := TOTAL_FIX + res_pair.swap_fixed;
        # Marker line in fps.g (parser ignores '# ...' lines).  Use stream.
        if GEN_FILE_OPEN then
            WriteAll(GEN_STREAM, Concatenation(
                "# checkpoint i=", String(i), " j=", String(j), "\n"));
        fi;
        # Write state.g with NEXT pair coords.
        if STATE_FILE <> "" then
            next_i := i;
            next_j := j + 1;
            if next_j > Length(H2DATA) then
                next_i := i + 1;
                next_j := 1;
            fi;
            tmp := Concatenation(STATE_FILE, ".tmp");
            PrintTo(tmp, "RESUME_STATE := rec( i := ", next_i,
                    ", j := ", next_j,
                    ", total_orb := ", TOTAL_ORB,
                    ", total_fix := ", TOTAL_FIX,
                    " );\n");
            Exec(Concatenation("mv -f -- '", tmp, "' '", STATE_FILE, "'"));
        fi;
        # Checkpoint: if elapsed exceeds threshold AND there's more to do,
        # quit.  Python wrapper sees state.g and re-invokes us.
        if STATE_FILE <> "" and CHECKPOINT_INTERVAL_MS > 0
           and Runtime() - WORKER_START >= CHECKPOINT_INTERVAL_MS
           and (i < n_left or j < Length(H2DATA)) then
            Print("CHECKPOINT_PAUSE i=", i, " j=", j,
                  " elapsed_ms=", Runtime() - WORKER_START,
                  " orb_so_far=", TOTAL_ORB, "\n");
            # Flush + close gen stream so all writes hit disk before exit.
            if GEN_FILE_OPEN then CloseStream(GEN_STREAM); fi;
            # Dump bench phases at checkpoint too (cumulative; overwrites
            # the previous dump).  Lets a profiler see partial data after
            # one cycle without waiting for full job completion.
            if BENCH_PHASES = 1 and BENCH_PHASES_OUT <> "" then
                PrintTo(BENCH_PHASES_OUT, "");
                AppendTo(BENCH_PHASES_OUT,
                    "checkpoint_partial=1\n",
                    "checkpoint_i=", i, "\n",
                    "checkpoint_j=", j, "\n",
                    "checkpoint_elapsed_ms=", Runtime() - WORKER_START, "\n",
                    "t_iso=", BENCH_T.t_iso, "\n",
                    "t_ensure=", BENCH_T.t_ensure, "\n",
                    "t_a1a2=", BENCH_T.t_a1a2, "\n",
                    "t_dc=", BENCH_T.t_dc, "\n",
                    "t_swap=", BENCH_T.t_swap, "\n",
                    "t_emit_qsize1=", BENCH_T.t_emit_qsize1, "\n",
                    "t_emit_c2_fast=", BENCH_T.t_emit_c2_fast, "\n",
                    "t_emit_c2_safe=", BENCH_T.t_emit_c2_safe, "\n",
                    "t_c2safe_shifted_hom=", BENCH_T.t_c2safe_shifted_hom, "\n",
                    "t_c2safe_gbfp=", BENCH_T.t_c2safe_gbfp, "\n",
                    "t_c2safe_emit_write=", BENCH_T.t_c2safe_emit_write, "\n",
                    "t_emit_general=", BENCH_T.t_emit_general, "\n",
                    "t_shifted_hom=", BENCH_T.t_shifted_hom, "\n",
                    "t_grp_construct=", BENCH_T.t_grp_construct, "\n",
                    "t_emit_write=", BENCH_T.t_emit_write, "\n",
                    "n_pairs=", BENCH_N.n_pairs, "\n",
                    "n_saturated=", BENCH_N.n_saturated, "\n",
                    "n_dc_call=", BENCH_N.n_dc_call, "\n",
                    "n_dc_orbits_total=", BENCH_N.n_dc_orbits_total, "\n",
                    "n_emit=", BENCH_N.n_emit, "\n",
                    "n_c2_safe_invocations=", BENCH_N.n_c2_safe_invocations, "\n",
                    "n_dc_cache_hits=", BENCH_N.n_dc_cache_hits, "\n",
                    "n_dc_cache_misses=", BENCH_N.n_dc_cache_misses, "\n");
            fi;
            LogTo();
            QuitGap();
        fi;
    od;
od;
# All pairs done — flush + close gen stream, clear state.g so Python exits.
if GEN_FILE_OPEN then CloseStream(GEN_STREAM); fi;
if STATE_FILE <> "" and IsExistingFile(STATE_FILE) then
    RemoveFile(STATE_FILE);
fi;

if BURNSIDE_M2 = 1 then
    PREDICTED := (TOTAL_ORB + TOTAL_FIX) / 2;
else
    PREDICTED := TOTAL_ORB;
fi;

Print("RESULT predicted=", PREDICTED,
      " orbits=", TOTAL_ORB,
      " swap_fixed=", TOTAL_FIX,
      " elapsed_ms=", Runtime() - t0, "\n");

if BENCH_PHASES = 1 and BENCH_PHASES_OUT <> "" then
    PrintTo(BENCH_PHASES_OUT, "");
    AppendTo(BENCH_PHASES_OUT,
        "t_iso=", BENCH_T.t_iso, "\n",
        "t_ensure=", BENCH_T.t_ensure, "\n",
        "t_a1a2=", BENCH_T.t_a1a2, "\n",
        "t_dc=", BENCH_T.t_dc, "\n",
        "t_swap=", BENCH_T.t_swap, "\n",
        "t_emit_qsize1=", BENCH_T.t_emit_qsize1, "\n",
        "t_emit_c2_fast=", BENCH_T.t_emit_c2_fast, "\n",
        "t_emit_c2_safe=", BENCH_T.t_emit_c2_safe, "\n",
        "t_c2safe_shifted_hom=", BENCH_T.t_c2safe_shifted_hom, "\n",
        "t_c2safe_gbfp=", BENCH_T.t_c2safe_gbfp, "\n",
        "t_c2safe_emit_write=", BENCH_T.t_c2safe_emit_write, "\n",
        "t_emit_general=", BENCH_T.t_emit_general, "\n",
        "t_shifted_hom=", BENCH_T.t_shifted_hom, "\n",
        "t_grp_construct=", BENCH_T.t_grp_construct, "\n",
        "t_emit_write=", BENCH_T.t_emit_write, "\n",
        "n_pairs=", BENCH_N.n_pairs, "\n",
        "n_saturated=", BENCH_N.n_saturated, "\n",
        "n_dc_call=", BENCH_N.n_dc_call, "\n",
        "n_dc_orbits_total=", BENCH_N.n_dc_orbits_total, "\n",
        "n_emit=", BENCH_N.n_emit, "\n",
        "n_c2_safe_invocations=", BENCH_N.n_c2_safe_invocations, "\n",
        "n_dc_cache_hits=", BENCH_N.n_dc_cache_hits, "\n",
        "n_dc_cache_misses=", BENCH_N.n_dc_cache_misses, "\n");
fi;
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

# Linear-orbits flag + Stage A/B prototype load (Cut 3 — applies to
# ExtendHCacheEntry / ComputeHCacheEntry / ComputeHDataDirect for the
# C_2/V_4/D_8 qids).  Default ON; set PRED_USE_LINEAR_ORBITS=0 to force legacy.
USE_LINEAR_ORBITS := __USE_LINEAR_ORBITS__;
if USE_LINEAR_ORBITS = 1 then
    Print("[USE_LINEAR_ORBITS=1] loading Stage A/B prototypes...\n");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_a.g");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_b.g");
fi;

# Path to lifting_algorithm.g for _GoursatBuildFiberProduct.
if not IsBound(_GoursatBuildFiberProduct) then Read("__LIFTING_G__"); fi;

# Common helpers (same as GAP_DRIVER).
ConjAction := function(K, g) return K^g; end;

SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

# === META catalog + H-iso -> Q-iso cache (Opts 1+2, 2026-05-09) ===========
# Opt 1: avoid re-reading the 6065-entry q_catalog.g per ComputeOrLoadLeftQGroups
#        call within a single GAP session.  _META_CATALOG_LOADED_PATH holds
#        the path that was loaded into the global META_Q_CATALOG; subsequent
#        calls with the same path reuse the in-memory list.
# Opt 2: file-based per-H-iso QT cache.  Master file h_to_qs.g shared across
#        all super-batches and orchestrator runs; workers READ master,
#        accumulate new entries in _META_H_TO_QS_NEW, write per-session
#        fragments, orchestrator merges fragments into master.
#        H_TO_QS lookup is keyed by SafeId(H) string.  Only safe iso-classes
#        (h_id[2] = 0) are cached; unsafe (heuristic SafeId) bypass cache.
if not IsBound(_META_CATALOG_LOADED_PATH) then
    _META_CATALOG_LOADED_PATH := "";
fi;
if not IsBound(_META_H_TO_QS_LOADED_PATH) then
    _META_H_TO_QS_LOADED_PATH := "";
fi;
if not IsBound(_META_H_TO_QS_RECORD) then
    _META_H_TO_QS_RECORD := rec();   # sanitized-key -> qid list
fi;
if not IsBound(_META_H_TO_QS_NEW) then
    _META_H_TO_QS_NEW := [];          # list of [h_id_str, [qid, ...]]
fi;

# Convert SafeId(H) string (e.g. "[ 36, 0, [ 36, 3 ] ]") to a valid GAP
# record-field identifier by stripping spaces/brackets.  Deterministic and
# collision-free for SafeId outputs.
SanitizeHidStr := function(s)
    local out, c;
    out := "h";
    for c in s do
        if c = ' ' or c = ',' then Add(out, '_');
        elif c = '[' or c = ']' then ;
        else Add(out, c);
        fi;
    od;
    return out;
end;

# Load master catalog from path; cache in METAQCATALOG global.  Skip disk
# read if already loaded from same path in this GAP session.
_LoadMasterCatalog := function(path)
    if path = "" then return fail; fi;
    if _META_CATALOG_LOADED_PATH = path and IsBound(META_Q_CATALOG) then
        return META_Q_CATALOG;
    fi;
    if not IsExistingFile(path) then return fail; fi;
    META_Q_CATALOG_SAVED_OK := false;
    Read(path);
    if IsBound(META_Q_CATALOG_SAVED_OK) and META_Q_CATALOG_SAVED_OK = true
       and IsBound(META_Q_CATALOG) then
        _META_CATALOG_LOADED_PATH := path;
        Print("[QGroups] loaded master catalog: ", Length(META_Q_CATALOG),
              " types from ", path, "\n");
        return META_Q_CATALOG;
    fi;
    Print("[QGroups] master catalog file present but invalid sentinel - ignoring\n");
    return fail;
end;

# Load h_to_qs master file (a list of [h_id_str, qid_list] pairs).  Builds
# an in-memory record keyed by SanitizeHidStr(h_id_str) for O(log) lookup.
# Idempotent within a GAP session (only re-reads if path differs).  Also
# loads pending fragments produced by other workers in this run.
_LoadHToQs := function(master_path, fragments_dir)
    local rec_obj, entry, key, fragments, fpath, frag_count, frag_added;
    if _META_H_TO_QS_LOADED_PATH = master_path and master_path <> "" then
        return _META_H_TO_QS_RECORD;
    fi;
    rec_obj := rec();
    if master_path <> "" and IsExistingFile(master_path) then
        META_H_TO_QS_SAVED_OK := false;
        META_H_TO_QS := [];
        Read(master_path);
        if IsBound(META_H_TO_QS_SAVED_OK) and META_H_TO_QS_SAVED_OK = true
           and IsBound(META_H_TO_QS) then
            for entry in META_H_TO_QS do
                key := SanitizeHidStr(entry[1]);
                rec_obj.(key) := entry[2];
            od;
            Print("[QGroups] loaded H_TO_QS master: ",
                  Length(META_H_TO_QS), " entries from ", master_path, "\n");
        fi;
    fi;
    # Also pre-merge any fragments that have not yet been consolidated.
    # Workers in the current run may have written fragments before this
    # worker started; reading them gives in-process cache hits.
    frag_count := 0;
    frag_added := 0;
    if fragments_dir <> "" and IsDirectoryPath(fragments_dir) then
        fragments := DirectoryContents(fragments_dir);
        for fpath in fragments do
            if Length(fpath) >= 2 and fpath{[Length(fpath)-1..Length(fpath)]} = ".g" then
                META_H_TO_QS_NEW_SAVED_OK := false;
                META_H_TO_QS_NEW := [];
                Read(Concatenation(fragments_dir, "/", fpath));
                if IsBound(META_H_TO_QS_NEW_SAVED_OK) and META_H_TO_QS_NEW_SAVED_OK = true then
                    frag_count := frag_count + 1;
                    for entry in META_H_TO_QS_NEW do
                        key := SanitizeHidStr(entry[1]);
                        if not IsBound(rec_obj.(key)) then
                            rec_obj.(key) := entry[2];
                            frag_added := frag_added + 1;
                        fi;
                    od;
                fi;
            fi;
        od;
        if frag_count > 0 then
            Print("[QGroups] absorbed ", frag_count, " fragment(s) -> ",
                  frag_added, " new H entries\n");
        fi;
    fi;
    _META_H_TO_QS_LOADED_PATH := master_path;
    _META_H_TO_QS_RECORD := rec_obj;
    # Reset the new-entries accumulator for THIS session (we never re-emit
    # entries we just absorbed from fragments).
    _META_H_TO_QS_NEW := [];
    return _META_H_TO_QS_RECORD;
end;

# Append _META_H_TO_QS_NEW to a fragment file (atomic tmp+mv).  Caller is
# responsible for clearing _META_H_TO_QS_NEW after a successful write if it
# wants to avoid double-emitting on subsequent calls in the same session.
_SaveHToQsFragment := function(fragment_path)
    local tmp;
    if fragment_path = "" or Length(_META_H_TO_QS_NEW) = 0 then return; fi;
    tmp := Concatenation(fragment_path, ".tmp");
    PrintTo(tmp, "META_H_TO_QS_NEW := ", _META_H_TO_QS_NEW, ";\n",
                 "META_H_TO_QS_NEW_SAVED_OK := true;\n");
    Exec(Concatenation("mv -f -- '", tmp, "' '", fragment_path, "'"));
    Print("[QGroups] saved H_TO_QS fragment: ", Length(_META_H_TO_QS_NEW),
          " new entries -> ", fragment_path, "\n");
end;

# Cache the SUBS_RIGHT walk: walking each R in subs_right.g and enumerating
# `for K in NormalSubgroups(R)` to get the Q-types of the right side.  Cache
# is keyed by cache_right_path (stable across runs).  Sidecar file is
# <cache_right_path>.right_qgroups.g; sentinel RIGHT_QGROUPS_FROM_SUBS_SAVED_OK.
LoadOrComputeRightQGroupsFromSubs := function(subs_right_path, cache_right_path)
    local sidecar, tmp, R, K, Q, qid, seen, result;
    if subs_right_path = "" then return []; fi;
    if cache_right_path <> "" then
        sidecar := Concatenation(cache_right_path, ".right_qgroups.g");
        if IsExistingFile(sidecar) then
            RIGHT_QGROUPS_FROM_SUBS_SAVED_OK := false;
            Read(sidecar);
            if IsBound(RIGHT_QGROUPS_FROM_SUBS_SAVED_OK) and RIGHT_QGROUPS_FROM_SUBS_SAVED_OK = true
               and IsBound(RIGHT_QGROUPS_FROM_SUBS) then
                Print("[QGroups] loaded RIGHT-derived qgroups from cache: ",
                      Length(RIGHT_QGROUPS_FROM_SUBS), " types from ", sidecar, "\n");
                return RIGHT_QGROUPS_FROM_SUBS;
            fi;
        fi;
    else
        sidecar := "";
    fi;
    Read(subs_right_path);
    result := [];
    seen := Set([]);
    for R in SUBGROUPS do
        for K in NormalSubgroups(R) do
            if Size(K) = Size(R) then continue; fi;
            Q := R/K;
            qid := SafeId(Q);
            if not (qid in seen) then
                AddSet(seen, qid);
                Add(result, Q);
            fi;
        od;
    od;
    # Normalize FactorGroup objects (their abstract f1, f2 generator names
    # would not be re-bindable on Read of the cached sidecar).
    result := List(result, function(q)
        local n, q_id;
        n := Size(q);
        if IdGroupsAvailable(n) then
            q_id := IdGroup(q);
            return SmallGroup(n, q_id[2]);
        else
            return Image(IsomorphismPermGroup(q));
        fi;
    end);
    if sidecar <> "" then
        tmp := Concatenation(sidecar, ".tmp");
        PrintTo(tmp, "RIGHT_QGROUPS_FROM_SUBS := ", result, ";\n",
                     "RIGHT_QGROUPS_FROM_SUBS_SAVED_OK := true;\n");
        Exec(Concatenation("mv -f -- '", tmp, "' '", sidecar, "'"));
        Print("[QGroups] saved RIGHT-derived qgroups: ", Length(result),
              " types -> ", sidecar, "\n");
    fi;
    return result;
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
    res := rec(H := H, N := N,
        H_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_H := fail, shifted_H_gens_noid := fail,
        orbits := []);
    # Trivial-quotient orbit (always present; hom is fast for H/H).
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N, AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
        K_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_K_gens_noid := fail, c2_rep := fail, shifted_c2_rep := fail,
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
            Stab := Stab, AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
            K_gens_noid := Filtered(GeneratorsOfGroup(K), g -> g <> ()),
            shifted_K_gens_noid := fail, c2_rep := fail, shifted_c2_rep := fail,
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
    local qid_str, can_entry, raw_a_gens;
    if orb.AutQ <> fail then return; fi;
    if orb.qsize <= 1 then return; fi;   # trivial Q has no auto
    EnsureHom(orb);   # AutQ depends on Q
    # Opt #5: canonical Q registry.  First orbit with a given qid registers
    # its Q + AutQ as canonical.  Subsequent orbits compute iso_to_can and
    # share the canonical AutQ.  A_gens are transported to canonical Aut(Q).
    qid_str := String(orb.qid);
    if not IsBound(QCAN_TABLE.(qid_str)) then
        QCAN_TABLE.(qid_str) := rec(Q := orb.Q, AutQ := AutomorphismGroup(orb.Q));
        orb.iso_to_can := IdentityMapping(orb.Q);
    else
        can_entry := QCAN_TABLE.(qid_str);
        orb.iso_to_can := IsomorphismGroups(orb.Q, can_entry.Q);
        if orb.iso_to_can = fail then
            # Should not happen: matching qid implies iso classes match.  Fall
            # back to fresh AutQ + identity to avoid runtime error; A_gens
            # below stay in orb.Q's Aut, so canonical sharing won't apply.
            QCAN_TABLE.(qid_str) := rec(Q := orb.Q, AutQ := AutomorphismGroup(orb.Q));
            orb.iso_to_can := IdentityMapping(orb.Q);
        fi;
    fi;
    can_entry := QCAN_TABLE.(qid_str);
    orb.AutQ := can_entry.AutQ;
    raw_a_gens := InducedAutoGens(orb.Stab, orb.H_ref, orb.hom);
    orb.A_gens := List(raw_a_gens, a -> InducedAutomorphism(orb.iso_to_can, a));
    # Optimization (3) 2026-04-28: cache full_aut.
    if Length(orb.A_gens) = 0 then
        orb.full_aut := false;
    else
        orb.full_aut := (Size(Subgroup(orb.AutQ, orb.A_gens)) = Size(orb.AutQ));
    fi;
end;

# Opt #1: lazily compute and cache the shifted-right quotient hom
# on h2orb.shifted_hom.  Used by C2-safe and general emit paths to
# skip rebuilding CompositionMapping(orb.hom, ConjugatorIsomorphism(
# H2_shifted, shift_R^-1)) on every emission.  Within one predict()
# call, H2_shifted is fixed for a given h2orb (parent H2data.H +
# file-global shift_R), so safe to reuse.
EnsureShiftedHom := function(orb, H2_shifted)
    if orb.shifted_hom <> fail then return; fi;
    EnsureHom(orb);
    orb.shifted_hom := CompositionMapping(orb.hom,
        ConjugatorIsomorphism(H2_shifted, shift_R^-1));
end;

EnsureShiftedHData := function(Hdata)
    if Hdata.shifted_H <> fail then return; fi;
    Hdata.shifted_H := Hdata.H^shift_R;
    Hdata.shifted_H_gens_noid := List(Hdata.H_gens_noid, g -> g^shift_R);
end;

EnsureShiftedKGenerators := function(orb)
    if orb.shifted_K_gens_noid <> fail then return; fi;
    orb.shifted_K_gens_noid := List(orb.K_gens_noid, g -> g^shift_R);
end;

EnsureC2Representative := function(orb)
    if orb.c2_rep <> fail then return; fi;
    orb.c2_rep := First(GeneratorsOfGroup(orb.H_ref),
                         g -> not (g in orb.K));
end;

EnsureShiftedC2Representative := function(orb)
    if orb.shifted_c2_rep <> fail then return; fi;
    EnsureC2Representative(orb);
    orb.shifted_c2_rep := orb.c2_rep^shift_R;
end;

# Opt #4: cache DoubleCosets results per h1orb keyed by the A2_in_h1
# subgroup.  Linear-list lookup; comparison via group equality.  Cache
# grows with distinct A2_in_h1 subgroups seen for this h1orb (bounded
# by the number of distinct quotient/iso classes among matching h2orbs).
LookupOrComputeDC := function(h1orb, A1, A2_in_h1)
    local entry, dcs;
    if h1orb.dc_cache = fail then h1orb.dc_cache := []; fi;
    for entry in h1orb.dc_cache do
        if entry[1] = A2_in_h1 then
            if BENCH_PHASES = 1 then BENCH_N.n_dc_cache_hits := BENCH_N.n_dc_cache_hits + 1; fi;
            return entry[2];
        fi;
    od;
    if BENCH_PHASES = 1 then BENCH_N.n_dc_cache_misses := BENCH_N.n_dc_cache_misses + 1; fi;
    dcs := DoubleCosets(h1orb.AutQ, A2_in_h1, A1);
    Add(h1orb.dc_cache, [A2_in_h1, dcs]);
    return dcs;
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
    local result, seen, t, T, K, Q, qid, key, cache_path, slash, i, t0;
    # Two-tier cache: in-memory (per-GAP-session) + file (across sessions).
    # Without caching, NrTransitiveGroups(MR)=301 at MR=12 forces a ~hour-long
    # walk on every call, multiplied by hundreds of per-job invocations.
    if not IsBound(_REQUIRED_QGROUPS_CACHE) then _REQUIRED_QGROUPS_CACHE := rec(); fi;
    key := Concatenation("m", String(M_R));
    if IsBound(_REQUIRED_QGROUPS_CACHE.(key)) then
        return _REQUIRED_QGROUPS_CACHE.(key);
    fi;
    # File cache: <META_CATALOG_PATH-dir>/required_qgroups_m<MR>.g
    cache_path := "";
    if IsBound(META_CATALOG_PATH) and META_CATALOG_PATH <> "" then
        slash := 0;
        for i in [Length(META_CATALOG_PATH), Length(META_CATALOG_PATH)-1..1] do
            if META_CATALOG_PATH[i] = '/' then slash := i; break; fi;
        od;
        if slash > 0 then
            cache_path := Concatenation(
                META_CATALOG_PATH{[1..slash]},
                "required_qgroups_m", String(M_R), ".g");
        fi;
    fi;
    if cache_path <> "" and IsExistingFile(cache_path) then
        REQUIRED_QGROUPS_CACHED_SAVED_OK := false;
        Read(cache_path);
        if IsBound(REQUIRED_QGROUPS_CACHED_SAVED_OK) and REQUIRED_QGROUPS_CACHED_SAVED_OK = true
           and IsBound(REQUIRED_QGROUPS_CACHED) then
            _REQUIRED_QGROUPS_CACHE.(key) := REQUIRED_QGROUPS_CACHED;
            Print("[RequiredQGroups] loaded from file cache: ",
                  Length(REQUIRED_QGROUPS_CACHED), " types for M_R=", M_R, "\n");
            return REQUIRED_QGROUPS_CACHED;
        fi;
    fi;
    # Compute
    result := [];
    seen := Set([]);
    if M_R = 0 then
        _REQUIRED_QGROUPS_CACHE.(key) := result;
        return result;
    fi;
    t0 := Runtime();
    Print("[RequiredQGroups] computing for M_R=", M_R, " (",
          NrTransitiveGroups(M_R), " transitive groups)...\n");
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
    # Normalize for safe re-Read (FactorGroup uses unbound generator names).
    result := List(result, function(q)
        local n, q_id;
        n := Size(q);
        if IdGroupsAvailable(n) then
            q_id := IdGroup(q);
            return SmallGroup(n, q_id[2]);
        else
            return Image(IsomorphismPermGroup(q));
        fi;
    end);
    Print("[RequiredQGroups] computed M_R=", M_R, ": ", Length(result),
          " types in ", Runtime() - t0, "ms\n");
    if cache_path <> "" then
        PrintTo(Concatenation(cache_path, ".tmp"),
                "REQUIRED_QGROUPS_CACHED := ", result, ";\n",
                "REQUIRED_QGROUPS_CACHED_SAVED_OK := true;\n");
        Exec(Concatenation("mv -f -- '", cache_path, ".tmp' '", cache_path, "'"));
        Print("[RequiredQGroups] saved file cache for M_R=", M_R, "\n");
    fi;
    _REQUIRED_QGROUPS_CACHE.(key) := result;
    return result;
end;

# Q-iso classes attainable as nontrivial quotients of any group in `groups`.
# Used to derive a TIGHT LEFT_Q_GROUPS filter: in Goursat's theorem the common
# quotient Q must be a quotient of BOTH factors, so deriving Q-types from the
# LEFT subgroup list is at least as tight as RequiredQGroups(M_R) and is
# DRAMATICALLY tighter when M_R >= 6 (where RequiredQGroups returns `fail` =
# full coverage, forcing NormalSubgroups(H) on every right-side H).
QuotientTypesOfGroups := function(arg)
    # Discovers Q-types achievable as H/K for some H in `groups`.
    #
    # When called with one argument (legacy): runs `for K in NormalSubgroups(H)`
    # discovery with iso-class dedup.  Can hang for hours on hostile H entries
    # (observed in S20 production).
    #
    # When called with two arguments (catalog-driven): iterates the master
    # catalog and uses `HasQuotientType(H, Q)` as a sound prefilter.  Never
    # calls `NormalSubgroups(H)` -- bounded runtime.  Result is a SUPERSET of
    # actually-achievable Q's (false positives from HasQuotientType returning
    # true for non-pgroup Q are filtered out at cache-build time by
    # `_EnumerateNormalsForQGroups`).
    #
    # When called with three arguments: third arg is a SafeId-keyed record of
    # already-known H-iso -> qid-list mappings (the META_H_TO_QS cache).  On
    # cache hit for a safe H, skips the catalog sweep and uses cached qids.
    # On miss, runs the sweep and appends the new entry to _META_H_TO_QS_NEW.
    #
    # Iso-class dedup is gated on SafeId(H)[2] = 0 in all paths.
    local groups, master_catalog, h_to_qs, result, seen_qids, seen_h_ids,
          n_total, idx, last_qt_hb, H, h_id, h_id_str, h_id_san, K, Q, q,
          qid, n_skipped, n_safe, master_qids, q_idx, h_size, q_size,
          cached_qids, hit_qids, n_cache_hit, n_cache_miss, qid_to_pos,
          pos;
    groups := arg[1];
    if Length(arg) >= 2 then master_catalog := arg[2]; else master_catalog := fail; fi;
    if Length(arg) >= 3 then h_to_qs := arg[3]; else h_to_qs := fail; fi;
    result := [];
    seen_qids := Set([]);
    seen_h_ids := Set([]);
    n_total := Length(groups);
    last_qt_hb := Runtime();
    idx := 0;
    n_skipped := 0;
    n_safe := 0;
    n_cache_hit := 0;
    n_cache_miss := 0;

    if master_catalog <> fail and Length(master_catalog) > 0 then
        # Catalog-driven path.  Iterates each H against master_catalog using
        # the cheap HasQuotientType structural check.  master_catalog is
        # expected in ascending size order (as seeded by seed_meta_catalog.py),
        # which lets us break the inner loop once Size(Q) > Size(H).
        Print("    [QuotientTypesOfGroups] catalog-driven: |catalog|=",
              Length(master_catalog), " |groups|=", n_total, "\n");
        master_qids := List(master_catalog, SafeId);
        # Index from String(qid) to position in master_catalog for O(1)
        # cache-hit lookup (avoids linear search per cached qid).
        qid_to_pos := rec();
        for q_idx in [1..Length(master_qids)] do
            qid_to_pos.(SanitizeHidStr(String(master_qids[q_idx]))) := q_idx;
        od;
        for H in groups do
            idx := idx + 1;
            if Runtime() - last_qt_hb >= 60000 then
                Print("    [QuotientTypesOfGroups] progress ", idx, "/", n_total,
                      " types=", Length(result),
                      " H_iso=", Length(seen_h_ids),
                      " safe_dedup=", n_skipped,
                      " unsafe=", n_safe,
                      " cache_hit=", n_cache_hit,
                      " cache_miss=", n_cache_miss, "\n");
                last_qt_hb := Runtime();
            fi;
            h_id := SafeId(H);
            h_id_san := "";
            if h_id[2] = 0 then
                h_id_str := String(h_id);
                if h_id_str in seen_h_ids then
                    n_skipped := n_skipped + 1;
                    continue;
                fi;
                AddSet(seen_h_ids, h_id_str);
                h_id_san := SanitizeHidStr(h_id_str);
                # Opt 2: cache hit on H iso-class
                if h_to_qs <> fail and IsBound(h_to_qs.(h_id_san)) then
                    cached_qids := h_to_qs.(h_id_san);
                    n_cache_hit := n_cache_hit + 1;
                    for qid in cached_qids do
                        if qid in seen_qids then continue; fi;
                        AddSet(seen_qids, qid);
                        pos := 0;
                        if IsBound(qid_to_pos.(SanitizeHidStr(String(qid)))) then
                            pos := qid_to_pos.(SanitizeHidStr(String(qid)));
                        fi;
                        if pos > 0 then Add(result, master_catalog[pos]); fi;
                    od;
                    continue;
                fi;
                n_cache_miss := n_cache_miss + 1;
            else
                n_safe := n_safe + 1;
            fi;
            hit_qids := [];
            h_size := Size(H);
            for q_idx in [1..Length(master_catalog)] do
                q_size := Size(master_catalog[q_idx]);
                if q_size = 1 then continue; fi;              # legacy excludes K=H (trivial Q)
                if q_size > h_size then break; fi;            # ascending-order early exit
                if h_size mod q_size <> 0 then continue; fi;  # Lagrange divides filter
                qid := master_qids[q_idx];
                if HasQuotientType(H, master_catalog[q_idx]) then
                    Add(hit_qids, qid);
                    if not (qid in seen_qids) then
                        AddSet(seen_qids, qid);
                        Add(result, master_catalog[q_idx]);
                    fi;
                fi;
            od;
            # Opt 2: record this H's qid list for future runs (only if safe).
            # Update in-memory cache so subsequent QuotientTypesOfGroups calls
            # in this session hit the cache, and append to NEW list for the
            # next fragment write.
            if h_id[2] = 0 and h_to_qs <> fail then
                h_to_qs.(h_id_san) := hit_qids;
                Add(_META_H_TO_QS_NEW, [h_id_str, hit_qids]);
            fi;
            if Length(result) >= Length(master_catalog) then break; fi;
        od;
        Print("    [QuotientTypesOfGroups] catalog-driven done: ",
              Length(result), " types (subset of |catalog|=",
              Length(master_catalog), ")  cache_hit=", n_cache_hit,
              "  cache_miss=", n_cache_miss, "\n");
        return result;
    fi;

    # Legacy NormalSubgroups path (used when master_catalog not supplied).
    for H in groups do
        idx := idx + 1;
        if Runtime() - last_qt_hb >= 60000 then
            Print("    [QuotientTypesOfGroups] progress ", idx, "/", n_total,
                  " types_so_far=", Length(result),
                  " H_iso_classes_safe=", Length(seen_h_ids),
                  " H_safe_dedup=", n_skipped,
                  " H_unsafe_processed=", n_safe, "\n");
            last_qt_hb := Runtime();
        fi;
        h_id := SafeId(H);
        if h_id[2] = 0 then
            h_id_str := String(h_id);
            if h_id_str in seen_h_ids then
                n_skipped := n_skipped + 1;
                continue;
            fi;
            AddSet(seen_h_ids, h_id_str);
        else
            n_safe := n_safe + 1;
        fi;
        for K in NormalSubgroups(H) do
            if Size(K) = Size(H) then continue; fi;
            Q := H/K;
            qid := SafeId(Q);
            if not (qid in seen_qids) then
                AddSet(seen_qids, qid);
                Add(result, Q);
            fi;
        od;
    od;
    return result;
end;

ComputeOrLoadLeftQGroups := function(arg)
    # Three-lane Q-discovery for LEFT subgroups:
    #   Lane 1 (small): catalog-driven HasQuotientType sweep against
    #     META_Q_CATALOG (cap MAX_Q_SIZE; bounded per H iso-class).
    #   Lane 2 (forced-large): walk each right cache (already-built or
    #     loaded from prior runs); for each Q-iso of size > cap, run
    #     TargetedQuotientExists on left subgroups.  Per-Q early exit.
    #   Lane 3 (unknown-large promotion): for each order > cap dividing
    #     some |H_left| and not yet covered by lanes 1+2, enumerate
    #     SmallGroup(n, *) candidates and test via TargetedQuotientExists.
    #     FATAL if any order has too many SmallGroups (catalog must extend).
    #
    # Args:
    #   arg[1] = groups (LEFT subgroup list)
    #   arg[2] = qgroups_path (sidecar; "" disables persistence)
    #   arg[3] = master_catalog_path (lane 1 catalog; "" => legacy
    #            NormalSubgroups path -- DEPRECATED, may hang)
    #   arg[4] = right_cache_paths (list of paths; [] disables lane 2)
    #   arg[5] = h_to_qs_master_path (Opt 2 master cache; "" disables)
    #   arg[6] = h_to_qs_fragment_path (Opt 2 per-session fragment; "" disables)
    #   arg[7] = h_to_qs_fragments_dir (Opt 2 sibling fragments dir; "" disables)
    #
    # Validation: sidecar ends with `LEFT_Q_GROUPS_SAVED_OK := true;` sentinel.
    # If missing/false after Read, treat as corrupt and recompute.
    local groups, qgroups_path, master_catalog_path, right_cache_paths,
          h_to_qs_master_path, h_to_qs_fragment_path, h_to_qs_fragments_dir,
          h_to_qs, result, tmp, master_catalog, small_qgroups, forced_qrecs,
          forced_qrecs_dedup, seen_qid_strs, qr, key, forced_qgroups,
          covered_qids, promoted_qgroups, path, MANAGEABLE_THRESHOLD,
          QT_CAP;
    groups := arg[1];
    qgroups_path := arg[2];
    if Length(arg) >= 3 then master_catalog_path := arg[3]; else master_catalog_path := ""; fi;
    if Length(arg) >= 4 then right_cache_paths := arg[4]; else right_cache_paths := []; fi;
    if Length(arg) >= 5 then h_to_qs_master_path := arg[5]; else h_to_qs_master_path := ""; fi;
    if Length(arg) >= 6 then h_to_qs_fragment_path := arg[6]; else h_to_qs_fragment_path := ""; fi;
    if Length(arg) >= 7 then h_to_qs_fragments_dir := arg[7]; else h_to_qs_fragments_dir := ""; fi;

    QT_CAP := 200;
    MANAGEABLE_THRESHOLD := 1000;

    LEFT_Q_GROUPS_SAVED_OK := false;
    if qgroups_path <> "" and IsExistingFile(qgroups_path) then
        Read(qgroups_path);
        if IsBound(LEFT_Q_GROUPS_SAVED_OK) and LEFT_Q_GROUPS_SAVED_OK = true
           and IsBound(LEFT_Q_GROUPS) then
            Print("[QGroups] loaded from cache: ", Length(LEFT_Q_GROUPS),
                  " types from ", qgroups_path, "\n");
            return LEFT_Q_GROUPS;
        fi;
        Print("[QGroups] cache file present but invalid sentinel - recomputing\n");
    fi;

    # Opt 1: cached master-catalog load (skips disk re-read within session)
    master_catalog := _LoadMasterCatalog(master_catalog_path);
    # Opt 2: cached H-iso -> Q-iso lookup record (cross-super-batch)
    h_to_qs := _LoadHToQs(h_to_qs_master_path, h_to_qs_fragments_dir);

    # Lane 1: small-catalog discovery
    if master_catalog <> fail then
        small_qgroups := QuotientTypesOfGroups(groups, master_catalog, h_to_qs);
    else
        small_qgroups := QuotientTypesOfGroups(groups);
    fi;
    Print("[QGroups] lane 1 (small): ", Length(small_qgroups), " types\n");

    # Opt 2: persist new H-iso entries discovered during this lane-1 sweep.
    # Do NOT reset _META_H_TO_QS_NEW -- it accumulates across all calls in
    # this GAP session, and each save overwrites the fragment with the
    # cumulative new entries (write-once-per-session-end semantics).
    _SaveHToQsFragment(h_to_qs_fragment_path);

    # Lane 2: forced-large from right caches
    forced_qrecs := [];
    for path in right_cache_paths do
        Append(forced_qrecs, ForcedQRepsFromHCache(path, QT_CAP));
    od;
    # Dedup by qid string across all right caches.
    seen_qid_strs := Set([]);
    forced_qrecs_dedup := [];
    for qr in forced_qrecs do
        key := String(qr.qid);
        if key in seen_qid_strs then continue; fi;
        AddSet(seen_qid_strs, key);
        Add(forced_qrecs_dedup, qr);
    od;
    if Length(forced_qrecs_dedup) > 0 then
        Print("[QGroups] lane 2 (forced-large): ", Length(forced_qrecs_dedup),
              " unique Q-iso candidates from ", Length(right_cache_paths),
              " right cache(s)\n");
        forced_qgroups := ProcessForcedLargeQTypes(groups, forced_qrecs_dedup);
        Print("[QGroups] lane 2 (forced-large): ", Length(forced_qgroups),
              " types accepted\n");
    else
        forced_qgroups := [];
    fi;

    # Lane 3: unknown-large promotion
    covered_qids := Set(Concatenation(
        List(small_qgroups, SafeId),
        List(forced_qgroups, SafeId)));
    promoted_qgroups := PromoteUnknownLargeOrders(
        groups, covered_qids, QT_CAP, MANAGEABLE_THRESHOLD);
    if Length(promoted_qgroups) > 0 then
        Print("[QGroups] lane 3 (promoted): ", Length(promoted_qgroups),
              " types accepted\n");
    fi;

    result := Concatenation(small_qgroups, forced_qgroups, promoted_qgroups);
    Print("[QGroups] union: ", Length(result), " types\n");

    # Normalize for serialization: FactorGroup objects (H/K) print with
    # abstract generator names (f1, f2, ...) that aren't bound at re-Read
    # time, so PrintTo(file, factorgroup) writes unreadable code.
    result := List(result, function(q)
        local n, q_id;
        n := Size(q);
        if IdGroupsAvailable(n) then
            q_id := IdGroup(q);
            return SmallGroup(n, q_id[2]);
        else
            return Image(IsomorphismPermGroup(q));
        fi;
    end);
    if qgroups_path <> "" then
        tmp := Concatenation(qgroups_path, ".tmp");
        PrintTo(tmp, "LEFT_Q_GROUPS := ", result, ";\n",
                "LEFT_Q_GROUPS_SAVED_OK := true;\n");
        Exec(Concatenation("mv -f -- '", tmp, "' '", qgroups_path, "'"));
        Print("[QGroups] saved to cache: ", Length(result),
              " types -> ", qgroups_path, "\n");
    fi;
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
# --- Quotient-free 2-group small-quotient enumeration for {C_2, V_4, D_8} ---
# Profiling on |H|=1024 entries showed the BFS-then-classify approach spent
# 42-52% in H/K NaturalHom calls (3-5ms each x ~12k calls) and 32% in
# Index2-via-abelianization, total ~106-130s per entry.  The targets
# {C_2, V_4, D_8} are structurally specific enough that we can enumerate
# the kernels DIRECTLY without ever building H/K.

Index2SubgroupsViaAbelianization := function(M)
    local D, hom, A, maxs;
    D := DerivedSubgroup(M);
    if Size(D) = Size(M) then return []; fi;
    hom := NaturalHomomorphismByNormalSubgroup(M, D);
    A := Range(hom);
    maxs := Filtered(MaximalSubgroupClassReps(A), U -> Index(A, U) = 2);
    return Set(List(maxs, U -> PreImage(hom, U)));
end;

# N_L := [H,L] · L^p.  Every K with H/K a central-C_p extension of H/L
# must contain N_L (forces K normal in H, L/K central, L/K elem-ab of
# exponent p).  Specialized to p=2 for D_8 enumeration; general p is
# used by PGroupQuotientKernels for odd-prime Q.
RelativePhiSubgroup := function(H, L, p)
    local commHL, pgens, N;
    commHL := CommutatorSubgroup(H, L);
    pgens := List(GeneratorsOfGroup(L), x -> x^p);
    N := SubgroupNC(L, Concatenation(GeneratorsOfGroup(commHL),
                                     Filtered(pgens, x -> x <> ())));
    if not IsNormal(L, N) then N := NormalClosure(L, N); fi;
    return N;
end;

# D_8 kernel enumeration with two early-skip filters per V_4 layer L:
#  - if D = [H,H] ⊆ N_L, every K refining L is abelian (= no D_8 possible)
#  - if Index(L, N_L) ∈ {1, 2}, no hyperplane enumeration is needed
# Both filters cut directly into the per-layer cost dominating |H|=1024
# entries (651 layers, most "dead" or trivial-refinement).
D8KernelsFromV4Layer := function(H, v4s)
    local D, result, L, N, idxLN, hom, A, maxs, U, K, reps, x, sq_in_K;
    D := DerivedSubgroup(H);
    result := [];
    for L in v4s do
        N := RelativePhiSubgroup(H, L, 2);
        # If D ⊆ N then K ⊇ N ⊃ D forces H/K abelian.  Skip the layer.
        if IsSubset(N, D) then continue; fi;
        idxLN := Index(L, N);
        if idxLN = 1 then continue; fi;     # N = L, no refinement
        reps := Filtered(RightTransversal(H, L), x -> not (x in L));
        if idxLN = 2 then
            # Unique K = N at index 2 in L.  D ⊄ N already established.
            sq_in_K := false;
            for x in reps do
                if x^2 in N then sq_in_K := true; break; fi;
            od;
            if sq_in_K then AddSet(result, N); fi;
            continue;
        fi;
        # idxLN >= 4: enumerate index-2 subgroups of L containing N
        # via L/N's abelianization.  K's are automatically H-normal.
        hom := NaturalHomomorphismByNormalSubgroup(L, N);
        A := Range(hom);
        maxs := Filtered(MaximalSubgroupClassReps(A), U -> Index(A, U) = 2);
        for U in maxs do
            K := PreImage(hom, U);
            if IsSubset(K, D) then continue; fi;
            sq_in_K := false;
            for x in reps do
                if x^2 in K then sq_in_K := true; break; fi;
            od;
            if sq_in_K then AddSet(result, K); fi;
        od;
    od;
    return result;
end;

Small2QuotientKernels := function(H, q_groups)
    local has_C2, has_V4, has_D8, result, c2s, v4s, d8s, i, j, L,
          c2_qid, v4_qid, d8_qid;
    has_C2 := ForAny(q_groups, Q -> Size(Q) = 2);
    has_V4 := ForAny(q_groups, Q -> Size(Q) = 4 and not IsCyclic(Q));
    has_D8 := ForAny(q_groups, Q -> Size(Q) = 8 and not IsAbelian(Q));
    result := [];
    # SafeId hardcoded: C_2 = SmallGroup(2,1), V_4 = (4,2), D_8 = (8,3).
    c2_qid := [2, 0, [2, 1]];
    v4_qid := [4, 0, [4, 2]];
    d8_qid := [8, 0, [8, 3]];

    c2s := Index2SubgroupsViaAbelianization(H);
    if has_C2 then
        Append(result, List(c2s, K -> rec(K := K, qsize := 2, qid := c2_qid)));
    fi;

    v4s := [];
    if has_V4 or has_D8 then
        for i in [1..Length(c2s)] do
            for j in [i+1..Length(c2s)] do
                L := Intersection(c2s[i], c2s[j]);
                if Index(H, L) = 4 then AddSet(v4s, L); fi;
            od;
        od;
        if has_V4 then
            Append(result, List(v4s, K -> rec(K := K, qsize := 4, qid := v4_qid)));
        fi;
    fi;

    if has_D8 then
        d8s := D8KernelsFromV4Layer(H, v4s);
        Append(result, List(d8s, K -> rec(K := K, qsize := 8, qid := d8_qid)));
    fi;

    return result;
end;

# Generalizes Index2SubgroupsViaAbelianization to arbitrary prime p.
# Returns the index-p normal subgroups of M, computed via M / [M,M].
Index_p_SubgroupsViaAbelianization := function(M, p)
    local D, hom, A, maxs;
    D := DerivedSubgroup(M);
    if Size(D) = Size(M) then return []; fi;
    if (Size(M) / Size(D)) mod p <> 0 then return []; fi;
    hom := NaturalHomomorphismByNormalSubgroup(M, D);
    A := Range(hom);
    maxs := Filtered(MaximalSubgroupClassReps(A), U -> Index(A, U) = p);
    return Set(List(maxs, U -> PreImage(hom, U)));
end;

# PGroupQuotientKernels(H, Q): returns Set of K ⊆ H with H/K ≅ Q, when Q is
# a p-group.  Generalizes D8KernelsFromV4Layer: pick a central A ≤ Q with
# |A|=p, recurse on Q/A, then enumerate central C_p refinements via the
# [H,K0]·K0^p floor.  Returns `fail` for non-p-group Q.
#
# Correctness: every K with H/K ≅ Q and central A ⊴ Q lifts to K ⊆ K0 ⊆ H
# with H/K0 ≅ Q/A and K0/K ≅ A.  K0/K central in H/K forces [H,K0] ⊆ K, so
# K must contain NK0 := [H,K0]·K0^p.  Conversely, every index-p subgroup K
# of K0 containing NK0 is automatically H-normal AND gives K0/K central, so
# we filter only by SafeId(H/K) = SafeId(Q) (distinguishes D_8 from Q_8 etc).

# HasQuotientType(H, Q): cheap necessary-condition check for "H surjects onto Q".
# Returns false → no Q-quotient exists (sound, no kernels lost).
# Returns true → might have kernels; do full enumeration.
#
# For p-group Q, two structural checks:
#  (1) Abelianization compatibility — H/[H,H] must surject onto Q/[Q,Q].
#      Necessary because every quotient surjects on its abelianization.
#  (2) Derived-subgroup compatibility — for non-abelian Q (i.e. [Q,Q] = D_Q
#      non-trivial), [H,H] must have an H-equivariant elementary-abelian
#      p-quotient of rank >= rank(D_Q^ab).  The maximum such quotient is
#      D_H / Phi_H(D_H) where Phi_H(D_H) := [D_H,H]·D_H^p (relative Frattini
#      under the H-action).  If Phi_H(D_H) = D_H, no non-trivial elementary
#      abelian H-image of D_H exists, so no non-abelian Q-quotient exists.
#
# Cost: O(1 RelativePhiSubgroup call) ≈ 10-30ms.  Matches GQuotients' speed
# on the no-quotient-exists case.
HasQuotientType := function(H, Q)
    local primes, p, D_H, D_Q, A_inv_p, Q_ab_inv, Phi_DH,
          DQ_inv, phidh_rank, dq_rank;
    if Size(Q) = 1 then return true; fi;
    primes := Set(FactorsInt(Size(Q)));
    if Length(primes) <> 1 then return true; fi;  # not p-group; defer
    p := primes[1];
    D_H := DerivedSubgroup(H);
    if Size(D_H) = Size(H) then return false; fi;  # H perfect
    A_inv_p := Filtered(AbelianInvariants(H / D_H), x -> x mod p = 0);
    Q_ab_inv := AbelianInvariants(Q / DerivedSubgroup(Q));
    if Length(Q_ab_inv) > 0 then
        if Length(A_inv_p) < Length(Q_ab_inv) then return false; fi;
        if Maximum(A_inv_p) < Maximum(Q_ab_inv) then return false; fi;
    fi;
    D_Q := DerivedSubgroup(Q);
    if Size(D_Q) > 1 then
        if Size(D_H) < Size(D_Q) then return false; fi;
        Phi_DH := RelativePhiSubgroup(H, D_H, p);
        if Size(Phi_DH) = Size(D_H) then return false; fi;
        phidh_rank := LogInt(Size(D_H) / Size(Phi_DH), p);
        DQ_inv := AbelianInvariants(D_Q / DerivedSubgroup(D_Q));
        dq_rank := Length(Filtered(DQ_inv, x -> x mod p = 0));
        if phidh_rank < dq_rank then return false; fi;
    fi;
    return true;
end;

PPrimaryExponentsOfAbelianInvariants := function(inv, p)
    local exps, n, e;
    exps := [];
    for n in inv do
        e := 0;
        while n mod p = 0 do
            e := e + 1;
            n := n / p;
        od;
        if e > 0 then Add(exps, e); fi;
    od;
    Sort(exps);
    return Reversed(exps);
end;

AbelianInvariantsCanSurject := function(src_inv, dst_inv)
    local primes, n, p, src_e, dst_e, i;
    primes := Set([]);
    for n in dst_inv do
        for p in Set(FactorsInt(n)) do AddSet(primes, p); od;
    od;
    for p in primes do
        src_e := PPrimaryExponentsOfAbelianInvariants(src_inv, p);
        dst_e := PPrimaryExponentsOfAbelianInvariants(dst_inv, p);
        if Length(src_e) < Length(dst_e) then return false; fi;
        for i in [1..Length(dst_e)] do
            if src_e[i] < dst_e[i] then return false; fi;
        od;
    od;
    return true;
end;

CanSurjectOnAbelianization := function(A, Q)
    local DQ, q_ab_inv;
    DQ := DerivedSubgroup(Q);
    if Size(DQ) = Size(Q) then return true; fi;
    if A = fail then return false; fi;
    q_ab_inv := AbelianInvariants(Q / DQ);
    return AbelianInvariantsCanSurject(AbelianInvariants(A), q_ab_inv);
end;

DerivedSeriesOrderCompatibleFromDH := function(H, Q, DH)
    local Hcur, Qcur, nextH, nextQ, first;
    Hcur := H;
    Qcur := Q;
    first := true;
    while Size(Qcur) > 1 do
        if Size(Hcur) mod Size(Qcur) <> 0 then return false; fi;
        if Size(Hcur) = 1 then return false; fi;
        if first then
            nextH := DH;
            first := false;
        else
            nextH := DerivedSubgroup(Hcur);
        fi;
        nextQ := DerivedSubgroup(Qcur);
        if Size(nextQ) = Size(Qcur) then
            return Size(nextH) mod Size(Qcur) = 0;
        fi;
        Hcur := nextH;
        Qcur := nextQ;
    od;
    return true;
end;

CheapQuotientPossiblePrepared := function(H, Q, DH, A)
    if Size(H) mod Size(Q) <> 0 then return false; fi;
    if not CanSurjectOnAbelianization(A, Q) then return false; fi;
    if not DerivedSeriesOrderCompatibleFromDH(H, Q, DH) then return false; fi;
    return true;
end;

SameOrderQuotientKernelRecord := function(H, Q, q_qid)
    local h_id, iso;
    if Size(H) <> Size(Q) then return fail; fi;
    h_id := SafeId(H);
    if h_id[2] = 0 and q_qid[2] = 0 then
        if h_id = q_qid then
            return rec(K := TrivialSubgroup(H), qsize := Size(Q), qid := q_qid);
        fi;
        return false;
    fi;
    iso := IsomorphismGroups(H, Q);
    if iso <> fail then
        return rec(K := TrivialSubgroup(H), qsize := Size(Q), qid := q_qid);
    fi;
    return false;
end;

PrimeKernelQuotientRecords := function(H, Q, q_qid)
    local ksize, result, K;
    ksize := Size(H) / Size(Q);
    if not IsPrimeInt(ksize) then return fail; fi;
    result := [];
    for K in MinimalNormalSubgroups(H) do
        if Size(K) = ksize and SafeId(H / K) = q_qid then
            AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
        fi;
    od;
    return result;
end;

PGroupQuotientKernelsCached := function(H, Q, cache)
    local primes, p, A, hom_QQbar, Qbar, K0_recs, K0_rec, K0, NK0, hom, F,
          maxs, U, K, target_id, target_qsize, result, gens_A,
          p_kernels, key, idx;
    # Memoized PGroupQuotientKernels.  cache is rec(keys := [], vals := []).
    # Hits on shared Qbar (e.g., D_8/Z and Q_8/Z both reduce to V_4) avoid
    # recomputing K0_set across multiple Q-types in one _EnumerateNormalsForQGroups call.
    if Size(Q) = 1 then
        return [rec(K := H, qsize := 1, qid := [1, 0, [1, 1]])];
    fi;
    primes := Set(FactorsInt(Size(Q)));
    if Length(primes) <> 1 then return fail; fi;
    p := primes[1];
    target_id := SafeId(Q);
    target_qsize := Size(Q);
    key := target_id;
    idx := Position(cache.keys, key);
    if idx <> fail then return cache.vals[idx]; fi;
    if not HasQuotientType(H, Q) then
        Add(cache.keys, key); Add(cache.vals, []);
        return [];
    fi;
    if Size(Q) = p then
        p_kernels := Index_p_SubgroupsViaAbelianization(H, p);
        result := List(p_kernels,
                       K -> rec(K := K, qsize := target_qsize, qid := target_id));
        Add(cache.keys, key); Add(cache.vals, result);
        return result;
    fi;
    A := MinimalNormalSubgroups(Q)[1];
    if Size(A) > p then
        gens_A := GeneratorsOfGroup(A);
        A := SubgroupNC(Q, [gens_A[1]]);
    fi;
    hom_QQbar := NaturalHomomorphismByNormalSubgroup(Q, A);
    Qbar := Range(hom_QQbar);
    K0_recs := PGroupQuotientKernelsCached(H, Qbar, cache);
    if K0_recs = fail then return fail; fi;
    result := [];
    for K0_rec in K0_recs do
        K0 := K0_rec.K;
        NK0 := RelativePhiSubgroup(H, K0, p);
        if Index(K0, NK0) < p then continue; fi;
        if Index(K0, NK0) = p then
            if SafeId(H / NK0) = target_id then
                AddSet(result, rec(K := NK0, qsize := target_qsize, qid := target_id));
            fi;
            continue;
        fi;
        hom := NaturalHomomorphismByNormalSubgroup(K0, NK0);
        F := Range(hom);
        maxs := Filtered(MaximalSubgroupClassReps(F), U -> Index(F, U) = p);
        for U in maxs do
            K := PreImage(hom, U);
            if SafeId(H / K) = target_id then
                AddSet(result, rec(K := K, qsize := target_qsize, qid := target_id));
            fi;
        od;
    od;
    Add(cache.keys, key); Add(cache.vals, result);
    return result;
end;

PGroupQuotientKernels := function(H, Q)
    # Backward-compat wrapper: creates a fresh cache for a single call.  The
    # production path in _EnumerateNormalsForQGroups uses
    # PGroupQuotientKernelsCached directly with a cache shared across all
    # Q-types for a given H.
    return PGroupQuotientKernelsCached(H, Q, rec(keys := [], vals := []));
end;

NonAbelianSimpleQuotientKernelRecords := function(H, Q, q_qid)
    local result, K;
    if not (IsSimpleGroup(Q) and not IsAbelian(Q)) then return fail; fi;
    if Size(H) mod Size(Q) <> 0 then return []; fi;
    result := [];
    for K in MaximalNormalSubgroups(H) do
        if Size(H) / Size(K) = Size(Q) and SafeId(H / K) = q_qid then
            AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
        fi;
    od;
    return result;
end;

# Self-centralizing almost-simple quotient shortcut.
# If Q' is non-abelian simple and C_Q(Q') = 1, then for any epi H -> Q
# the kernel is the full preimage of C_{H/L}(H'/L), where L is the kernel
# of the induced simple quotient H' -> Q'.  This avoids enumerating every
# outer abelian quotient (e.g. all C2 quotients of S5 x 2^r).
AlmostSimpleQuotientKernelRecords := function(H, Q, q_qid)
    local DQ, CQ, DH, dq_id, simple_recs, result, L_rec, L,
          hom, Hbar, Dbar, Cbar, K;
    if IsSolvable(Q) then return fail; fi;
    DQ := DerivedSubgroup(Q);
    if not (IsSimpleGroup(DQ) and not IsAbelian(DQ)) then return fail; fi;
    CQ := Centralizer(Q, DQ);
    if Size(CQ) <> 1 then return fail; fi;
    DH := DerivedSubgroup(H);
    if Size(DH) mod Size(DQ) <> 0 then return []; fi;
    dq_id := SafeId(DQ);
    simple_recs := NonAbelianSimpleQuotientKernelRecords(DH, DQ, dq_id);
    if simple_recs = fail then return fail; fi;
    result := [];
    for L_rec in simple_recs do
        L := L_rec.K;
        if not IsNormal(H, L) then continue; fi;
        hom := NaturalHomomorphismByNormalSubgroup(H, L);
        Hbar := Range(hom);
        Dbar := Image(hom, DH);
        Cbar := Centralizer(Hbar, Dbar);
        if Size(Cbar) <> Size(Hbar) / Size(Q) then continue; fi;
        K := PreImage(hom, Cbar);
        if IsNormal(H, K) and SafeId(H / K) = q_qid then
            AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
        fi;
    od;
    return result;
end;

# Bounded direct exact path for small H or tiny kernel.  Enumerates
# NormalSubgroups(H) and filters to those whose index gives Q.  Much faster
# than recursive solvable-quotient enumeration when |H| is small enough that
# NormalSubgroups(H) is cheap, OR when the kernel is small enough that there
# are very few candidates.
SmallKernelQuotientKernelRecords := function(H, Q, q_qid)
    local ksize, result, K;
    if Size(H) mod Size(Q) <> 0 then return []; fi;
    ksize := Size(H) / Size(Q);
    # Thresholds tuned empirically (n=15 [12,3] benchmark): |H|=2304 with
    # ksize=16 hit a 66s SolvableQuotientKernelRecords ladder, so widen to
    # |H|<=4096 or ksize<=16.
    if not (Size(H) <= 4096 or ksize <= 16) then return fail; fi;
    result := [];
    for K in NormalSubgroups(H) do
        if Size(K) = ksize and SafeId(H / K) = q_qid then
            AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
        fi;
    od;
    return result;
end;

# Direct GQuotients(H, Q) wrapper for small mixed-solvable Q.  Used in place
# of recursive SolvableQuotientKernelRecords when |H| and |Q| are small
# enough that GAP's native quotient enumeration is the right tool.
DirectGQuotientsKernelRecords := function(H, Q, q_qid)
    local result, epi, K;
    result := [];
    for epi in GQuotients(H, Q) do
        K := Kernel(epi);
        AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
    od;
    return result;
end;

SolvableQuotientKernelRecords := function(H, Q, pg_cache)
    local sz, target_id, DH, hom, A, same_rec, prime_recs, p, max_subs,
          result, epi, pg_recs, max_normals, M, Qbar, K0_recs, K0_rec,
          K0, M_recs, K_rec, K, simple_recs, almost_recs, candidates,
          branch_result, branch_ok, handled;
    sz := Size(Q);
    target_id := SafeId(Q);
    if sz = 1 then
        return [rec(K := H, qsize := 1, qid := target_id)];
    fi;
    if Size(H) mod sz <> 0 then return []; fi;
    DH := DerivedSubgroup(H);
    if Size(DH) = Size(H) then
        hom := fail; A := fail;
    else
        hom := NaturalHomomorphismByNormalSubgroup(H, DH);
        A := Range(hom);
    fi;
    if not CheapQuotientPossiblePrepared(H, Q, DH, A) then return []; fi;
    same_rec := SameOrderQuotientKernelRecord(H, Q, target_id);
    if same_rec <> fail then
        if same_rec = false then return []; fi;
        return [same_rec];
    fi;
    prime_recs := PrimeKernelQuotientRecords(H, Q, target_id);
    if prime_recs <> fail then return prime_recs; fi;
    if IsPrimeInt(sz) then
        if A = fail then return []; fi;
        if Size(A) mod sz <> 0 then return []; fi;
        p := sz;
        max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = p);
        return List(max_subs,
            K -> rec(K := PreImage(hom, K), qsize := sz, qid := target_id));
    fi;
    if IsPGroup(Q) and sz <= 256 then
        pg_recs := PGroupQuotientKernelsCached(H, Q, pg_cache);
        if pg_recs <> fail then return pg_recs; fi;
    fi;
    if IsAbelian(Q) then
        if A = fail then return []; fi;
        result := [];
        for epi in GQuotients(A, Q) do
            Add(result, rec(K := PreImage(hom, Kernel(epi)),
                            qsize := sz, qid := target_id));
        od;
        return result;
    fi;
    almost_recs := AlmostSimpleQuotientKernelRecords(H, Q, target_id);
    if almost_recs <> fail then return almost_recs; fi;
    simple_recs := NonAbelianSimpleQuotientKernelRecords(H, Q, target_id);
    if simple_recs <> fail then return simple_recs; fi;
    max_normals := Filtered(MaximalNormalSubgroups(Q),
                            M -> Size(M) > 1 and Size(M) < Size(Q));
    if Length(max_normals) = 0 then return fail; fi;
    result := [];
    handled := false;
    if IsSolvable(Q) then candidates := [max_normals[1]];
    else candidates := max_normals; fi;
    for M in candidates do
        Qbar := Range(NaturalHomomorphismByNormalSubgroup(Q, M));
        K0_recs := SolvableQuotientKernelRecords(H, Qbar, pg_cache);
        if K0_recs = fail then continue; fi;
        branch_result := [];
        branch_ok := true;
        for K0_rec in K0_recs do
            K0 := K0_rec.K;
            M_recs := SolvableQuotientKernelRecords(K0, M, rec(keys := [], vals := []));
            if M_recs = fail then
                branch_ok := false;
                break;
            fi;
            for K_rec in M_recs do
                K := K_rec.K;
                if IsNormal(H, K) and SafeId(H / K) = target_id then
                    AddSet(branch_result, rec(K := K, qsize := sz, qid := target_id));
                fi;
            od;
        od;
        if branch_ok then
            handled := true;
            for K_rec in branch_result do AddSet(result, K_rec); od;
        fi;
    od;
    if handled then return result; fi;
    return fail;
end;

# ------------------------------------------------------------------
# Stage C: forced-large discovery from a trusted opposite-side H-cache.
# ------------------------------------------------------------------
#
# Given a concrete Q (typically extracted from the right cache), test
# whether some H_left actually surjects onto Q -- WITHOUT calling
# NormalSubgroups(H).  Returns true|false.
#
# Three branches:
#   1. p-group Q: use PGroupQuotientKernelsCached (bounded recursion).
#   2. abelian Q: lift via H/[H,H] = A and call GQuotients(A, Q) (cheap;
#      A is small).
#   3. non-abelian non-p-group Q: GQuotients(H, Q) directly.  Can be slow
#      for hostile H but is bounded per (H, Q) pair, unlike NormalSubgroups
#      which enumerates the entire normal lattice.
TargetedQuotientExists := function(H, Q, pg_cache)
    local sz, DH, hom, A, recs, q_qid, same_rec, prime_recs;
    sz := Size(Q);
    if sz = 1 then return true; fi;
    if Size(H) mod sz <> 0 then return false; fi;
    DH := DerivedSubgroup(H);
    if Size(DH) = Size(H) then
        hom := fail; A := fail;
    else
        hom := NaturalHomomorphismByNormalSubgroup(H, DH);
        A := Range(hom);
    fi;
    if not CheapQuotientPossiblePrepared(H, Q, DH, A) then return false; fi;
    q_qid := SafeId(Q);
    same_rec := SameOrderQuotientKernelRecord(H, Q, q_qid);
    if same_rec <> fail then return same_rec <> false; fi;
    prime_recs := PrimeKernelQuotientRecords(H, Q, q_qid);
    if prime_recs <> fail then return Length(prime_recs) > 0; fi;
    if IsPGroup(Q) then
        recs := PGroupQuotientKernelsCached(H, Q, pg_cache);
        if recs <> fail then return Length(recs) > 0; fi;
        # PGroupQuotientKernelsCached may return fail when its preconditions
        # aren't met; fall through to the abelian/general path below.
    fi;
    if IsAbelian(Q) then
        if A = fail then return false; fi;
        return Length(GQuotients(A, Q)) > 0;
    fi;
    recs := SolvableQuotientKernelRecords(H, Q, pg_cache);
    if recs <> fail then return Length(recs) > 0; fi;
    return Length(GQuotients(H, Q)) > 0;
end;

# Walk a previously-built right H-cache file and extract the set of distinct
# Q-iso-classes of size > cap as concrete group representatives.  Each entry
# carries: rec(Q, qsize, qid, source).  The qid[2]=0 case uses SmallGroup
# directly; the heuristic-fallback case (qid[2]=1) reconstructs Q := H/K
# and normalizes via IsomorphismPermGroup.
#
# Saves & restores any pre-existing global H_CACHE so this can run before
# the LEFT cache is loaded.
ForcedQRepsFromHCache := function(cache_path, cap)
    local out, seen, entry, orb, Q, key, saved_H_CACHE, right_cache, H, K;
    out := [];
    seen := Set([]);
    if cache_path = "" or not IsExistingFile(cache_path) then return out; fi;
    saved_H_CACHE := fail;
    if IsBound(H_CACHE) then
        saved_H_CACHE := H_CACHE;
        Unbind(H_CACHE);
    fi;
    Read(cache_path);
    if not IsBound(H_CACHE) or not IsList(H_CACHE) then
        if saved_H_CACHE <> fail then H_CACHE := saved_H_CACHE; fi;
        return out;
    fi;
    right_cache := H_CACHE;
    Unbind(H_CACHE);
    if saved_H_CACHE <> fail then H_CACHE := saved_H_CACHE; fi;
    for entry in right_cache do
        for orb in entry.orbits do
            if orb.qsize <= cap then continue; fi;
            key := String(orb.qid);
            if key in seen then continue; fi;
            AddSet(seen, key);
            if orb.qid[2] = 0 then
                Q := SmallGroup(orb.qid[3]);
            else
                # Fallback: reconstruct via H/K.  H from this right-cache entry.
                H := Group(entry.H_gens);
                K := Subgroup(H, orb.K_H_gens);
                Q := Image(IsomorphismPermGroup(
                    Range(NaturalHomomorphismByNormalSubgroup(H, K))));
            fi;
            Add(out, rec(Q := Q, qsize := orb.qsize, qid := orb.qid,
                        source := "right-cache"));
        od;
    od;
    return out;
end;

# Test each forced-large Q against LEFT subgroups via TargetedQuotientExists.
# Per-Q early exit on first H that succeeds (we only need to know membership
# in LEFT_Q_GROUPS, not enumerate all kernels here).
ProcessForcedLargeQTypes := function(left_groups, forced_qrecs)
    local result, qr, H, pg_cache, t_q;
    result := [];
    for qr in forced_qrecs do
        Print("    [forced-large] testing Q=[", qr.qsize, ",",
              qr.qid, "]\n");
        t_q := Runtime();
        for H in left_groups do
            if Size(H) mod qr.qsize <> 0 then continue; fi;
            pg_cache := rec(keys := [], vals := []);
            if TargetedQuotientExists(H, qr.Q, pg_cache) then
                Add(result, qr.Q);
                Print("    [forced-large] FOUND Q=[", qr.qsize, ",",
                      qr.qid, "] in |H|=", Size(H), " (",
                      Runtime() - t_q, "ms)\n");
                break;
            fi;
        od;
    od;
    return result;
end;

# Stage D: for each order n > cap appearing as a divisor of some |H_left|,
# enumerate all SmallGroup(n, *) candidates and test via
# TargetedQuotientExists.  FATAL if any required order has unmanageably
# many SmallGroups (in which case the catalog cap must be raised or a
# chunking strategy implemented).
PromoteUnknownLargeOrders := function(left_groups, covered_qids, cap, max_per_order)
    local left_orders, n, i, qrecs_to_test, covered_orders, candidate_Q,
          qid, H, d;
    qrecs_to_test := [];
    left_orders := Set([]);
    for H in left_groups do
        for d in DivisorsInt(Size(H)) do
            if d > cap then AddSet(left_orders, d); fi;
        od;
    od;
    covered_orders := Set(List(covered_qids, q -> q[1]));
    for n in left_orders do
        if not IdGroupsAvailable(n) then
            # SmallGroups database does not include this order (e.g., 2160).
            # Skip: the forced-large lane already covers any Q of this order
            # that actually appears on the right side, which is the only case
            # that contributes orbits under Goursat.
            Print("    [promote] WARNING: order ", n,
                  " has no SmallGroups database; skipping ",
                  "(forced-large lane covers right-side Q's).\n");
            continue;
        fi;
        if NumberSmallGroups(n) > max_per_order then
            Print("    [promote] WARNING: order ", n, " has ",
                  NumberSmallGroups(n),
                  " SmallGroups (> max_per_order=", max_per_order,
                  "); skipping (forced-large lane covers right-side Q's).\n");
            continue;
        fi;
        for i in [1..NumberSmallGroups(n)] do
            candidate_Q := SmallGroup(n, i);
            qid := SafeId(candidate_Q);
            if qid in covered_qids then continue; fi;
            Add(qrecs_to_test, rec(Q := candidate_Q, qsize := n, qid := qid,
                                    source := "promoted"));
        od;
    od;
    if Length(qrecs_to_test) = 0 then return []; fi;
    Print("    [promote] testing ", Length(qrecs_to_test),
          " unknown-large candidates across ", Length(left_orders),
          " orders > cap=", cap, "\n");
    return ProcessForcedLargeQTypes(left_groups, qrecs_to_test);
end;

_EnumerateNormalsForQGroups := function(H, q_groups)
    local q_size_H, DH, abel_hom, A, result, Q, sz, p, max_subs, epi,
          qids_set, all_normals, K, qid_K, t_q,
          h_is_2group, small_qs, other_qs, pg_kernels, q_qid, q_size,
          c2_qid, pg_cache, same_rec, prime_recs, solv_kernels,
          small_recs, direct_recs;
    # Returns a list of records: rec(K := <kernel>, qsize := |H/K|, qid := SafeId(H/K)).
    # qid is propagated from each enumeration branch so that the downstream
    # orbit construction (_ComputeOrbitRecsFromKs) can skip the per-orbit
    # NaturalHomomorphismByNormalSubgroup + SafeId reconstruction.
    #
    # As of Stage B (2026-05-08): never calls NormalSubgroups(H).  The legacy
    # `q_groups = fail` (full enumeration) and `use_direct` (max(|Q|)>200)
    # branches are removed -- callers must always pass a concrete Q list, and
    # large Q's are routed per-Q via the existing PGroupQuotientKernelsCached
    # / abelianization / GQuotients paths below.
    if q_groups = fail then
        Error("EnumerateNormalsForQGroups requires non-fail q_groups; ",
              "the legacy NormalSubgroups discovery path has been removed. ",
              "|H|=", Size(H));
    fi;
    if Length(q_groups) = 0 then return []; fi;
    h_is_2group := ForAll(FactorsInt(Size(H)), p -> p = 2);
    if h_is_2group then
        small_qs := Filtered(q_groups, Q ->
            Size(Q) = 2
            or (Size(Q) = 4 and not IsCyclic(Q))
            or (Size(Q) = 8 and not IsAbelian(Q) and IdGroup(Q) = [8, 3]));
    else
        small_qs := Filtered(q_groups, Q -> Size(Q) = 2);
    fi;
    other_qs := Filtered(q_groups, Q -> not (Q in small_qs));
    result := [];
    if Length(small_qs) > 0 then
        Print("    [enum/L0/small] BEGIN |H|=", Size(H),
              " n_small=", Length(small_qs), "\n");
        t_q := Runtime();
        if h_is_2group then
            Append(result, Small2QuotientKernels(H, small_qs));
        else
            c2_qid := [2, 0, [2, 1]];
            Append(result, List(Index2SubgroupsViaAbelianization(H),
                                K -> rec(K := K, qsize := 2, qid := c2_qid)));
        fi;
        Print("    [enum/L0/small] END   |H|=", Size(H),
              " -> ", Length(result), " kernels in ", Runtime() - t_q, "ms\n");
    fi;
    if Length(other_qs) = 0 then return result; fi;
    q_size_H := Size(H);
    DH := DerivedSubgroup(H);
    if Size(DH) = q_size_H then
        abel_hom := fail; A := fail;
    else
        abel_hom := NaturalHomomorphismByNormalSubgroup(H, DH);
        A := Range(abel_hom);
    fi;
    pg_cache := rec(keys := [], vals := []);   # shared across all Q in other_qs
    for Q in other_qs do
        sz := Size(Q);
        if q_size_H mod sz <> 0 then continue; fi;
        q_qid := SafeId(Q);
        q_size := sz;
        t_q := Runtime();
        if not CheapQuotientPossiblePrepared(H, Q, DH, A) then
            if Runtime() - t_q >= 100 then
                Print("    [enum/cheap_skip] |H|=", Size(H), " Q=", q_qid,
                      " in ", Runtime() - t_q, "ms\n");
            fi;
            continue;
        fi;
        same_rec := SameOrderQuotientKernelRecord(H, Q, q_qid);
        if same_rec <> fail then
            if same_rec <> false then Add(result, same_rec); fi;
            if Runtime() - t_q >= 100 then
                Print("    [enum/same_order] |H|=", Size(H), " Q=", q_qid,
                      " in ", Runtime() - t_q, "ms\n");
            fi;
            continue;
        fi;
        prime_recs := PrimeKernelQuotientRecords(H, Q, q_qid);
        if prime_recs <> fail then
            Append(result, prime_recs);
            if Runtime() - t_q >= 100 then
                Print("    [enum/prime_kernel] |H|=", Size(H), " Q=", q_qid,
                      " -> ", Length(prime_recs), " kernels in ",
                      Runtime() - t_q, "ms\n");
            fi;
            continue;
        fi;
        # Small-H or tiny-kernel direct path: NormalSubgroups(H) bounded.
        small_recs := SmallKernelQuotientKernelRecords(H, Q, q_qid);
        if small_recs <> fail then
            Append(result, small_recs);
            if Runtime() - t_q >= 100 then
                Print("    [enum/small_kernel] |H|=", Size(H), " Q=", q_qid,
                      " -> ", Length(small_recs), " kernels in ",
                      Runtime() - t_q, "ms\n");
            fi;
            continue;
        fi;
        if IsPrimeInt(sz) then
            if abel_hom = fail then continue; fi;
            if Size(A) mod sz <> 0 then continue; fi;
            p := sz;
            max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = p);
            Append(result, List(max_subs,
                K -> rec(K := PreImage(abel_hom, K), qsize := q_size, qid := q_qid)));
            if Runtime() - t_q >= 100 then
                Print("    [enum/prime_abel] |H|=", Size(H), " Q=", q_qid,
                      " -> ", Length(max_subs), " kernels in ",
                      Runtime() - t_q, "ms\n");
            fi;
        elif IsPGroup(Q) and sz <= 256 then
            # Level 1: p-group Q (abelian or non-abelian) via memoized
            # PGroupQuotientKernelsCached.  HasQuotientType inside that
            # function gives a cheap top-level feasibility check (O(1
            # RelativePhi call) ≈ 10-30ms) that matches GQuotients' speed
            # on the no-quotient case, so non-abelian Q is now safe to
            # route here even when many H entries don't admit such a
            # quotient.  Memoization (#3) shares K0_set across siblings.
            Print("    [enum/L1/pgroup] BEGIN |H|=", Size(H),
                  " Q=[", sz, ",", IdGroup(Q)[2], "]\n");
            t_q := Runtime();
            pg_kernels := PGroupQuotientKernelsCached(H, Q, pg_cache);
            if pg_kernels <> fail then
                Append(result, pg_kernels);
                Print("    [enum/L1/pgroup] END   |H|=", Size(H),
                      " Q=[", sz, ",", IdGroup(Q)[2], "] -> ",
                      Length(pg_kernels), " kernels in ",
                      Runtime() - t_q, "ms\n");
            else
                Print("    [enum/L1/pgroup] FALLBACK |H|=", Size(H),
                      " Q=[", sz, ",", IdGroup(Q)[2], "]\n");
                if abel_hom <> fail then
                    for epi in GQuotients(A, Q) do
                        Add(result, rec(K := PreImage(abel_hom, Kernel(epi)),
                                        qsize := q_size, qid := q_qid));
                    od;
                fi;
            fi;
        elif IsAbelian(Q) then
            if abel_hom = fail then continue; fi;
            for epi in GQuotients(A, Q) do
                Add(result, rec(K := PreImage(abel_hom, Kernel(epi)),
                                qsize := q_size, qid := q_qid));
            od;
            if Runtime() - t_q >= 100 then
                Print("    [enum/abelian] |H|=", Size(H), " Q=", q_qid,
                      " in ", Runtime() - t_q, "ms\n");
            fi;
        else
            # Small mixed-solvable Q: GQuotients(H, Q) is the right tool.
            # Avoids the recursive SolvableQuotientKernelRecords ladder that
            # can hit pathological cases (e.g. Q=SmallGroup(48,50) on
            # H=TG[12,90] taking 130s).
            if IsSolvable(Q) and not IsPGroup(Q) and not IsAbelian(Q)
               and Size(H) <= 4096 and Size(Q) <= 1024 then
                direct_recs := DirectGQuotientsKernelRecords(H, Q, q_qid);
                Append(result, direct_recs);
                if Runtime() - t_q >= 100 then
                    Print("    [enum/direct_gq] |H|=", Size(H), " Q=", q_qid,
                          " -> ", Length(direct_recs), " kernels in ",
                          Runtime() - t_q, "ms\n");
                fi;
                continue;
            fi;
            solv_kernels := SolvableQuotientKernelRecords(H, Q, pg_cache);
            if solv_kernels <> fail then
                Append(result, solv_kernels);
                if Runtime() - t_q >= 100 then
                    Print("    [enum/solvable] |H|=", Size(H), " Q=", q_qid,
                          " -> ", Length(solv_kernels), " kernels in ",
                          Runtime() - t_q, "ms\n");
                fi;
                continue;
            fi;
            Print("    [enum/fallback/GQuot] BEGIN |H|=", Size(H),
                  " Q=[", sz, ",", IdGroup(Q)[2], "]\n");
            Append(result, List(Set(List(GQuotients(H, Q), Kernel)),
                                K -> rec(K := K, qsize := q_size, qid := q_qid)));
            Print("    [enum/fallback/GQuot] END   |H|=", Size(H),
                  " Q=[", sz, ",", IdGroup(Q)[2], "] in ",
                  Runtime() - t_q, "ms\n");
        fi;
    od;
    return result;
end;

# Cut 3 dispatcher: splits q_groups into linear-supported and legacy.
# For supported qids (C_2, V_4, D_8), calls Stage A/B prototypes directly
# (produces orbit recs in the right format with K_H_gens + Stab_NH_KH_gens).
# Returns the LINEAR orbit-recs as a list; caller is responsible for running
# the legacy path on the remaining q_groups.
_LinearOrbitsForSupportedQids := function(H, N_H, q_groups)
    local supported_qids, orbits, legacy_qs, Q, qid, sz, recs;
    # Fail-safe: if USE_LINEAR_ORBITS isn't defined in this driver template
    # (only GAP_DRIVER has it currently), default to legacy.
    if not IsBound(USE_LINEAR_ORBITS) or USE_LINEAR_ORBITS <> 1 then
        return rec(linear := [], legacy := q_groups);
    fi;
    supported_qids := [[2,0,[2,1]], [4,0,[4,2]], [8,0,[8,3]]];
    orbits := [];
    legacy_qs := [];
    for Q in q_groups do
        qid := SafeId(Q);
        sz := Size(Q);
        if qid = [2,0,[2,1]] then
            Append(orbits, LinearOrbitRecsCpa(H, N_H, 2, 1));
        elif qid = [4,0,[4,2]] then
            Append(orbits, LinearOrbitRecsCpa(H, N_H, 2, 2));
        elif qid = [8,0,[8,3]] then
            Append(orbits, LinearOrbitRecsD8(H, N_H));
        else
            Add(legacy_qs, Q);
        fi;
    od;
    return rec(linear := orbits, legacy := legacy_qs);
end;


_ComputeOrbitRecsFromKs := function(H, N_H, k_recs)
    local kbyqid, qid_str, key, bucket, normals, K_orbit, K_H, Stab_NH_KH,
          orbits, kr, q_size_v, q_qid_v;
    # k_recs is a list of rec(K, qsize, qid).  Bucket by qid (kernels with
    # different qids cannot be N_H-conjugate), orbit per bucket, and skip
    # the per-orbit NaturalHomomorphismByNormalSubgroup + SafeId rebuild —
    # the qid is propagated from the enumeration step.
    orbits := [];
    kbyqid := rec();
    for kr in k_recs do
        qid_str := String(kr.qid);
        if not IsBound(kbyqid.(qid_str)) then
            kbyqid.(qid_str) := rec(qsize := kr.qsize, qid := kr.qid, recs := []);
        fi;
        Add(kbyqid.(qid_str).recs, kr);
    od;
    for key in RecNames(kbyqid) do
        bucket := kbyqid.(key);
        normals := List(bucket.recs, kr -> kr.K);
        q_size_v := bucket.qsize;
        q_qid_v := bucket.qid;
        for K_orbit in Orbits(N_H, normals, ConjAction) do
            K_H := K_orbit[1];
            Stab_NH_KH := Stabilizer(N_H, K_H, ConjAction);
            Add(orbits, rec(
                K_H_gens := GeneratorsOfGroup(K_H),
                Stab_NH_KH_gens := GeneratorsOfGroup(Stab_NH_KH),
                qsize := q_size_v,
                qid := q_qid_v
            ));
        od;
    od;
    return orbits;
end;

ComputeHCacheEntry := function(H, S_M, q_groups)
    local N_H, k_recs, t0, t_norm, t_enum, t_orbit, result_orbits;
    t0 := Runtime();
    N_H := Normalizer(S_M, H);
    t_norm := Runtime() - t0;
    t0 := Runtime();
    k_recs := _EnumerateNormalsForQGroups(H, q_groups);
    t_enum := Runtime() - t0;
    t0 := Runtime();
    result_orbits := _ComputeOrbitRecsFromKs(H, N_H, k_recs);
    t_orbit := Runtime() - t0;
    if t_norm + t_enum + t_orbit >= 1000 then
        Print("    [ComputeHCacheEntry] |H|=", Size(H),
              " norm=", t_norm, "ms enum=", t_enum,
              "ms orbit=", t_orbit, "ms (n_kernels=",
              Length(k_recs), ")\n");
    fi;
    return rec(
        H_gens := GeneratorsOfGroup(H),
        N_H_gens := GeneratorsOfGroup(N_H),
        computed_q_ids := QIdsOfGroups(q_groups),
        orbits := result_orbits
    );
end;

ComputeHDataDirect := function(H, S_M, q_groups)
    local N_H, k_recs, t0, t_norm, t_enum, t_orbit, res, hom_triv,
          kbyqid, kr, qid_str, key, bucket, normals, K_orbit, K_H,
          Stab, i;
    t0 := Runtime();
    N_H := Normalizer(S_M, H);
    t_norm := Runtime() - t0;
    t0 := Runtime();
    k_recs := _EnumerateNormalsForQGroups(H, q_groups);
    t_enum := Runtime() - t0;

    res := rec(H := H, N := N_H,
        H_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_H := fail, shifted_H_gens_noid := fail,
        orbits := []);
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N_H, AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
        K_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_K_gens_noid := fail, c2_rep := fail, shifted_c2_rep := fail,
        H_ref := H));

    t0 := Runtime();
    kbyqid := rec();
    for kr in k_recs do
        qid_str := String(kr.qid);
        if not IsBound(kbyqid.(qid_str)) then
            kbyqid.(qid_str) := rec(qsize := kr.qsize, qid := kr.qid, recs := []);
        fi;
        Add(kbyqid.(qid_str).recs, kr);
    od;
    for key in RecNames(kbyqid) do
        bucket := kbyqid.(key);
        normals := List(bucket.recs, kr -> kr.K);
        for K_orbit in Orbits(N_H, normals, ConjAction) do
            K_H := K_orbit[1];
            Stab := Stabilizer(N_H, K_H, ConjAction);
            Add(res.orbits, rec(K := K_H, hom := fail, Q := fail,
                qsize := bucket.qsize, qid := bucket.qid,
                Stab := Stab, AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
                K_gens_noid := Filtered(GeneratorsOfGroup(K_H), g -> g <> ()),
                shifted_K_gens_noid := fail, c2_rep := fail, shifted_c2_rep := fail,
                H_ref := H));
        od;
    od;
    res.byqid := rec();
    for i in [1..Length(res.orbits)] do
        key := String(res.orbits[i].qid);
        if not IsBound(res.byqid.(key)) then res.byqid.(key) := []; fi;
        Add(res.byqid.(key), i);
    od;
    t_orbit := Runtime() - t0;
    if t_norm + t_enum + t_orbit >= 1000 then
        Print("    [ComputeHDataDirect] |H|=", Size(H),
              " norm=", t_norm, "ms enum=", t_enum,
              "ms orbit=", t_orbit, "ms (n_kernels=",
              Length(k_recs), ")\n");
    fi;
    return res;
end;

ExtendHCacheEntry := function(entry, S_M, additional_q_groups)
    local H, N_H, current, missing_groups, k_recs, new_orbits, all_normals,
          K, qid_K, _linear_split, _linear_t0, _linear_t1;
    if entry.computed_q_ids = fail then return entry; fi;
    H := SafeGroup(entry.H_gens, S_M);
    N_H := SafeGroup(entry.N_H_gens, S_M);
    current := entry.computed_q_ids;
    if additional_q_groups = fail then
        # Extend to FULL coverage: enumerate ALL normals; add only the K's
        # whose quotient iso-class is not already in current.
        all_normals := Filtered(NormalSubgroups(H), K -> K <> H);
        k_recs := [];
        for K in all_normals do
            qid_K := SafeId(H/K);
            if not (qid_K in current) then
                Add(k_recs, rec(K := K, qsize := Size(H)/Size(K), qid := qid_K));
            fi;
        od;
        new_orbits := _ComputeOrbitRecsFromKs(H, N_H, k_recs);
        Append(entry.orbits, new_orbits);
        entry.computed_q_ids := fail;
        return entry;
    fi;
    missing_groups := QGroupsMissing(current, additional_q_groups);
    if Length(missing_groups) = 0 then return entry; fi;
    # Cut 3: route supported qids ({C_2, V_4, D_8}) through Stage A/B (linear
    # orbit math; orbit recs returned directly).  Remaining qids go through
    # the legacy enumerate-then-orbit path.  When USE_LINEAR_ORBITS=0, all
    # qids go to legacy (no behavior change).
    _linear_t0 := Runtime();
    _linear_split := _LinearOrbitsForSupportedQids(H, N_H, missing_groups);
    _linear_t1 := Runtime();
    if Length(_linear_split.linear) > 0 then
        Append(entry.orbits, _linear_split.linear);
    fi;
    if Length(_linear_split.legacy) > 0 then
        k_recs := _EnumerateNormalsForQGroups(H, _linear_split.legacy);
        new_orbits := _ComputeOrbitRecsFromKs(H, N_H, k_recs);
        Append(entry.orbits, new_orbits);
    fi;
    UniteSet(entry.computed_q_ids, QIdsOfGroups(missing_groups));
    if IsBound(USE_LINEAR_ORBITS) and USE_LINEAR_ORBITS = 1
       and (_linear_t1 - _linear_t0) >= 1000 then
        Print("    [cut3/linear] |H|=", Size(H),
              " n_orbits=", Length(_linear_split.linear),
              " time=", _linear_t1 - _linear_t0, "ms\n");
    fi;
    return entry;
end;

# File-level coverage tag: union of computed_q_ids across all H_CACHE
# entries.  An m_r=2 build only covers the q-types of TG(2,*) plus the
# subgroups thereof; an extension to m_r=3,4,... unions in extra qids.
# Saving compares this tag against the on-disk one and only overwrites if
# our in-memory cache covers at least as much as the file does.
ComputeCoverageTag := function(h_cache)
    local tag, e;
    tag := Set([]);
    for e in h_cache do
        # Treat unbound and the `fail` sentinel (set by ExtendHCacheEntry
        # when full coverage was requested) as full coverage.  UniteSet on
        # `fail` would crash GAP, killing the worker silently.
        if not IsBound(e.computed_q_ids) or e.computed_q_ids = fail then
            return fail;
        fi;
        UniteSet(tag, e.computed_q_ids);
    od;
    return tag;
end;

# Read just the first line of a cache file to extract its coverage tag.
# Format: "# coverage_qids: <set>;\n" (or "# coverage_qids: fail;\n" for
# full coverage).  Returns:
#   "missing" - file does not exist
#   "unknown" - file has no header (legacy file written before this opt)
#   fail      - file marked as full coverage
#   <list>    - parsed coverage tag (a Set of qids)
ReadCoverageTagFromFile := function(path)
    local f, line, prefix, payload, n;
    if not IsExistingFile(path) then return "missing"; fi;
    f := InputTextFile(path);
    if f = fail then return "missing"; fi;
    line := ReadLine(f);
    CloseStream(f);
    if line = fail then return "unknown"; fi;
    n := Length(line);
    while n > 0 and line[n] in [' ', '\n', '\r', '\t'] do n := n - 1; od;
    line := line{[1..n]};
    prefix := "# coverage_qids: ";
    if Length(line) < Length(prefix) then return "unknown"; fi;
    if line{[1..Length(prefix)]} <> prefix then return "unknown"; fi;
    payload := line{[Length(prefix)+1..Length(line)]};
    if Length(payload) >= 1 and payload[Length(payload)] = ';' then
        payload := payload{[1..Length(payload)-1]};
    fi;
    if payload = "fail" then return fail; fi;
    return EvalString(payload);
end;

SaveHCacheList := function(path, h_cache)
    local tmp, mem_tag, disk_tag, header, header_stream;
    # Coverage-tagged save: overwrite iff in-memory cache strictly extends
    # (or equals) the on-disk coverage.  Header line is parsed without
    # touching the body, so the check is cheap on multi-MB files.  Files
    # without a header (legacy) always trigger overwrite, which gives them
    # a header on first save.  IsValidCacheFile guards against skipping
    # when the on-disk file is corrupt: we'd otherwise refuse to overwrite
    # a truncated cache and leave readers crashing forever.
    mem_tag := ComputeCoverageTag(h_cache);
    disk_tag := ReadCoverageTagFromFile(path);
    if disk_tag = fail and IsValidCacheFile(path) then
        return;  # on-disk has full coverage and is intact
    fi;
    if disk_tag <> "missing" and disk_tag <> "unknown" and disk_tag <> fail
       and mem_tag <> fail and IsSubset(disk_tag, mem_tag)
       and not IsSubset(mem_tag, disk_tag)
       and IsValidCacheFile(path) then
        # disk_tag STRICTLY dominates mem_tag (disk has q-types we don't).
        # Equal tags are NOT a skip case: during EXTEND, individual entries
        # gain q-ids even when the cross-entry UNION is unchanged (because
        # some other entry already had that q-id).  Skipping the save in
        # that case loses the per-entry progress, so the next epoch loads
        # the same stale cache and re-runs the same slow entry forever.
        return;
    fi;
    if mem_tag = fail then
        header := "# coverage_qids: fail;\n";
    else
        header := Concatenation("# coverage_qids: ", String(mem_tag), ";\n");
    fi;
    # Atomic write: PrintTo to a unique .tmp file, then `mv` to final path.
    # Unique tmp prevents two GAP workers from clobbering each other's
    # PrintTo when racing on the same cache file.
    tmp := Concatenation(path, ".tmp.", String(Runtime()), ".",
                          String(Random([1..1000000])));
    # Header via WriteAll (verbatim, no auto-wrap).  PrintTo would wrap the
    # `# coverage_qids: ...` comment at SizeScreen() chars with backslash-
    # newline, but GAP comments don't honor `\` continuation -- the wrapped
    # comment turns into invalid code on the next line and crashes Read on
    # the next worker spawn.  Body uses default PrintTo wrapping, which is
    # fine since wrapping happens inside expressions (parses correctly).
    header_stream := OutputTextFile(tmp, false);
    WriteAll(header_stream, header);
    CloseStream(header_stream);
    AppendTo(tmp, "H_CACHE := ", h_cache, ";\n");
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
META_CATALOG_PATH := "__META_CATALOG__";
H_TO_QS_MASTER_PATH := "__H_TO_QS_MASTER__";
H_TO_QS_FRAGMENT_PATH := "__H_TO_QS_FRAGMENT__";
H_TO_QS_FRAGMENTS_DIR := "__H_TO_QS_FRAGMENTS_DIR__";

# Load JOBS array first so we can compute the LEFT q-size filter from the
# union of m_right's across all jobs in this batch.
JOBS := __JOBS_ARRAY__;

S_ML := SymmetricGroup(ML);
W_ML := BlockWreathFromPartition(LEFT_PARTITION);
batch_t0 := Runtime();

# ---- Checkpoint-restart support (opts 8, 9) ----
# Long-running batches (heavy LEFTs) accumulate GAP heap pressure that slows
# garbage collection 10-20x per pair after a few hours.  To avoid this, we
# checkpoint after each LEFT-class iteration once `Runtime() - WORKER_START`
# crosses CHECKPOINT_INTERVAL_MS, save state to STATE_FILE, then QuitGap.
# Two phases checkpoint independently, sharing the same state.g file:
#   - opt 8: pair-loop phase (RESUME_STATE := rec(...))
#   - opt 9: cache-build phase (RESUME_BUILD := rec(next_hi := K)), with
#     the partial H_CACHE saved atomically to CACHE_LEFT_PATH.
# Setup must run BEFORE the cache-load logic, since cache-load reads
# RESUME_BUILD_NEXT_HI to decide whether to treat the on-disk cache as
# partial-resume vs final-skip-load.
STATE_FILE := "__STATE_FILE__";
CHECKPOINT_INTERVAL_MS := __CHECKPOINT_INTERVAL_MS__;
STATE_SAVE_INTERVAL_MS := __STATE_SAVE_INTERVAL_MS__;
LAST_STATE_SAVE_MS := 0;
BENCH_PHASES   := __BENCH_PHASES__;
BENCH_PHASES_OUT := "__BENCH_PHASES_OUT__";
BENCH_T := rec(t_iso := 0, t_ensure := 0, t_a1a2 := 0, t_dc := 0, t_swap := 0,
               t_emit_qsize1 := 0, t_emit_c2_fast := 0, t_emit_c2_safe := 0,
               t_emit_general := 0, t_shifted_hom := 0,
               t_grp_construct := 0, t_emit_write := 0,
               t_c2safe_shifted_hom := 0, t_c2safe_gbfp := 0,
               t_c2safe_emit_write := 0);
BENCH_N := rec(n_pairs := 0, n_saturated := 0, n_dc_call := 0,
               n_dc_orbits_total := 0, n_emit := 0, n_c2_safe_invocations := 0,
               n_dc_cache_hits := 0, n_dc_cache_misses := 0);
# Opt #5 canonical-Q registry.  qid_str -> rec(Q := canonical_Q,
# AutQ := Aut(Qcan)).  Populated lazily by EnsureAutQ.
QCAN_TABLE := rec();
WORKER_START := Runtime();

RESUME_JOB_IDX := 1;
RESUME_PAIR_I := 1;
RESUME_PAIR_J := 1;          # 1 = no mid-i resume (start of a fresh i)
RESUME_FP_LINES := [];
RESUME_TOTAL_ORB := 0;
RESUME_TOTAL_FIX := 0;
RESUME_BUILD_NEXT_HI := 0;   # 0 = no build resume

if STATE_FILE <> "" and IsExistingFile(STATE_FILE) then
    Read(STATE_FILE);
    if IsBound(RESUME_STATE) then
        RESUME_JOB_IDX := RESUME_STATE.job_idx;
        RESUME_PAIR_I := RESUME_STATE.pair_i;
        if IsBound(RESUME_STATE.pair_j) then
            RESUME_PAIR_J := RESUME_STATE.pair_j;
        fi;
        RESUME_FP_LINES := RESUME_STATE.fp_lines;
        RESUME_TOTAL_ORB := RESUME_STATE.total_orb;
        RESUME_TOTAL_FIX := RESUME_STATE.total_fix;
        Print("CHECKPOINT_RESUME job_idx=", RESUME_JOB_IDX,
              " pair_i=", RESUME_PAIR_I,
              " pair_j=", RESUME_PAIR_J,
              " fp_lines=", Length(RESUME_FP_LINES),
              " orb=", RESUME_TOTAL_ORB, "\n");
    fi;
    if IsBound(RESUME_BUILD) then
        RESUME_BUILD_NEXT_HI := RESUME_BUILD.next_hi;
        Print("CHECKPOINT_RESUME_BUILD next_hi=", RESUME_BUILD_NEXT_HI, "\n");
    fi;
fi;

# Read LEFT subgroup list eagerly; it is always needed to build/load H_CACHE.
Print("[t+", Runtime() - batch_t0, "ms] reading subs_left.g: ",
      SUBS_LEFT_PATH, "\n");
Read(SUBS_LEFT_PATH);
SUBGROUPS_LEFT_RAW := SUBGROUPS;
Print("[t+", Runtime() - batch_t0, "ms] subs_left.g loaded: ",
      Length(SUBGROUPS_LEFT_RAW), " entries\n");

RIGHT_Q_GROUPS := [];
seen_qids := Set([]);
# Per-job specific Q-discovery: for TG-source jobs walk just TG(d, t); for
# subs_right-source jobs walk the cached SUBS_RIGHT path.  Avoids the
# RequiredQGroups(MR) union which iterates all NrTransitiveGroups(MR) TG's
# (~1 hour for MR=12) and is wider than needed.
seen_tg_keys := Set([]);
seen_subs_paths := Set([]);
for job_idx in [1..Length(JOBS)] do
    if JOBS[job_idx].right_tg_d > 0 then
        key := Concatenation(String(JOBS[job_idx].right_tg_d), ",",
                             String(JOBS[job_idx].right_tg_t));
        if not (key in seen_tg_keys) then
            AddSet(seen_tg_keys, key);
            T_for_qg := TransitiveGroup(JOBS[job_idx].right_tg_d, JOBS[job_idx].right_tg_t);
            for K in NormalSubgroups(T_for_qg) do
                if Size(K) = Size(T_for_qg) then continue; fi;
                Q := T_for_qg/K;
                qid := SafeId(Q);
                if not (qid in seen_qids) then
                    AddSet(seen_qids, qid);
                    if IdGroupsAvailable(Size(Q)) then
                        Add(RIGHT_Q_GROUPS, SmallGroup(Size(Q), IdGroup(Q)[2]));
                    else
                        Add(RIGHT_Q_GROUPS, Image(IsomorphismPermGroup(Q)));
                    fi;
                fi;
            od;
        fi;
    fi;
    if JOBS[job_idx].subs_right <> "" and
       not (JOBS[job_idx].subs_right in seen_subs_paths) then
        AddSet(seen_subs_paths, JOBS[job_idx].subs_right);
        for Q in LoadOrComputeRightQGroupsFromSubs(
                JOBS[job_idx].subs_right, JOBS[job_idx].cache_right) do
            qid := SafeId(Q);
            if not (qid in seen_qids) then
                AddSet(seen_qids, qid);
                Add(RIGHT_Q_GROUPS, Q);
            fi;
        od;
    fi;
od;

if Length(RIGHT_Q_GROUPS) = 0 then
    LEFT_Q_GROUPS := ComputeOrLoadLeftQGroups(
        SUBGROUPS_LEFT_RAW,
        Concatenation(CACHE_LEFT_PATH, ".qgroups.g"),
        META_CATALOG_PATH,
        Filtered(DuplicateFreeList(List(JOBS, j -> j.cache_right)),
                 p -> p <> ""),
        H_TO_QS_MASTER_PATH,
        H_TO_QS_FRAGMENT_PATH,
        H_TO_QS_FRAGMENTS_DIR);
    Print("[t+", Runtime() - batch_t0, "ms] LEFT-derived Q-groups: ",
          Length(LEFT_Q_GROUPS), " types, max |Q|=",
          Maximum(Concatenation([0], List(LEFT_Q_GROUPS, Size))), "\n");
else
    LEFT_Q_GROUPS := RIGHT_Q_GROUPS;
    Print("[t+", Runtime() - batch_t0, "ms] RIGHT-bounded Q-groups: ",
          Length(LEFT_Q_GROUPS), " types, max |Q|=",
          Maximum(Concatenation([0], List(LEFT_Q_GROUPS, Size))), "\n");
fi;

H_CACHE := fail;
# Cache-load policy: if RESUME_BUILD is in flight, the on-disk file is a
# *partial* cache that we want to extend, NOT a complete cache to skip-load.
if CACHE_LEFT_PATH <> "" and IsValidCacheFile(CACHE_LEFT_PATH) then
    if RESUME_BUILD_NEXT_HI > 0 then
        Print("[t+", Runtime() - batch_t0,
              "ms] reading PARTIAL H_CACHE from disk (resuming build at ",
              RESUME_BUILD_NEXT_HI, "): ", CACHE_LEFT_PATH, "\n");
        Read(CACHE_LEFT_PATH);
        Print("[t+", Runtime() - batch_t0, "ms] partial H_CACHE: ",
              Length(H_CACHE), " entries already built\n");
    else
        Print("[t+", Runtime() - batch_t0, "ms] reading H_CACHE from disk: ",
              CACHE_LEFT_PATH, "\n");
        Read(CACHE_LEFT_PATH);
        Print("[t+", Runtime() - batch_t0, "ms] H_CACHE read complete: ",
              Length(H_CACHE), " entries\n");
    fi;
fi;
if H_CACHE <> fail and RESUME_BUILD_NEXT_HI = 0 then
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
        last_hb := Runtime();
        last_hb_count := 0;
        for hi in [1..Length(H_CACHE)] do
            missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
            if hi = 1 or hi - last_hb_count >= 500
               or Runtime() - last_hb >= 60000 then
                if missing = fail then
                    Print("  [t+", Runtime() - batch_t0,
                          "ms] H_CACHE EXTEND ", hi, "/", Length(H_CACHE),
                          " n_missing=fail\n");
                else
                    Print("  [t+", Runtime() - batch_t0,
                          "ms] H_CACHE EXTEND ", hi, "/", Length(H_CACHE),
                          " n_missing=", Length(missing), "\n");
                fi;
                last_hb := Runtime();
                last_hb_count := hi;
            fi;
            if missing = fail then
                ExtendHCacheEntry(H_CACHE[hi], W_ML, LEFT_Q_GROUPS);
            elif Length(missing) > 0 then
                ExtendHCacheEntry(H_CACHE[hi], W_ML, missing);
            fi;
            # Opt 9b: extend-phase checkpoint.  After each entry, if we've
            # crossed the elapsed threshold and there's more work, persist
            # the partially-extended cache and quit.  No RESUME_EXTEND state
            # is needed: on restart, the extend-needed loop above re-derives
            # which entries still need extension from their computed_q_ids.
            # We still write a placeholder state.g so the orchestrator's
            # resume loop knows to re-invoke GAP.
            # Soft state save (no exit) every STATE_SAVE_INTERVAL_MS.
            if STATE_FILE <> "" and STATE_SAVE_INTERVAL_MS > 0
               and Runtime() - LAST_STATE_SAVE_MS >= STATE_SAVE_INTERVAL_MS
               and hi < Length(H_CACHE)
               and CACHE_LEFT_PATH <> "" then
                SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
                tmp := Concatenation(STATE_FILE, ".tmp");
                PrintTo(tmp, "RESUME_EXTEND := rec( done_until := ", hi, " );\n");
                Exec(Concatenation("mv -f -- '", tmp, "' '", STATE_FILE, "'"));
                LAST_STATE_SAVE_MS := Runtime();
                Print("[soft_checkpoint] EXTEND done_until=", hi,
                      "/", Length(H_CACHE),
                      " elapsed_ms=", Runtime() - WORKER_START, "\n");
            fi;
            if STATE_FILE <> "" and CHECKPOINT_INTERVAL_MS > 0
               and Runtime() - WORKER_START >= CHECKPOINT_INTERVAL_MS
               and hi < Length(H_CACHE)
               and CACHE_LEFT_PATH <> "" then
                SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
                tmp := Concatenation(STATE_FILE, ".tmp");
                PrintTo(tmp, "RESUME_EXTEND := rec( done_until := ", hi, " );\n");
                Exec(Concatenation("mv -f -- '", tmp, "' '", STATE_FILE, "'"));
                Print("CHECKPOINT_PAUSE_EXTEND done_until=", hi,
                      "/", Length(H_CACHE),
                      " elapsed_ms=", Runtime() - WORKER_START, "\n");
                LogTo();
                QuitGap();
            fi;
        od;
        if CACHE_LEFT_PATH <> "" then
            SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
        fi;
        # Clear RESUME_EXTEND if it was set; pair loop will re-checkpoint
        # if it needs to.  Keep RESUME_STATE / RESUME_BUILD if any are present
        # (shouldn't be in this code path, but defensive).
        if STATE_FILE <> "" and IsExistingFile(STATE_FILE)
           and IsBound(RESUME_EXTEND)
           and not IsBound(RESUME_STATE) and not IsBound(RESUME_BUILD) then
            RemoveFile(STATE_FILE);
        fi;
        Print("[t+", Runtime() - batch_t0, "ms] extension done\n");
    fi;
fi;
if H_CACHE = fail or RESUME_BUILD_NEXT_HI > 0 then
    # SUBGROUPS_LEFT_RAW already loaded above for Q-type derivation.
    if H_CACHE = fail then
        Print("[t+", Runtime() - batch_t0, "ms] no cache; building from scratch\n");
        H_CACHE := [];
        BUILD_START_HI := 1;
    else
        BUILD_START_HI := RESUME_BUILD_NEXT_HI;
    fi;
    Print("[t+", Runtime() - batch_t0, "ms] computing left H_CACHE for ",
          Length(SUBGROUPS_LEFT_RAW), " subgroups (in W_ML)",
          " from entry ", BUILD_START_HI, "...\n");
    last_hb := Runtime();
    last_hb_count := 0;
    for hi in [BUILD_START_HI..Length(SUBGROUPS_LEFT_RAW)] do
        if hi = BUILD_START_HI or hi - last_hb_count >= 500
           or Runtime() - last_hb >= 60000 then
            Print("  [t+", Runtime() - batch_t0, "ms] H_CACHE starting ",
                  hi, "/", Length(SUBGROUPS_LEFT_RAW),
                  " |H|=", Size(SUBGROUPS_LEFT_RAW[hi]), "\n");
            last_hb := Runtime();
            last_hb_count := hi;
        fi;
        Add(H_CACHE, ComputeHCacheEntry(SUBGROUPS_LEFT_RAW[hi], W_ML, LEFT_Q_GROUPS));
        # Opt 9: build-phase checkpoint.  After each entry, if we've crossed
        # the elapsed threshold AND there's more work to do, save partial
        # cache + state.g and quit.  Python relaunches; on resume,
        # RESUME_BUILD_NEXT_HI points us to continue from hi+1.
        # Soft state save (no exit) every STATE_SAVE_INTERVAL_MS.
        if STATE_FILE <> "" and STATE_SAVE_INTERVAL_MS > 0
           and Runtime() - LAST_STATE_SAVE_MS >= STATE_SAVE_INTERVAL_MS
           and hi < Length(SUBGROUPS_LEFT_RAW)
           and CACHE_LEFT_PATH <> "" then
            SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
            tmp := Concatenation(STATE_FILE, ".tmp");
            PrintTo(tmp, "RESUME_BUILD := rec( next_hi := ", hi + 1, " );\n");
            Exec(Concatenation("mv -f -- '", tmp, "' '", STATE_FILE, "'"));
            LAST_STATE_SAVE_MS := Runtime();
            Print("[soft_checkpoint] BUILD next_hi=", hi + 1,
                  " of=", Length(SUBGROUPS_LEFT_RAW),
                  " elapsed_ms=", Runtime() - WORKER_START, "\n");
        fi;
        if STATE_FILE <> "" and CHECKPOINT_INTERVAL_MS > 0
           and Runtime() - WORKER_START >= CHECKPOINT_INTERVAL_MS
           and hi < Length(SUBGROUPS_LEFT_RAW)
           and CACHE_LEFT_PATH <> "" then
            SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
            tmp := Concatenation(STATE_FILE, ".tmp");
            PrintTo(tmp, "RESUME_BUILD := rec( next_hi := ", hi + 1, " );\n");
            Exec(Concatenation("mv -f -- '", tmp, "' '", STATE_FILE, "'"));
            Print("CHECKPOINT_PAUSE_BUILD next_hi=", hi + 1,
                  " of=", Length(SUBGROUPS_LEFT_RAW),
                  " elapsed_ms=", Runtime() - WORKER_START, "\n");
            LogTo();
            QuitGap();
        fi;
    od;
    Print("[t+", Runtime() - batch_t0, "ms] H_CACHE compute done\n");
    if CACHE_LEFT_PATH <> "" then
        SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
    fi;
    # Build done — clear any RESUME_BUILD state so the pair loop starts
    # cleanly.  (RESUME_STATE if present remains for pair-loop resume.)
    if RESUME_BUILD_NEXT_HI > 0 and STATE_FILE <> "" and IsExistingFile(STATE_FILE) then
        RemoveFile(STATE_FILE);
        RESUME_BUILD_NEXT_HI := 0;
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

Print("JOBS: ", Length(JOBS), " jobs to run\n");

# Per-job processing.  RESUME_JOB_IDX was set during the checkpoint setup
# block (which runs before the LEFT cache build).
for job_idx in [RESUME_JOB_IDX..Length(JOBS)] do
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
    H2DATA := fail;
    if JOB.right_tg_d > 0 then
        T_orig_j := TransitiveGroup(JOB.right_tg_d, JOB.right_tg_t);
        H2DATA := [ComputeHDataDirect(T_orig_j, S_MR, LEFT_Q_GROUPS)];
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
                        ExtendHCacheEntry(H_CACHE[hi], S_MR, LEFT_Q_GROUPS);
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
    if H2DATA = fail then
        H2DATA := List(H_CACHE_R, e -> ReconstructHData(e, S_MR));
    fi;

    # ---- Goursat counting + collect generator lines for emission ----
    # Honor resume state for the resuming job; fresh start for later jobs.
    if job_idx = RESUME_JOB_IDX then
        fp_lines := RESUME_FP_LINES;
        i_resume_start := RESUME_PAIR_I;
        j_resume_start := RESUME_PAIR_J;
        resume_total_orb := RESUME_TOTAL_ORB;
        resume_total_fix := RESUME_TOTAL_FIX;
    else
        fp_lines := [];
        i_resume_start := 1;
        j_resume_start := 1;
        resume_total_orb := 0;
        resume_total_fix := 0;
    fi;

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

    EmitGenList := function(gens)
        local s;
        if Length(gens) > 0 then
            s := JoinStringsWithSeparator(List(gens, String), ",");
        else
            s := "";
        fi;
        Add(fp_lines, Concatenation("[", s, "]"));
    end;

    FiberProductGeneratorList := function(H1data, h1orb, h2orb, phi)
        local gens, g, img_q, preimg, gen, n;
        gens := [];
        for g in GeneratorsOfGroup(h1orb.H_ref) do
            img_q := Image(phi, Image(h1orb.hom, g));
            preimg := PreImagesRepresentative(h2orb.shifted_hom, img_q);
            gen := g * preimg;
            if gen <> () then Add(gens, gen); fi;
        od;
        for n in GeneratorsOfGroup(Kernel(h2orb.shifted_hom)) do
            if n <> () then Add(gens, n); fi;
        od;
        return gens;
    end;

    ProcessPairBatch := function(H1data, H2data, H1, H2)
        local total, swap_fixed, h1orb, h2idxs, h2idx, h2orb, key, isoTH,
              isos, n, gensQ, KeyOf, idx, seen, n_orb, queue, j, phi,
              alpha, beta, neighbor, nkey, k, fp, orbit_id, i, swap_phi,
              swap_key, swap_iso_idx, swap_orbit_id,
              h1_orb_idx, orbit_reps_phi, h_0, t_0, swap_orb_id_arr,
              gens_for_fp,
              dcs, A1, A2_in_h1, A2_in_h1_gens, tinv, g_swap,
          bench_t0, bench_t1, h2_shifted_hom;
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
                            EmitGenList(Concatenation(H1data.H_gens_noid,
                                                      H2data.shifted_H_gens_noid));
                        fi;
                        if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                            swap_fixed := swap_fixed + 1;
                        fi;
                    fi;
                od;
                continue;
            fi;

            if h1orb.qsize = 2 then
                # Use the direct C_2 shortcut only when the RIGHT factor is
                # literally degree 2.  For MR>2, keep the C_2 orbit shortcut
                # but build the subgroup through the quotient homomorphisms.
                if MR = 2 then
                    for h2idx in h2idxs do
                        h2orb := H2data.orbits[h2idx];
                        if h2orb.qsize <> 2 then continue; fi;
                        total := total + 1;
                        if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                            EnsureC2Representative(h1orb);
                            EnsureShiftedKGenerators(h2orb);
                            EnsureShiftedC2Representative(h2orb);
                            EmitGenList(Concatenation(
                                h1orb.K_gens_noid,
                                h2orb.shifted_K_gens_noid,
                                [h1orb.c2_rep * h2orb.shifted_c2_rep]));
                        fi;
                        if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                            swap_fixed := swap_fixed + 1;
                        fi;
                    od;
                else
                    for h2idx in h2idxs do
                        h2orb := H2data.orbits[h2idx];
                        if h2orb.qsize <> 2 then continue; fi;
                        total := total + 1;
                        if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                            EnsureHom(h1orb); EnsureHom(h2orb);
                            isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
                            if isoTH <> fail then
                                EnsureShiftedHom(h2orb, H2);
                                fp := _GoursatBuildFiberProduct(
                                    H1, H2, h1orb.hom,
                                    h2orb.shifted_hom,
                                    InverseGeneralMapping(isoTH),
                                    [1..ML], [ML+1..ML+MR]);
                                if fp <> fail then EmitGen(fp); fi;
                            fi;
                        fi;
                        if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                            swap_fixed := swap_fixed + 1;
                        fi;
                    od;
                fi;
                continue;
            fi;

            for h2idx in h2idxs do
                h2orb := H2data.orbits[h2idx];
                if h2orb.qsize <> h1orb.qsize then continue; fi;
                EnsureHom(h1orb); EnsureHom(h2orb);
                EnsureShiftedHom(h2orb, H2);
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
                    if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                A1 := SafeSub(h1orb.AutQ, h1orb.A_gens);
                    # Use InducedAutomorphism to transport b to Aut(h1.Q).
                    # Opt #5: A_gens already in canonical Aut(Q); skip isoTH transport.
                    A2_in_h1 := SafeSub(h1orb.AutQ, h2orb.A_gens);
                    dcs := LookupOrComputeDC(h1orb, A1, A2_in_h1);
                    n_orb := Length(dcs);
                    orbit_reps_phi := List(dcs, dc ->
                    h2orb.iso_to_can * Representative(dc) * InverseGeneralMapping(h1orb.iso_to_can));
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
                        gens_for_fp := FiberProductGeneratorList(
                            H1data, h1orb, h2orb,
                            InverseGeneralMapping(orbit_reps_phi[i]));
                        EmitGenList(gens_for_fp);
                    od;
                elif BURNSIDE_M2 = 1 and h2idx = h1_orb_idx then
                    # Self-pair: within-pair canonical (i <= swap_orb_id[i]).
                    for i in [1..n_orb] do
                        if swap_orb_id_arr[i] >= i then
                            gens_for_fp := FiberProductGeneratorList(
                                H1data, h1orb, h2orb,
                                InverseGeneralMapping(orbit_reps_phi[i]));
                            EmitGenList(gens_for_fp);
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

    TOTAL_ORB := resume_total_orb;
    TOTAL_FIX := resume_total_fix;
    last_hb_ms := Runtime() - job_t0;
    n_pairs_done := (i_resume_start - 1) * Length(H2DATA);
    n_pairs_total := Length(H1DATA_LIST) * Length(H2DATA);
    if i_resume_start > 1 then
        Print("    [t+", Runtime() - job_t0, "ms] resuming pair loop at i=",
              i_resume_start, "/", Length(H1DATA_LIST),
              " (", n_pairs_done, " pairs already done, orb=", TOTAL_ORB, ")\n");
    else
        Print("    [t+", Runtime() - job_t0, "ms] starting H1xH2 loop: ",
              Length(H1DATA_LIST), " x ", Length(H2DATA),
              " = ", n_pairs_total, " pairs\n");
    fi;
    # Optimization (4) 2026-04-28: precompute shifted RIGHT once per j outside
    # the i loop.  For burnside_m2 mode, H2DATA[1] gets overwritten per-i so
    # we must compute per-pair (only 1 entry, so cheap).
    if BURNSIDE_M2 = 0 then
        for H2data_j in H2DATA do EnsureShiftedHData(H2data_j); od;
        H2_SHIFTED := List(H2DATA, hd -> hd.shifted_H);
    fi;
    for i in [i_resume_start..Length(H1DATA_LIST)] do
        H1data_j := H1DATA_LIST[i];
        H1_j := H1data_j.H;
        # For burnside_m2: override H2DATA[1] with H1data so K = K comparison works.
        if BURNSIDE_M2 = 1 then
            H2DATA[1] := H1data_j;
        fi;
        # j_lo honours mid-i resume only on the first iteration.
        j_lo := 1;
        if i = i_resume_start then j_lo := j_resume_start; fi;
        for j in [j_lo..Length(H2DATA)] do
            H2data_j := H2DATA[j];
            if BURNSIDE_M2 = 0 then
                H2_j := H2_SHIFTED[j];
            else
                EnsureShiftedHData(H2data_j);
                H2_j := H2data_j.shifted_H;
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
            # Soft state save (no exit) every STATE_SAVE_INTERVAL_MS.  Caps
            # work loss from unplanned crashes (OOM etc.) to the soft-save
            # interval rather than up to CHECKPOINT_INTERVAL_MS (= the gap
            # between the previous hard checkpoint and now).  fp_lines is
            # the bulky payload (multi-MB at scale); write atomically via
            # tmp + mv.  Skips on last pair (nothing to resume).
            if STATE_FILE <> "" and STATE_SAVE_INTERVAL_MS > 0
               and Runtime() - LAST_STATE_SAVE_MS >= STATE_SAVE_INTERVAL_MS
               and (j < Length(H2DATA) or i < Length(H1DATA_LIST)) then
                next_i := i;
                next_j := j + 1;
                if next_j > Length(H2DATA) then
                    next_i := i + 1;
                    next_j := 1;
                fi;
                tmp := Concatenation(STATE_FILE, ".tmp");
                PrintTo(tmp, "RESUME_STATE := rec(\n",
                    "  job_idx := ", job_idx, ",\n",
                    "  pair_i := ", next_i, ",\n",
                    "  pair_j := ", next_j, ",\n",
                    "  total_orb := ", TOTAL_ORB, ",\n",
                    "  total_fix := ", TOTAL_FIX, ",\n",
                    "  fp_lines := ", fp_lines, "\n",
                    ");\n");
                Exec(Concatenation("mv -f -- '", tmp, "' '", STATE_FILE, "'"));
                LAST_STATE_SAVE_MS := Runtime();
                Print("[soft_checkpoint] job_idx=", job_idx,
                      " pair_i=", next_i, "/", Length(H1DATA_LIST),
                      " pair_j=", next_j,
                      " orb=", TOTAL_ORB,
                      " elapsed_ms=", Runtime() - WORKER_START, "\n");
            fi;
            # Per-pair checkpoint (post-pair).  After CHECKPOINT_INTERVAL_MS
            # have elapsed since worker start, save state at the next pair
            # boundary and exit.  Closes the n_left=1/2 hole where end-of-i
            # checkpointing never fired.  Bounds heap to ~30 min of pair work,
            # critical for combos like [2,1]_[2,1] x [4,3]^4 where a single
            # i can take days due to GAP runtime degradation.
            if STATE_FILE <> "" and CHECKPOINT_INTERVAL_MS > 0
               and Runtime() - WORKER_START >= CHECKPOINT_INTERVAL_MS
               and (j < Length(H2DATA) or i < Length(H1DATA_LIST)) then
                next_i := i;
                next_j := j + 1;
                if next_j > Length(H2DATA) then
                    next_i := i + 1;
                    next_j := 1;
                fi;
                tmp := Concatenation(STATE_FILE, ".tmp");
                PrintTo(tmp, "RESUME_STATE := rec(\n",
                    "  job_idx := ", job_idx, ",\n",
                    "  pair_i := ", next_i, ",\n",
                    "  pair_j := ", next_j, ",\n",
                    "  total_orb := ", TOTAL_ORB, ",\n",
                    "  total_fix := ", TOTAL_FIX, ",\n",
                    "  fp_lines := ", fp_lines, "\n",
                    ");\n");
                Exec(Concatenation("mv -f -- '", tmp, "' '", STATE_FILE, "'"));
                Print("CHECKPOINT_PAUSE job_idx=", job_idx,
                      " next_pair_i=", next_i,
                      " next_pair_j=", next_j,
                      " of=", Length(H1DATA_LIST), "x", Length(H2DATA),
                      " orb=", TOTAL_ORB,
                      " elapsed_ms=", Runtime() - WORKER_START, "\n");
                LogTo();
                QuitGap();
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
    # Stream-based: open ONCE, WriteAll many times (100x+ faster than
    # AppendTo-per-line on Cygwin).
    TMP_OUT := Concatenation(OUTPUT_PATH, ".tmp");
    OUT_STREAM := OutputTextFile(TMP_OUT, false);
    SetPrintFormattingStatus(OUT_STREAM, false);
    WriteAll(OUT_STREAM, Concatenation(COMBO_HEADER, "\n"));
    WriteAll(OUT_STREAM, Concatenation("# candidates: ", String(PREDICTED), "\n"));
    WriteAll(OUT_STREAM, Concatenation("# deduped: ", String(PREDICTED), "\n"));
    WriteAll(OUT_STREAM, Concatenation("# elapsed_ms: ", String(elapsed_ms), "\n"));
    for line in fp_lines do
        WriteAll(OUT_STREAM, Concatenation(line, "\n"));
    od;
    CloseStream(OUT_STREAM);
    Exec(Concatenation("mv -f -- '", TMP_OUT, "' '", OUTPUT_PATH, "'"));

    Print("RESULT idx=", job_idx, " predicted=", PREDICTED,
          " orbits=", TOTAL_ORB, " swap_fixed=", TOTAL_FIX,
          " elapsed_ms=", elapsed_ms, "\n");

    # Between-JOB checkpoint: after RESULT is written, if elapsed exceeds
    # threshold and there are more jobs, save state with the NEXT job_idx
    # (fresh pair state) and quit.  Bounds heap to one JOB's worth.  Pair-loop
    # checkpoint can't fire when n_left = 1 or 2 (its `i < n_left` gate is
    # false at end of last i), so this is the only between-job heap reset.
    if STATE_FILE <> "" and CHECKPOINT_INTERVAL_MS > 0
       and Runtime() - WORKER_START >= CHECKPOINT_INTERVAL_MS
       and job_idx < Length(JOBS) then
        tmp := Concatenation(STATE_FILE, ".tmp");
        PrintTo(tmp, "RESUME_STATE := rec(\n",
            "  job_idx := ", job_idx + 1, ",\n",
            "  pair_i := 1,\n",
            "  total_orb := 0,\n",
            "  total_fix := 0,\n",
            "  fp_lines := [ ]\n",
            ");\n");
        Exec(Concatenation("mv -f -- '", tmp, "' '", STATE_FILE, "'"));
        Print("CHECKPOINT_PAUSE end_of_job=", job_idx,
              " next_job_idx=", job_idx + 1, "/", Length(JOBS),
              " elapsed_ms=", Runtime() - WORKER_START, "\n");
        LogTo();
        QuitGap();
    fi;
od;

# All jobs done — remove the state file so the orchestrator's resume loop
# stops re-invoking us.
if STATE_FILE <> "" and IsExistingFile(STATE_FILE) then
    RemoveFile(STATE_FILE);
fi;

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

# Linear-orbits flag + Stage A/B prototype load.  See BATCH_DRIVER for details.
USE_LINEAR_ORBITS := __USE_LINEAR_ORBITS__;
if USE_LINEAR_ORBITS = 1 then
    Print("[USE_LINEAR_ORBITS=1] loading Stage A/B prototypes...\n");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_a.g");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_b.g");
fi;

if not IsBound(_GoursatBuildFiberProduct) then Read("__LIFTING_G__"); fi;

ConjAction := function(K, g) return K^g; end;

SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

# === META catalog + H-iso -> Q-iso cache (Opts 1+2, 2026-05-09) ===========
# Opt 1: avoid re-reading the 6065-entry q_catalog.g per ComputeOrLoadLeftQGroups
#        call within a single GAP session.  _META_CATALOG_LOADED_PATH holds
#        the path that was loaded into the global META_Q_CATALOG; subsequent
#        calls with the same path reuse the in-memory list.
# Opt 2: file-based per-H-iso QT cache.  Master file h_to_qs.g shared across
#        all super-batches and orchestrator runs; workers READ master,
#        accumulate new entries in _META_H_TO_QS_NEW, write per-session
#        fragments, orchestrator merges fragments into master.
#        H_TO_QS lookup is keyed by SafeId(H) string.  Only safe iso-classes
#        (h_id[2] = 0) are cached; unsafe (heuristic SafeId) bypass cache.
if not IsBound(_META_CATALOG_LOADED_PATH) then
    _META_CATALOG_LOADED_PATH := "";
fi;
if not IsBound(_META_H_TO_QS_LOADED_PATH) then
    _META_H_TO_QS_LOADED_PATH := "";
fi;
if not IsBound(_META_H_TO_QS_RECORD) then
    _META_H_TO_QS_RECORD := rec();   # sanitized-key -> qid list
fi;
if not IsBound(_META_H_TO_QS_NEW) then
    _META_H_TO_QS_NEW := [];          # list of [h_id_str, [qid, ...]]
fi;

# Convert SafeId(H) string (e.g. "[ 36, 0, [ 36, 3 ] ]") to a valid GAP
# record-field identifier by stripping spaces/brackets.  Deterministic and
# collision-free for SafeId outputs.
SanitizeHidStr := function(s)
    local out, c;
    out := "h";
    for c in s do
        if c = ' ' or c = ',' then Add(out, '_');
        elif c = '[' or c = ']' then ;
        else Add(out, c);
        fi;
    od;
    return out;
end;

# Load master catalog from path; cache in METAQCATALOG global.  Skip disk
# read if already loaded from same path in this GAP session.
_LoadMasterCatalog := function(path)
    if path = "" then return fail; fi;
    if _META_CATALOG_LOADED_PATH = path and IsBound(META_Q_CATALOG) then
        return META_Q_CATALOG;
    fi;
    if not IsExistingFile(path) then return fail; fi;
    META_Q_CATALOG_SAVED_OK := false;
    Read(path);
    if IsBound(META_Q_CATALOG_SAVED_OK) and META_Q_CATALOG_SAVED_OK = true
       and IsBound(META_Q_CATALOG) then
        _META_CATALOG_LOADED_PATH := path;
        Print("[QGroups] loaded master catalog: ", Length(META_Q_CATALOG),
              " types from ", path, "\n");
        return META_Q_CATALOG;
    fi;
    Print("[QGroups] master catalog file present but invalid sentinel - ignoring\n");
    return fail;
end;

# Load h_to_qs master file (a list of [h_id_str, qid_list] pairs).  Builds
# an in-memory record keyed by SanitizeHidStr(h_id_str) for O(log) lookup.
# Idempotent within a GAP session (only re-reads if path differs).  Also
# loads pending fragments produced by other workers in this run.
_LoadHToQs := function(master_path, fragments_dir)
    local rec_obj, entry, key, fragments, fpath, frag_count, frag_added;
    if _META_H_TO_QS_LOADED_PATH = master_path and master_path <> "" then
        return _META_H_TO_QS_RECORD;
    fi;
    rec_obj := rec();
    if master_path <> "" and IsExistingFile(master_path) then
        META_H_TO_QS_SAVED_OK := false;
        META_H_TO_QS := [];
        Read(master_path);
        if IsBound(META_H_TO_QS_SAVED_OK) and META_H_TO_QS_SAVED_OK = true
           and IsBound(META_H_TO_QS) then
            for entry in META_H_TO_QS do
                key := SanitizeHidStr(entry[1]);
                rec_obj.(key) := entry[2];
            od;
            Print("[QGroups] loaded H_TO_QS master: ",
                  Length(META_H_TO_QS), " entries from ", master_path, "\n");
        fi;
    fi;
    # Also pre-merge any fragments that have not yet been consolidated.
    # Workers in the current run may have written fragments before this
    # worker started; reading them gives in-process cache hits.
    frag_count := 0;
    frag_added := 0;
    if fragments_dir <> "" and IsDirectoryPath(fragments_dir) then
        fragments := DirectoryContents(fragments_dir);
        for fpath in fragments do
            if Length(fpath) >= 2 and fpath{[Length(fpath)-1..Length(fpath)]} = ".g" then
                META_H_TO_QS_NEW_SAVED_OK := false;
                META_H_TO_QS_NEW := [];
                Read(Concatenation(fragments_dir, "/", fpath));
                if IsBound(META_H_TO_QS_NEW_SAVED_OK) and META_H_TO_QS_NEW_SAVED_OK = true then
                    frag_count := frag_count + 1;
                    for entry in META_H_TO_QS_NEW do
                        key := SanitizeHidStr(entry[1]);
                        if not IsBound(rec_obj.(key)) then
                            rec_obj.(key) := entry[2];
                            frag_added := frag_added + 1;
                        fi;
                    od;
                fi;
            fi;
        od;
        if frag_count > 0 then
            Print("[QGroups] absorbed ", frag_count, " fragment(s) -> ",
                  frag_added, " new H entries\n");
        fi;
    fi;
    _META_H_TO_QS_LOADED_PATH := master_path;
    _META_H_TO_QS_RECORD := rec_obj;
    # Reset the new-entries accumulator for THIS session (we never re-emit
    # entries we just absorbed from fragments).
    _META_H_TO_QS_NEW := [];
    return _META_H_TO_QS_RECORD;
end;

# Append _META_H_TO_QS_NEW to a fragment file (atomic tmp+mv).  Caller is
# responsible for clearing _META_H_TO_QS_NEW after a successful write if it
# wants to avoid double-emitting on subsequent calls in the same session.
_SaveHToQsFragment := function(fragment_path)
    local tmp;
    if fragment_path = "" or Length(_META_H_TO_QS_NEW) = 0 then return; fi;
    tmp := Concatenation(fragment_path, ".tmp");
    PrintTo(tmp, "META_H_TO_QS_NEW := ", _META_H_TO_QS_NEW, ";\n",
                 "META_H_TO_QS_NEW_SAVED_OK := true;\n");
    Exec(Concatenation("mv -f -- '", tmp, "' '", fragment_path, "'"));
    Print("[QGroups] saved H_TO_QS fragment: ", Length(_META_H_TO_QS_NEW),
          " new entries -> ", fragment_path, "\n");
end;

# Cache the SUBS_RIGHT walk: walking each R in subs_right.g and enumerating
# `for K in NormalSubgroups(R)` to get the Q-types of the right side.  Cache
# is keyed by cache_right_path (stable across runs).  Sidecar file is
# <cache_right_path>.right_qgroups.g; sentinel RIGHT_QGROUPS_FROM_SUBS_SAVED_OK.
LoadOrComputeRightQGroupsFromSubs := function(subs_right_path, cache_right_path)
    local sidecar, tmp, R, K, Q, qid, seen, result;
    if subs_right_path = "" then return []; fi;
    if cache_right_path <> "" then
        sidecar := Concatenation(cache_right_path, ".right_qgroups.g");
        if IsExistingFile(sidecar) then
            RIGHT_QGROUPS_FROM_SUBS_SAVED_OK := false;
            Read(sidecar);
            if IsBound(RIGHT_QGROUPS_FROM_SUBS_SAVED_OK) and RIGHT_QGROUPS_FROM_SUBS_SAVED_OK = true
               and IsBound(RIGHT_QGROUPS_FROM_SUBS) then
                Print("[QGroups] loaded RIGHT-derived qgroups from cache: ",
                      Length(RIGHT_QGROUPS_FROM_SUBS), " types from ", sidecar, "\n");
                return RIGHT_QGROUPS_FROM_SUBS;
            fi;
        fi;
    else
        sidecar := "";
    fi;
    Read(subs_right_path);
    result := [];
    seen := Set([]);
    for R in SUBGROUPS do
        for K in NormalSubgroups(R) do
            if Size(K) = Size(R) then continue; fi;
            Q := R/K;
            qid := SafeId(Q);
            if not (qid in seen) then
                AddSet(seen, qid);
                Add(result, Q);
            fi;
        od;
    od;
    # Normalize FactorGroup objects (their abstract f1, f2 generator names
    # would not be re-bindable on Read of the cached sidecar).
    result := List(result, function(q)
        local n, q_id;
        n := Size(q);
        if IdGroupsAvailable(n) then
            q_id := IdGroup(q);
            return SmallGroup(n, q_id[2]);
        else
            return Image(IsomorphismPermGroup(q));
        fi;
    end);
    if sidecar <> "" then
        tmp := Concatenation(sidecar, ".tmp");
        PrintTo(tmp, "RIGHT_QGROUPS_FROM_SUBS := ", result, ";\n",
                     "RIGHT_QGROUPS_FROM_SUBS_SAVED_OK := true;\n");
        Exec(Concatenation("mv -f -- '", tmp, "' '", sidecar, "'"));
        Print("[QGroups] saved RIGHT-derived qgroups: ", Length(result),
              " types -> ", sidecar, "\n");
    fi;
    return result;
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
    res := rec(H := H, N := N,
        H_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_H := fail, shifted_H_gens_noid := fail,
        orbits := []);
    # Trivial-quotient orbit (always present; hom is fast for H/H).
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N, AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
        K_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_K_gens_noid := fail, c2_rep := fail, shifted_c2_rep := fail,
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
            Stab := Stab, AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
            K_gens_noid := Filtered(GeneratorsOfGroup(K), g -> g <> ()),
            shifted_K_gens_noid := fail, c2_rep := fail, shifted_c2_rep := fail,
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
    local qid_str, can_entry, raw_a_gens;
    if orb.AutQ <> fail then return; fi;
    if orb.qsize <= 1 then return; fi;   # trivial Q has no auto
    EnsureHom(orb);   # AutQ depends on Q
    # Opt #5: canonical Q registry.  First orbit with a given qid registers
    # its Q + AutQ as canonical.  Subsequent orbits compute iso_to_can and
    # share the canonical AutQ.  A_gens are transported to canonical Aut(Q).
    qid_str := String(orb.qid);
    if not IsBound(QCAN_TABLE.(qid_str)) then
        QCAN_TABLE.(qid_str) := rec(Q := orb.Q, AutQ := AutomorphismGroup(orb.Q));
        orb.iso_to_can := IdentityMapping(orb.Q);
    else
        can_entry := QCAN_TABLE.(qid_str);
        orb.iso_to_can := IsomorphismGroups(orb.Q, can_entry.Q);
        if orb.iso_to_can = fail then
            # Should not happen: matching qid implies iso classes match.  Fall
            # back to fresh AutQ + identity to avoid runtime error; A_gens
            # below stay in orb.Q's Aut, so canonical sharing won't apply.
            QCAN_TABLE.(qid_str) := rec(Q := orb.Q, AutQ := AutomorphismGroup(orb.Q));
            orb.iso_to_can := IdentityMapping(orb.Q);
        fi;
    fi;
    can_entry := QCAN_TABLE.(qid_str);
    orb.AutQ := can_entry.AutQ;
    raw_a_gens := InducedAutoGens(orb.Stab, orb.H_ref, orb.hom);
    orb.A_gens := List(raw_a_gens, a -> InducedAutomorphism(orb.iso_to_can, a));
    # Optimization (3) 2026-04-28: cache full_aut.
    if Length(orb.A_gens) = 0 then
        orb.full_aut := false;
    else
        orb.full_aut := (Size(Subgroup(orb.AutQ, orb.A_gens)) = Size(orb.AutQ));
    fi;
end;

# Opt #1: lazily compute and cache the shifted-right quotient hom
# on h2orb.shifted_hom.  Used by C2-safe and general emit paths to
# skip rebuilding CompositionMapping(orb.hom, ConjugatorIsomorphism(
# H2_shifted, shift_R^-1)) on every emission.  Within one predict()
# call, H2_shifted is fixed for a given h2orb (parent H2data.H +
# file-global shift_R), so safe to reuse.
EnsureShiftedHom := function(orb, H2_shifted)
    if orb.shifted_hom <> fail then return; fi;
    EnsureHom(orb);
    orb.shifted_hom := CompositionMapping(orb.hom,
        ConjugatorIsomorphism(H2_shifted, shift_R^-1));
end;

EnsureShiftedHData := function(Hdata)
    if Hdata.shifted_H <> fail then return; fi;
    Hdata.shifted_H := Hdata.H^shift_R;
    Hdata.shifted_H_gens_noid := List(Hdata.H_gens_noid, g -> g^shift_R);
end;

EnsureShiftedKGenerators := function(orb)
    if orb.shifted_K_gens_noid <> fail then return; fi;
    orb.shifted_K_gens_noid := List(orb.K_gens_noid, g -> g^shift_R);
end;

EnsureC2Representative := function(orb)
    if orb.c2_rep <> fail then return; fi;
    orb.c2_rep := First(GeneratorsOfGroup(orb.H_ref),
                         g -> not (g in orb.K));
end;

EnsureShiftedC2Representative := function(orb)
    if orb.shifted_c2_rep <> fail then return; fi;
    EnsureC2Representative(orb);
    orb.shifted_c2_rep := orb.c2_rep^shift_R;
end;

# Opt #4: cache DoubleCosets results per h1orb keyed by the A2_in_h1
# subgroup.  Linear-list lookup; comparison via group equality.  Cache
# grows with distinct A2_in_h1 subgroups seen for this h1orb (bounded
# by the number of distinct quotient/iso classes among matching h2orbs).
LookupOrComputeDC := function(h1orb, A1, A2_in_h1)
    local entry, dcs;
    if h1orb.dc_cache = fail then h1orb.dc_cache := []; fi;
    for entry in h1orb.dc_cache do
        if entry[1] = A2_in_h1 then
            if BENCH_PHASES = 1 then BENCH_N.n_dc_cache_hits := BENCH_N.n_dc_cache_hits + 1; fi;
            return entry[2];
        fi;
    od;
    if BENCH_PHASES = 1 then BENCH_N.n_dc_cache_misses := BENCH_N.n_dc_cache_misses + 1; fi;
    dcs := DoubleCosets(h1orb.AutQ, A2_in_h1, A1);
    Add(h1orb.dc_cache, [A2_in_h1, dcs]);
    return dcs;
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
    local result, seen, t, T, K, Q, qid, key, cache_path, slash, i, t0;
    # Two-tier cache: in-memory (per-GAP-session) + file (across sessions).
    # Without caching, NrTransitiveGroups(MR)=301 at MR=12 forces a ~hour-long
    # walk on every call, multiplied by hundreds of per-job invocations.
    if not IsBound(_REQUIRED_QGROUPS_CACHE) then _REQUIRED_QGROUPS_CACHE := rec(); fi;
    key := Concatenation("m", String(M_R));
    if IsBound(_REQUIRED_QGROUPS_CACHE.(key)) then
        return _REQUIRED_QGROUPS_CACHE.(key);
    fi;
    # File cache: <META_CATALOG_PATH-dir>/required_qgroups_m<MR>.g
    cache_path := "";
    if IsBound(META_CATALOG_PATH) and META_CATALOG_PATH <> "" then
        slash := 0;
        for i in [Length(META_CATALOG_PATH), Length(META_CATALOG_PATH)-1..1] do
            if META_CATALOG_PATH[i] = '/' then slash := i; break; fi;
        od;
        if slash > 0 then
            cache_path := Concatenation(
                META_CATALOG_PATH{[1..slash]},
                "required_qgroups_m", String(M_R), ".g");
        fi;
    fi;
    if cache_path <> "" and IsExistingFile(cache_path) then
        REQUIRED_QGROUPS_CACHED_SAVED_OK := false;
        Read(cache_path);
        if IsBound(REQUIRED_QGROUPS_CACHED_SAVED_OK) and REQUIRED_QGROUPS_CACHED_SAVED_OK = true
           and IsBound(REQUIRED_QGROUPS_CACHED) then
            _REQUIRED_QGROUPS_CACHE.(key) := REQUIRED_QGROUPS_CACHED;
            Print("[RequiredQGroups] loaded from file cache: ",
                  Length(REQUIRED_QGROUPS_CACHED), " types for M_R=", M_R, "\n");
            return REQUIRED_QGROUPS_CACHED;
        fi;
    fi;
    # Compute
    result := [];
    seen := Set([]);
    if M_R = 0 then
        _REQUIRED_QGROUPS_CACHE.(key) := result;
        return result;
    fi;
    t0 := Runtime();
    Print("[RequiredQGroups] computing for M_R=", M_R, " (",
          NrTransitiveGroups(M_R), " transitive groups)...\n");
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
    # Normalize for safe re-Read (FactorGroup uses unbound generator names).
    result := List(result, function(q)
        local n, q_id;
        n := Size(q);
        if IdGroupsAvailable(n) then
            q_id := IdGroup(q);
            return SmallGroup(n, q_id[2]);
        else
            return Image(IsomorphismPermGroup(q));
        fi;
    end);
    Print("[RequiredQGroups] computed M_R=", M_R, ": ", Length(result),
          " types in ", Runtime() - t0, "ms\n");
    if cache_path <> "" then
        PrintTo(Concatenation(cache_path, ".tmp"),
                "REQUIRED_QGROUPS_CACHED := ", result, ";\n",
                "REQUIRED_QGROUPS_CACHED_SAVED_OK := true;\n");
        Exec(Concatenation("mv -f -- '", cache_path, ".tmp' '", cache_path, "'"));
        Print("[RequiredQGroups] saved file cache for M_R=", M_R, "\n");
    fi;
    _REQUIRED_QGROUPS_CACHE.(key) := result;
    return result;
end;

# Q-iso classes attainable as nontrivial quotients of any group in `groups`.
# Used to derive a TIGHT LEFT_Q_GROUPS filter: in Goursat's theorem the common
# quotient Q must be a quotient of BOTH factors, so deriving Q-types from the
# LEFT subgroup list is at least as tight as RequiredQGroups(M_R) and is
# DRAMATICALLY tighter when M_R >= 6 (where RequiredQGroups returns `fail` =
# full coverage, forcing NormalSubgroups(H) on every right-side H).
QuotientTypesOfGroups := function(arg)
    # Discovers Q-types achievable as H/K for some H in `groups`.
    #
    # When called with one argument (legacy): runs `for K in NormalSubgroups(H)`
    # discovery with iso-class dedup.  Can hang for hours on hostile H entries
    # (observed in S20 production).
    #
    # When called with two arguments (catalog-driven): iterates the master
    # catalog and uses `HasQuotientType(H, Q)` as a sound prefilter.  Never
    # calls `NormalSubgroups(H)` -- bounded runtime.  Result is a SUPERSET of
    # actually-achievable Q's (false positives from HasQuotientType returning
    # true for non-pgroup Q are filtered out at cache-build time by
    # `_EnumerateNormalsForQGroups`).
    #
    # When called with three arguments: third arg is a SafeId-keyed record of
    # already-known H-iso -> qid-list mappings (the META_H_TO_QS cache).  On
    # cache hit for a safe H, skips the catalog sweep and uses cached qids.
    # On miss, runs the sweep and appends the new entry to _META_H_TO_QS_NEW.
    #
    # Iso-class dedup is gated on SafeId(H)[2] = 0 in all paths.
    local groups, master_catalog, h_to_qs, result, seen_qids, seen_h_ids,
          n_total, idx, last_qt_hb, H, h_id, h_id_str, h_id_san, K, Q, q,
          qid, n_skipped, n_safe, master_qids, q_idx, h_size, q_size,
          cached_qids, hit_qids, n_cache_hit, n_cache_miss, qid_to_pos,
          pos;
    groups := arg[1];
    if Length(arg) >= 2 then master_catalog := arg[2]; else master_catalog := fail; fi;
    if Length(arg) >= 3 then h_to_qs := arg[3]; else h_to_qs := fail; fi;
    result := [];
    seen_qids := Set([]);
    seen_h_ids := Set([]);
    n_total := Length(groups);
    last_qt_hb := Runtime();
    idx := 0;
    n_skipped := 0;
    n_safe := 0;
    n_cache_hit := 0;
    n_cache_miss := 0;

    if master_catalog <> fail and Length(master_catalog) > 0 then
        # Catalog-driven path.  Iterates each H against master_catalog using
        # the cheap HasQuotientType structural check.  master_catalog is
        # expected in ascending size order (as seeded by seed_meta_catalog.py),
        # which lets us break the inner loop once Size(Q) > Size(H).
        Print("    [QuotientTypesOfGroups] catalog-driven: |catalog|=",
              Length(master_catalog), " |groups|=", n_total, "\n");
        master_qids := List(master_catalog, SafeId);
        # Index from String(qid) to position in master_catalog for O(1)
        # cache-hit lookup (avoids linear search per cached qid).
        qid_to_pos := rec();
        for q_idx in [1..Length(master_qids)] do
            qid_to_pos.(SanitizeHidStr(String(master_qids[q_idx]))) := q_idx;
        od;
        for H in groups do
            idx := idx + 1;
            if Runtime() - last_qt_hb >= 60000 then
                Print("    [QuotientTypesOfGroups] progress ", idx, "/", n_total,
                      " types=", Length(result),
                      " H_iso=", Length(seen_h_ids),
                      " safe_dedup=", n_skipped,
                      " unsafe=", n_safe,
                      " cache_hit=", n_cache_hit,
                      " cache_miss=", n_cache_miss, "\n");
                last_qt_hb := Runtime();
            fi;
            h_id := SafeId(H);
            h_id_san := "";
            if h_id[2] = 0 then
                h_id_str := String(h_id);
                if h_id_str in seen_h_ids then
                    n_skipped := n_skipped + 1;
                    continue;
                fi;
                AddSet(seen_h_ids, h_id_str);
                h_id_san := SanitizeHidStr(h_id_str);
                # Opt 2: cache hit on H iso-class
                if h_to_qs <> fail and IsBound(h_to_qs.(h_id_san)) then
                    cached_qids := h_to_qs.(h_id_san);
                    n_cache_hit := n_cache_hit + 1;
                    for qid in cached_qids do
                        if qid in seen_qids then continue; fi;
                        AddSet(seen_qids, qid);
                        pos := 0;
                        if IsBound(qid_to_pos.(SanitizeHidStr(String(qid)))) then
                            pos := qid_to_pos.(SanitizeHidStr(String(qid)));
                        fi;
                        if pos > 0 then Add(result, master_catalog[pos]); fi;
                    od;
                    continue;
                fi;
                n_cache_miss := n_cache_miss + 1;
            else
                n_safe := n_safe + 1;
            fi;
            hit_qids := [];
            h_size := Size(H);
            for q_idx in [1..Length(master_catalog)] do
                q_size := Size(master_catalog[q_idx]);
                if q_size = 1 then continue; fi;              # legacy excludes K=H (trivial Q)
                if q_size > h_size then break; fi;            # ascending-order early exit
                if h_size mod q_size <> 0 then continue; fi;  # Lagrange divides filter
                qid := master_qids[q_idx];
                if HasQuotientType(H, master_catalog[q_idx]) then
                    Add(hit_qids, qid);
                    if not (qid in seen_qids) then
                        AddSet(seen_qids, qid);
                        Add(result, master_catalog[q_idx]);
                    fi;
                fi;
            od;
            # Opt 2: record this H's qid list for future runs (only if safe).
            # Update in-memory cache so subsequent QuotientTypesOfGroups calls
            # in this session hit the cache, and append to NEW list for the
            # next fragment write.
            if h_id[2] = 0 and h_to_qs <> fail then
                h_to_qs.(h_id_san) := hit_qids;
                Add(_META_H_TO_QS_NEW, [h_id_str, hit_qids]);
            fi;
            if Length(result) >= Length(master_catalog) then break; fi;
        od;
        Print("    [QuotientTypesOfGroups] catalog-driven done: ",
              Length(result), " types (subset of |catalog|=",
              Length(master_catalog), ")  cache_hit=", n_cache_hit,
              "  cache_miss=", n_cache_miss, "\n");
        return result;
    fi;

    # Legacy NormalSubgroups path (used when master_catalog not supplied).
    for H in groups do
        idx := idx + 1;
        if Runtime() - last_qt_hb >= 60000 then
            Print("    [QuotientTypesOfGroups] progress ", idx, "/", n_total,
                  " types_so_far=", Length(result),
                  " H_iso_classes_safe=", Length(seen_h_ids),
                  " H_safe_dedup=", n_skipped,
                  " H_unsafe_processed=", n_safe, "\n");
            last_qt_hb := Runtime();
        fi;
        h_id := SafeId(H);
        if h_id[2] = 0 then
            h_id_str := String(h_id);
            if h_id_str in seen_h_ids then
                n_skipped := n_skipped + 1;
                continue;
            fi;
            AddSet(seen_h_ids, h_id_str);
        else
            n_safe := n_safe + 1;
        fi;
        for K in NormalSubgroups(H) do
            if Size(K) = Size(H) then continue; fi;
            Q := H/K;
            qid := SafeId(Q);
            if not (qid in seen_qids) then
                AddSet(seen_qids, qid);
                Add(result, Q);
            fi;
        od;
    od;
    return result;
end;

ComputeOrLoadLeftQGroups := function(arg)
    # Three-lane Q-discovery for LEFT subgroups:
    #   Lane 1 (small): catalog-driven HasQuotientType sweep against
    #     META_Q_CATALOG (cap MAX_Q_SIZE; bounded per H iso-class).
    #   Lane 2 (forced-large): walk each right cache (already-built or
    #     loaded from prior runs); for each Q-iso of size > cap, run
    #     TargetedQuotientExists on left subgroups.  Per-Q early exit.
    #   Lane 3 (unknown-large promotion): for each order > cap dividing
    #     some |H_left| and not yet covered by lanes 1+2, enumerate
    #     SmallGroup(n, *) candidates and test via TargetedQuotientExists.
    #     FATAL if any order has too many SmallGroups (catalog must extend).
    #
    # Args:
    #   arg[1] = groups (LEFT subgroup list)
    #   arg[2] = qgroups_path (sidecar; "" disables persistence)
    #   arg[3] = master_catalog_path (lane 1 catalog; "" => legacy
    #            NormalSubgroups path -- DEPRECATED, may hang)
    #   arg[4] = right_cache_paths (list of paths; [] disables lane 2)
    #   arg[5] = h_to_qs_master_path (Opt 2 master cache; "" disables)
    #   arg[6] = h_to_qs_fragment_path (Opt 2 per-session fragment; "" disables)
    #   arg[7] = h_to_qs_fragments_dir (Opt 2 sibling fragments dir; "" disables)
    #
    # Validation: sidecar ends with `LEFT_Q_GROUPS_SAVED_OK := true;` sentinel.
    # If missing/false after Read, treat as corrupt and recompute.
    local groups, qgroups_path, master_catalog_path, right_cache_paths,
          h_to_qs_master_path, h_to_qs_fragment_path, h_to_qs_fragments_dir,
          h_to_qs, result, tmp, master_catalog, small_qgroups, forced_qrecs,
          forced_qrecs_dedup, seen_qid_strs, qr, key, forced_qgroups,
          covered_qids, promoted_qgroups, path, MANAGEABLE_THRESHOLD,
          QT_CAP;
    groups := arg[1];
    qgroups_path := arg[2];
    if Length(arg) >= 3 then master_catalog_path := arg[3]; else master_catalog_path := ""; fi;
    if Length(arg) >= 4 then right_cache_paths := arg[4]; else right_cache_paths := []; fi;
    if Length(arg) >= 5 then h_to_qs_master_path := arg[5]; else h_to_qs_master_path := ""; fi;
    if Length(arg) >= 6 then h_to_qs_fragment_path := arg[6]; else h_to_qs_fragment_path := ""; fi;
    if Length(arg) >= 7 then h_to_qs_fragments_dir := arg[7]; else h_to_qs_fragments_dir := ""; fi;

    QT_CAP := 200;
    MANAGEABLE_THRESHOLD := 1000;

    LEFT_Q_GROUPS_SAVED_OK := false;
    if qgroups_path <> "" and IsExistingFile(qgroups_path) then
        Read(qgroups_path);
        if IsBound(LEFT_Q_GROUPS_SAVED_OK) and LEFT_Q_GROUPS_SAVED_OK = true
           and IsBound(LEFT_Q_GROUPS) then
            Print("[QGroups] loaded from cache: ", Length(LEFT_Q_GROUPS),
                  " types from ", qgroups_path, "\n");
            return LEFT_Q_GROUPS;
        fi;
        Print("[QGroups] cache file present but invalid sentinel - recomputing\n");
    fi;

    # Opt 1: cached master-catalog load (skips disk re-read within session)
    master_catalog := _LoadMasterCatalog(master_catalog_path);
    # Opt 2: cached H-iso -> Q-iso lookup record (cross-super-batch)
    h_to_qs := _LoadHToQs(h_to_qs_master_path, h_to_qs_fragments_dir);

    # Lane 1: small-catalog discovery
    if master_catalog <> fail then
        small_qgroups := QuotientTypesOfGroups(groups, master_catalog, h_to_qs);
    else
        small_qgroups := QuotientTypesOfGroups(groups);
    fi;
    Print("[QGroups] lane 1 (small): ", Length(small_qgroups), " types\n");

    # Opt 2: persist new H-iso entries discovered during this lane-1 sweep.
    # Do NOT reset _META_H_TO_QS_NEW -- it accumulates across all calls in
    # this GAP session, and each save overwrites the fragment with the
    # cumulative new entries (write-once-per-session-end semantics).
    _SaveHToQsFragment(h_to_qs_fragment_path);

    # Lane 2: forced-large from right caches
    forced_qrecs := [];
    for path in right_cache_paths do
        Append(forced_qrecs, ForcedQRepsFromHCache(path, QT_CAP));
    od;
    # Dedup by qid string across all right caches.
    seen_qid_strs := Set([]);
    forced_qrecs_dedup := [];
    for qr in forced_qrecs do
        key := String(qr.qid);
        if key in seen_qid_strs then continue; fi;
        AddSet(seen_qid_strs, key);
        Add(forced_qrecs_dedup, qr);
    od;
    if Length(forced_qrecs_dedup) > 0 then
        Print("[QGroups] lane 2 (forced-large): ", Length(forced_qrecs_dedup),
              " unique Q-iso candidates from ", Length(right_cache_paths),
              " right cache(s)\n");
        forced_qgroups := ProcessForcedLargeQTypes(groups, forced_qrecs_dedup);
        Print("[QGroups] lane 2 (forced-large): ", Length(forced_qgroups),
              " types accepted\n");
    else
        forced_qgroups := [];
    fi;

    # Lane 3: unknown-large promotion
    covered_qids := Set(Concatenation(
        List(small_qgroups, SafeId),
        List(forced_qgroups, SafeId)));
    promoted_qgroups := PromoteUnknownLargeOrders(
        groups, covered_qids, QT_CAP, MANAGEABLE_THRESHOLD);
    if Length(promoted_qgroups) > 0 then
        Print("[QGroups] lane 3 (promoted): ", Length(promoted_qgroups),
              " types accepted\n");
    fi;

    result := Concatenation(small_qgroups, forced_qgroups, promoted_qgroups);
    Print("[QGroups] union: ", Length(result), " types\n");

    # Normalize for serialization: FactorGroup objects (H/K) print with
    # abstract generator names (f1, f2, ...) that aren't bound at re-Read
    # time, so PrintTo(file, factorgroup) writes unreadable code.
    result := List(result, function(q)
        local n, q_id;
        n := Size(q);
        if IdGroupsAvailable(n) then
            q_id := IdGroup(q);
            return SmallGroup(n, q_id[2]);
        else
            return Image(IsomorphismPermGroup(q));
        fi;
    end);
    if qgroups_path <> "" then
        tmp := Concatenation(qgroups_path, ".tmp");
        PrintTo(tmp, "LEFT_Q_GROUPS := ", result, ";\n",
                "LEFT_Q_GROUPS_SAVED_OK := true;\n");
        Exec(Concatenation("mv -f -- '", tmp, "' '", qgroups_path, "'"));
        Print("[QGroups] saved to cache: ", Length(result),
              " types -> ", qgroups_path, "\n");
    fi;
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
# --- Quotient-free 2-group small-quotient enumeration for {C_2, V_4, D_8} ---
# Profiling on |H|=1024 entries showed the BFS-then-classify approach spent
# 42-52% in H/K NaturalHom calls (3-5ms each x ~12k calls) and 32% in
# Index2-via-abelianization, total ~106-130s per entry.  The targets
# {C_2, V_4, D_8} are structurally specific enough that we can enumerate
# the kernels DIRECTLY without ever building H/K.

Index2SubgroupsViaAbelianization := function(M)
    local D, hom, A, maxs;
    D := DerivedSubgroup(M);
    if Size(D) = Size(M) then return []; fi;
    hom := NaturalHomomorphismByNormalSubgroup(M, D);
    A := Range(hom);
    maxs := Filtered(MaximalSubgroupClassReps(A), U -> Index(A, U) = 2);
    return Set(List(maxs, U -> PreImage(hom, U)));
end;

# N_L := [H,L] · L^p.  Every K with H/K a central-C_p extension of H/L
# must contain N_L (forces K normal in H, L/K central, L/K elem-ab of
# exponent p).  Specialized to p=2 for D_8 enumeration; general p is
# used by PGroupQuotientKernels for odd-prime Q.
RelativePhiSubgroup := function(H, L, p)
    local commHL, pgens, N;
    commHL := CommutatorSubgroup(H, L);
    pgens := List(GeneratorsOfGroup(L), x -> x^p);
    N := SubgroupNC(L, Concatenation(GeneratorsOfGroup(commHL),
                                     Filtered(pgens, x -> x <> ())));
    if not IsNormal(L, N) then N := NormalClosure(L, N); fi;
    return N;
end;

# D_8 kernel enumeration with two early-skip filters per V_4 layer L:
#  - if D = [H,H] ⊆ N_L, every K refining L is abelian (= no D_8 possible)
#  - if Index(L, N_L) ∈ {1, 2}, no hyperplane enumeration is needed
# Both filters cut directly into the per-layer cost dominating |H|=1024
# entries (651 layers, most "dead" or trivial-refinement).
D8KernelsFromV4Layer := function(H, v4s)
    local D, result, L, N, idxLN, hom, A, maxs, U, K, reps, x, sq_in_K;
    D := DerivedSubgroup(H);
    result := [];
    for L in v4s do
        N := RelativePhiSubgroup(H, L, 2);
        # If D ⊆ N then K ⊇ N ⊃ D forces H/K abelian.  Skip the layer.
        if IsSubset(N, D) then continue; fi;
        idxLN := Index(L, N);
        if idxLN = 1 then continue; fi;     # N = L, no refinement
        reps := Filtered(RightTransversal(H, L), x -> not (x in L));
        if idxLN = 2 then
            # Unique K = N at index 2 in L.  D ⊄ N already established.
            sq_in_K := false;
            for x in reps do
                if x^2 in N then sq_in_K := true; break; fi;
            od;
            if sq_in_K then AddSet(result, N); fi;
            continue;
        fi;
        # idxLN >= 4: enumerate index-2 subgroups of L containing N
        # via L/N's abelianization.  K's are automatically H-normal.
        hom := NaturalHomomorphismByNormalSubgroup(L, N);
        A := Range(hom);
        maxs := Filtered(MaximalSubgroupClassReps(A), U -> Index(A, U) = 2);
        for U in maxs do
            K := PreImage(hom, U);
            if IsSubset(K, D) then continue; fi;
            sq_in_K := false;
            for x in reps do
                if x^2 in K then sq_in_K := true; break; fi;
            od;
            if sq_in_K then AddSet(result, K); fi;
        od;
    od;
    return result;
end;

Small2QuotientKernels := function(H, q_groups)
    local has_C2, has_V4, has_D8, result, c2s, v4s, d8s, i, j, L,
          c2_qid, v4_qid, d8_qid;
    has_C2 := ForAny(q_groups, Q -> Size(Q) = 2);
    has_V4 := ForAny(q_groups, Q -> Size(Q) = 4 and not IsCyclic(Q));
    has_D8 := ForAny(q_groups, Q -> Size(Q) = 8 and not IsAbelian(Q));
    result := [];
    # SafeId hardcoded: C_2 = SmallGroup(2,1), V_4 = (4,2), D_8 = (8,3).
    c2_qid := [2, 0, [2, 1]];
    v4_qid := [4, 0, [4, 2]];
    d8_qid := [8, 0, [8, 3]];

    c2s := Index2SubgroupsViaAbelianization(H);
    if has_C2 then
        Append(result, List(c2s, K -> rec(K := K, qsize := 2, qid := c2_qid)));
    fi;

    v4s := [];
    if has_V4 or has_D8 then
        for i in [1..Length(c2s)] do
            for j in [i+1..Length(c2s)] do
                L := Intersection(c2s[i], c2s[j]);
                if Index(H, L) = 4 then AddSet(v4s, L); fi;
            od;
        od;
        if has_V4 then
            Append(result, List(v4s, K -> rec(K := K, qsize := 4, qid := v4_qid)));
        fi;
    fi;

    if has_D8 then
        d8s := D8KernelsFromV4Layer(H, v4s);
        Append(result, List(d8s, K -> rec(K := K, qsize := 8, qid := d8_qid)));
    fi;

    return result;
end;

# Generalizes Index2SubgroupsViaAbelianization to arbitrary prime p.
# Returns the index-p normal subgroups of M, computed via M / [M,M].
Index_p_SubgroupsViaAbelianization := function(M, p)
    local D, hom, A, maxs;
    D := DerivedSubgroup(M);
    if Size(D) = Size(M) then return []; fi;
    if (Size(M) / Size(D)) mod p <> 0 then return []; fi;
    hom := NaturalHomomorphismByNormalSubgroup(M, D);
    A := Range(hom);
    maxs := Filtered(MaximalSubgroupClassReps(A), U -> Index(A, U) = p);
    return Set(List(maxs, U -> PreImage(hom, U)));
end;

# PGroupQuotientKernels(H, Q): returns Set of K ⊆ H with H/K ≅ Q, when Q is
# a p-group.  Generalizes D8KernelsFromV4Layer: pick a central A ≤ Q with
# |A|=p, recurse on Q/A, then enumerate central C_p refinements via the
# [H,K0]·K0^p floor.  Returns `fail` for non-p-group Q.
#
# Correctness: every K with H/K ≅ Q and central A ⊴ Q lifts to K ⊆ K0 ⊆ H
# with H/K0 ≅ Q/A and K0/K ≅ A.  K0/K central in H/K forces [H,K0] ⊆ K, so
# K must contain NK0 := [H,K0]·K0^p.  Conversely, every index-p subgroup K
# of K0 containing NK0 is automatically H-normal AND gives K0/K central, so
# we filter only by SafeId(H/K) = SafeId(Q) (distinguishes D_8 from Q_8 etc).

# HasQuotientType(H, Q): cheap necessary-condition check for "H surjects onto Q".
# Returns false → no Q-quotient exists (sound, no kernels lost).
# Returns true → might have kernels; do full enumeration.
#
# For p-group Q, two structural checks:
#  (1) Abelianization compatibility — H/[H,H] must surject onto Q/[Q,Q].
#      Necessary because every quotient surjects on its abelianization.
#  (2) Derived-subgroup compatibility — for non-abelian Q (i.e. [Q,Q] = D_Q
#      non-trivial), [H,H] must have an H-equivariant elementary-abelian
#      p-quotient of rank >= rank(D_Q^ab).  The maximum such quotient is
#      D_H / Phi_H(D_H) where Phi_H(D_H) := [D_H,H]·D_H^p (relative Frattini
#      under the H-action).  If Phi_H(D_H) = D_H, no non-trivial elementary
#      abelian H-image of D_H exists, so no non-abelian Q-quotient exists.
#
# Cost: O(1 RelativePhiSubgroup call) ≈ 10-30ms.  Matches GQuotients' speed
# on the no-quotient-exists case.
HasQuotientType := function(H, Q)
    local primes, p, D_H, D_Q, A_inv_p, Q_ab_inv, Phi_DH,
          DQ_inv, phidh_rank, dq_rank;
    if Size(Q) = 1 then return true; fi;
    primes := Set(FactorsInt(Size(Q)));
    if Length(primes) <> 1 then return true; fi;  # not p-group; defer
    p := primes[1];
    D_H := DerivedSubgroup(H);
    if Size(D_H) = Size(H) then return false; fi;  # H perfect
    A_inv_p := Filtered(AbelianInvariants(H / D_H), x -> x mod p = 0);
    Q_ab_inv := AbelianInvariants(Q / DerivedSubgroup(Q));
    if Length(Q_ab_inv) > 0 then
        if Length(A_inv_p) < Length(Q_ab_inv) then return false; fi;
        if Maximum(A_inv_p) < Maximum(Q_ab_inv) then return false; fi;
    fi;
    D_Q := DerivedSubgroup(Q);
    if Size(D_Q) > 1 then
        if Size(D_H) < Size(D_Q) then return false; fi;
        Phi_DH := RelativePhiSubgroup(H, D_H, p);
        if Size(Phi_DH) = Size(D_H) then return false; fi;
        phidh_rank := LogInt(Size(D_H) / Size(Phi_DH), p);
        DQ_inv := AbelianInvariants(D_Q / DerivedSubgroup(D_Q));
        dq_rank := Length(Filtered(DQ_inv, x -> x mod p = 0));
        if phidh_rank < dq_rank then return false; fi;
    fi;
    return true;
end;

PPrimaryExponentsOfAbelianInvariants := function(inv, p)
    local exps, n, e;
    exps := [];
    for n in inv do
        e := 0;
        while n mod p = 0 do
            e := e + 1;
            n := n / p;
        od;
        if e > 0 then Add(exps, e); fi;
    od;
    Sort(exps);
    return Reversed(exps);
end;

AbelianInvariantsCanSurject := function(src_inv, dst_inv)
    local primes, n, p, src_e, dst_e, i;
    primes := Set([]);
    for n in dst_inv do
        for p in Set(FactorsInt(n)) do AddSet(primes, p); od;
    od;
    for p in primes do
        src_e := PPrimaryExponentsOfAbelianInvariants(src_inv, p);
        dst_e := PPrimaryExponentsOfAbelianInvariants(dst_inv, p);
        if Length(src_e) < Length(dst_e) then return false; fi;
        for i in [1..Length(dst_e)] do
            if src_e[i] < dst_e[i] then return false; fi;
        od;
    od;
    return true;
end;

CanSurjectOnAbelianization := function(A, Q)
    local DQ, q_ab_inv;
    DQ := DerivedSubgroup(Q);
    if Size(DQ) = Size(Q) then return true; fi;
    if A = fail then return false; fi;
    q_ab_inv := AbelianInvariants(Q / DQ);
    return AbelianInvariantsCanSurject(AbelianInvariants(A), q_ab_inv);
end;

DerivedSeriesOrderCompatibleFromDH := function(H, Q, DH)
    local Hcur, Qcur, nextH, nextQ, first;
    Hcur := H;
    Qcur := Q;
    first := true;
    while Size(Qcur) > 1 do
        if Size(Hcur) mod Size(Qcur) <> 0 then return false; fi;
        if Size(Hcur) = 1 then return false; fi;
        if first then
            nextH := DH;
            first := false;
        else
            nextH := DerivedSubgroup(Hcur);
        fi;
        nextQ := DerivedSubgroup(Qcur);
        if Size(nextQ) = Size(Qcur) then
            return Size(nextH) mod Size(Qcur) = 0;
        fi;
        Hcur := nextH;
        Qcur := nextQ;
    od;
    return true;
end;

CheapQuotientPossiblePrepared := function(H, Q, DH, A)
    if Size(H) mod Size(Q) <> 0 then return false; fi;
    if not CanSurjectOnAbelianization(A, Q) then return false; fi;
    if not DerivedSeriesOrderCompatibleFromDH(H, Q, DH) then return false; fi;
    return true;
end;

SameOrderQuotientKernelRecord := function(H, Q, q_qid)
    local h_id, iso;
    if Size(H) <> Size(Q) then return fail; fi;
    h_id := SafeId(H);
    if h_id[2] = 0 and q_qid[2] = 0 then
        if h_id = q_qid then
            return rec(K := TrivialSubgroup(H), qsize := Size(Q), qid := q_qid);
        fi;
        return false;
    fi;
    iso := IsomorphismGroups(H, Q);
    if iso <> fail then
        return rec(K := TrivialSubgroup(H), qsize := Size(Q), qid := q_qid);
    fi;
    return false;
end;

PrimeKernelQuotientRecords := function(H, Q, q_qid)
    local ksize, result, K;
    ksize := Size(H) / Size(Q);
    if not IsPrimeInt(ksize) then return fail; fi;
    result := [];
    for K in MinimalNormalSubgroups(H) do
        if Size(K) = ksize and SafeId(H / K) = q_qid then
            AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
        fi;
    od;
    return result;
end;

PGroupQuotientKernelsCached := function(H, Q, cache)
    local primes, p, A, hom_QQbar, Qbar, K0_recs, K0_rec, K0, NK0, hom, F,
          maxs, U, K, target_id, target_qsize, result, gens_A,
          p_kernels, key, idx;
    # Memoized PGroupQuotientKernels.  cache is rec(keys := [], vals := []).
    # Hits on shared Qbar (e.g., D_8/Z and Q_8/Z both reduce to V_4) avoid
    # recomputing K0_set across multiple Q-types in one _EnumerateNormalsForQGroups call.
    if Size(Q) = 1 then
        return [rec(K := H, qsize := 1, qid := [1, 0, [1, 1]])];
    fi;
    primes := Set(FactorsInt(Size(Q)));
    if Length(primes) <> 1 then return fail; fi;
    p := primes[1];
    target_id := SafeId(Q);
    target_qsize := Size(Q);
    key := target_id;
    idx := Position(cache.keys, key);
    if idx <> fail then return cache.vals[idx]; fi;
    if not HasQuotientType(H, Q) then
        Add(cache.keys, key); Add(cache.vals, []);
        return [];
    fi;
    if Size(Q) = p then
        p_kernels := Index_p_SubgroupsViaAbelianization(H, p);
        result := List(p_kernels,
                       K -> rec(K := K, qsize := target_qsize, qid := target_id));
        Add(cache.keys, key); Add(cache.vals, result);
        return result;
    fi;
    A := MinimalNormalSubgroups(Q)[1];
    if Size(A) > p then
        gens_A := GeneratorsOfGroup(A);
        A := SubgroupNC(Q, [gens_A[1]]);
    fi;
    hom_QQbar := NaturalHomomorphismByNormalSubgroup(Q, A);
    Qbar := Range(hom_QQbar);
    K0_recs := PGroupQuotientKernelsCached(H, Qbar, cache);
    if K0_recs = fail then return fail; fi;
    result := [];
    for K0_rec in K0_recs do
        K0 := K0_rec.K;
        NK0 := RelativePhiSubgroup(H, K0, p);
        if Index(K0, NK0) < p then continue; fi;
        if Index(K0, NK0) = p then
            if SafeId(H / NK0) = target_id then
                AddSet(result, rec(K := NK0, qsize := target_qsize, qid := target_id));
            fi;
            continue;
        fi;
        hom := NaturalHomomorphismByNormalSubgroup(K0, NK0);
        F := Range(hom);
        maxs := Filtered(MaximalSubgroupClassReps(F), U -> Index(F, U) = p);
        for U in maxs do
            K := PreImage(hom, U);
            if SafeId(H / K) = target_id then
                AddSet(result, rec(K := K, qsize := target_qsize, qid := target_id));
            fi;
        od;
    od;
    Add(cache.keys, key); Add(cache.vals, result);
    return result;
end;

PGroupQuotientKernels := function(H, Q)
    # Backward-compat wrapper: creates a fresh cache for a single call.  The
    # production path in _EnumerateNormalsForQGroups uses
    # PGroupQuotientKernelsCached directly with a cache shared across all
    # Q-types for a given H.
    return PGroupQuotientKernelsCached(H, Q, rec(keys := [], vals := []));
end;

NonAbelianSimpleQuotientKernelRecords := function(H, Q, q_qid)
    local result, K;
    if not (IsSimpleGroup(Q) and not IsAbelian(Q)) then return fail; fi;
    if Size(H) mod Size(Q) <> 0 then return []; fi;
    result := [];
    for K in MaximalNormalSubgroups(H) do
        if Size(H) / Size(K) = Size(Q) and SafeId(H / K) = q_qid then
            AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
        fi;
    od;
    return result;
end;

# Self-centralizing almost-simple quotient shortcut.
# If Q' is non-abelian simple and C_Q(Q') = 1, then for any epi H -> Q
# the kernel is the full preimage of C_{H/L}(H'/L), where L is the kernel
# of the induced simple quotient H' -> Q'.  This avoids enumerating every
# outer abelian quotient (e.g. all C2 quotients of S5 x 2^r).
AlmostSimpleQuotientKernelRecords := function(H, Q, q_qid)
    local DQ, CQ, DH, dq_id, simple_recs, result, L_rec, L,
          hom, Hbar, Dbar, Cbar, K;
    if IsSolvable(Q) then return fail; fi;
    DQ := DerivedSubgroup(Q);
    if not (IsSimpleGroup(DQ) and not IsAbelian(DQ)) then return fail; fi;
    CQ := Centralizer(Q, DQ);
    if Size(CQ) <> 1 then return fail; fi;
    DH := DerivedSubgroup(H);
    if Size(DH) mod Size(DQ) <> 0 then return []; fi;
    dq_id := SafeId(DQ);
    simple_recs := NonAbelianSimpleQuotientKernelRecords(DH, DQ, dq_id);
    if simple_recs = fail then return fail; fi;
    result := [];
    for L_rec in simple_recs do
        L := L_rec.K;
        if not IsNormal(H, L) then continue; fi;
        hom := NaturalHomomorphismByNormalSubgroup(H, L);
        Hbar := Range(hom);
        Dbar := Image(hom, DH);
        Cbar := Centralizer(Hbar, Dbar);
        if Size(Cbar) <> Size(Hbar) / Size(Q) then continue; fi;
        K := PreImage(hom, Cbar);
        if IsNormal(H, K) and SafeId(H / K) = q_qid then
            AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
        fi;
    od;
    return result;
end;

# Bounded direct exact path for small H or tiny kernel.  Enumerates
# NormalSubgroups(H) and filters to those whose index gives Q.  Much faster
# than recursive solvable-quotient enumeration when |H| is small enough that
# NormalSubgroups(H) is cheap, OR when the kernel is small enough that there
# are very few candidates.
SmallKernelQuotientKernelRecords := function(H, Q, q_qid)
    local ksize, result, K;
    if Size(H) mod Size(Q) <> 0 then return []; fi;
    ksize := Size(H) / Size(Q);
    # Thresholds tuned empirically (n=15 [12,3] benchmark): |H|=2304 with
    # ksize=16 hit a 66s SolvableQuotientKernelRecords ladder, so widen to
    # |H|<=4096 or ksize<=16.
    if not (Size(H) <= 4096 or ksize <= 16) then return fail; fi;
    result := [];
    for K in NormalSubgroups(H) do
        if Size(K) = ksize and SafeId(H / K) = q_qid then
            AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
        fi;
    od;
    return result;
end;

# Direct GQuotients(H, Q) wrapper for small mixed-solvable Q.  Used in place
# of recursive SolvableQuotientKernelRecords when |H| and |Q| are small
# enough that GAP's native quotient enumeration is the right tool.
DirectGQuotientsKernelRecords := function(H, Q, q_qid)
    local result, epi, K;
    result := [];
    for epi in GQuotients(H, Q) do
        K := Kernel(epi);
        AddSet(result, rec(K := K, qsize := Size(Q), qid := q_qid));
    od;
    return result;
end;

SolvableQuotientKernelRecords := function(H, Q, pg_cache)
    local sz, target_id, DH, hom, A, same_rec, prime_recs, p, max_subs,
          result, epi, pg_recs, max_normals, M, Qbar, K0_recs, K0_rec,
          K0, M_recs, K_rec, K, simple_recs, almost_recs, candidates,
          branch_result, branch_ok, handled;
    sz := Size(Q);
    target_id := SafeId(Q);
    if sz = 1 then
        return [rec(K := H, qsize := 1, qid := target_id)];
    fi;
    if Size(H) mod sz <> 0 then return []; fi;
    DH := DerivedSubgroup(H);
    if Size(DH) = Size(H) then
        hom := fail; A := fail;
    else
        hom := NaturalHomomorphismByNormalSubgroup(H, DH);
        A := Range(hom);
    fi;
    if not CheapQuotientPossiblePrepared(H, Q, DH, A) then return []; fi;
    same_rec := SameOrderQuotientKernelRecord(H, Q, target_id);
    if same_rec <> fail then
        if same_rec = false then return []; fi;
        return [same_rec];
    fi;
    prime_recs := PrimeKernelQuotientRecords(H, Q, target_id);
    if prime_recs <> fail then return prime_recs; fi;
    if IsPrimeInt(sz) then
        if A = fail then return []; fi;
        if Size(A) mod sz <> 0 then return []; fi;
        p := sz;
        max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = p);
        return List(max_subs,
            K -> rec(K := PreImage(hom, K), qsize := sz, qid := target_id));
    fi;
    if IsPGroup(Q) and sz <= 256 then
        pg_recs := PGroupQuotientKernelsCached(H, Q, pg_cache);
        if pg_recs <> fail then return pg_recs; fi;
    fi;
    if IsAbelian(Q) then
        if A = fail then return []; fi;
        result := [];
        for epi in GQuotients(A, Q) do
            Add(result, rec(K := PreImage(hom, Kernel(epi)),
                            qsize := sz, qid := target_id));
        od;
        return result;
    fi;
    almost_recs := AlmostSimpleQuotientKernelRecords(H, Q, target_id);
    if almost_recs <> fail then return almost_recs; fi;
    simple_recs := NonAbelianSimpleQuotientKernelRecords(H, Q, target_id);
    if simple_recs <> fail then return simple_recs; fi;
    max_normals := Filtered(MaximalNormalSubgroups(Q),
                            M -> Size(M) > 1 and Size(M) < Size(Q));
    if Length(max_normals) = 0 then return fail; fi;
    result := [];
    handled := false;
    if IsSolvable(Q) then candidates := [max_normals[1]];
    else candidates := max_normals; fi;
    for M in candidates do
        Qbar := Range(NaturalHomomorphismByNormalSubgroup(Q, M));
        K0_recs := SolvableQuotientKernelRecords(H, Qbar, pg_cache);
        if K0_recs = fail then continue; fi;
        branch_result := [];
        branch_ok := true;
        for K0_rec in K0_recs do
            K0 := K0_rec.K;
            M_recs := SolvableQuotientKernelRecords(K0, M, rec(keys := [], vals := []));
            if M_recs = fail then
                branch_ok := false;
                break;
            fi;
            for K_rec in M_recs do
                K := K_rec.K;
                if IsNormal(H, K) and SafeId(H / K) = target_id then
                    AddSet(branch_result, rec(K := K, qsize := sz, qid := target_id));
                fi;
            od;
        od;
        if branch_ok then
            handled := true;
            for K_rec in branch_result do AddSet(result, K_rec); od;
        fi;
    od;
    if handled then return result; fi;
    return fail;
end;

# ------------------------------------------------------------------
# Stage C: forced-large discovery from a trusted opposite-side H-cache.
# ------------------------------------------------------------------
#
# Given a concrete Q (typically extracted from the right cache), test
# whether some H_left actually surjects onto Q -- WITHOUT calling
# NormalSubgroups(H).  Returns true|false.
#
# Three branches:
#   1. p-group Q: use PGroupQuotientKernelsCached (bounded recursion).
#   2. abelian Q: lift via H/[H,H] = A and call GQuotients(A, Q) (cheap;
#      A is small).
#   3. non-abelian non-p-group Q: GQuotients(H, Q) directly.  Can be slow
#      for hostile H but is bounded per (H, Q) pair, unlike NormalSubgroups
#      which enumerates the entire normal lattice.
TargetedQuotientExists := function(H, Q, pg_cache)
    local sz, DH, hom, A, recs, q_qid, same_rec, prime_recs;
    sz := Size(Q);
    if sz = 1 then return true; fi;
    if Size(H) mod sz <> 0 then return false; fi;
    DH := DerivedSubgroup(H);
    if Size(DH) = Size(H) then
        hom := fail; A := fail;
    else
        hom := NaturalHomomorphismByNormalSubgroup(H, DH);
        A := Range(hom);
    fi;
    if not CheapQuotientPossiblePrepared(H, Q, DH, A) then return false; fi;
    q_qid := SafeId(Q);
    same_rec := SameOrderQuotientKernelRecord(H, Q, q_qid);
    if same_rec <> fail then return same_rec <> false; fi;
    prime_recs := PrimeKernelQuotientRecords(H, Q, q_qid);
    if prime_recs <> fail then return Length(prime_recs) > 0; fi;
    if IsPGroup(Q) then
        recs := PGroupQuotientKernelsCached(H, Q, pg_cache);
        if recs <> fail then return Length(recs) > 0; fi;
        # PGroupQuotientKernelsCached may return fail when its preconditions
        # aren't met; fall through to the abelian/general path below.
    fi;
    if IsAbelian(Q) then
        if A = fail then return false; fi;
        return Length(GQuotients(A, Q)) > 0;
    fi;
    recs := SolvableQuotientKernelRecords(H, Q, pg_cache);
    if recs <> fail then return Length(recs) > 0; fi;
    return Length(GQuotients(H, Q)) > 0;
end;

# Walk a previously-built right H-cache file and extract the set of distinct
# Q-iso-classes of size > cap as concrete group representatives.  Each entry
# carries: rec(Q, qsize, qid, source).  The qid[2]=0 case uses SmallGroup
# directly; the heuristic-fallback case (qid[2]=1) reconstructs Q := H/K
# and normalizes via IsomorphismPermGroup.
#
# Saves & restores any pre-existing global H_CACHE so this can run before
# the LEFT cache is loaded.
ForcedQRepsFromHCache := function(cache_path, cap)
    local out, seen, entry, orb, Q, key, saved_H_CACHE, right_cache, H, K;
    out := [];
    seen := Set([]);
    if cache_path = "" or not IsExistingFile(cache_path) then return out; fi;
    saved_H_CACHE := fail;
    if IsBound(H_CACHE) then
        saved_H_CACHE := H_CACHE;
        Unbind(H_CACHE);
    fi;
    Read(cache_path);
    if not IsBound(H_CACHE) or not IsList(H_CACHE) then
        if saved_H_CACHE <> fail then H_CACHE := saved_H_CACHE; fi;
        return out;
    fi;
    right_cache := H_CACHE;
    Unbind(H_CACHE);
    if saved_H_CACHE <> fail then H_CACHE := saved_H_CACHE; fi;
    for entry in right_cache do
        for orb in entry.orbits do
            if orb.qsize <= cap then continue; fi;
            key := String(orb.qid);
            if key in seen then continue; fi;
            AddSet(seen, key);
            if orb.qid[2] = 0 then
                Q := SmallGroup(orb.qid[3]);
            else
                # Fallback: reconstruct via H/K.  H from this right-cache entry.
                H := Group(entry.H_gens);
                K := Subgroup(H, orb.K_H_gens);
                Q := Image(IsomorphismPermGroup(
                    Range(NaturalHomomorphismByNormalSubgroup(H, K))));
            fi;
            Add(out, rec(Q := Q, qsize := orb.qsize, qid := orb.qid,
                        source := "right-cache"));
        od;
    od;
    return out;
end;

# Test each forced-large Q against LEFT subgroups via TargetedQuotientExists.
# Per-Q early exit on first H that succeeds (we only need to know membership
# in LEFT_Q_GROUPS, not enumerate all kernels here).
ProcessForcedLargeQTypes := function(left_groups, forced_qrecs)
    local result, qr, H, pg_cache, t_q;
    result := [];
    for qr in forced_qrecs do
        Print("    [forced-large] testing Q=[", qr.qsize, ",",
              qr.qid, "]\n");
        t_q := Runtime();
        for H in left_groups do
            if Size(H) mod qr.qsize <> 0 then continue; fi;
            pg_cache := rec(keys := [], vals := []);
            if TargetedQuotientExists(H, qr.Q, pg_cache) then
                Add(result, qr.Q);
                Print("    [forced-large] FOUND Q=[", qr.qsize, ",",
                      qr.qid, "] in |H|=", Size(H), " (",
                      Runtime() - t_q, "ms)\n");
                break;
            fi;
        od;
    od;
    return result;
end;

# Stage D: for each order n > cap appearing as a divisor of some |H_left|,
# enumerate all SmallGroup(n, *) candidates and test via
# TargetedQuotientExists.  FATAL if any required order has unmanageably
# many SmallGroups (in which case the catalog cap must be raised or a
# chunking strategy implemented).
PromoteUnknownLargeOrders := function(left_groups, covered_qids, cap, max_per_order)
    local left_orders, n, i, qrecs_to_test, covered_orders, candidate_Q,
          qid, H, d;
    qrecs_to_test := [];
    left_orders := Set([]);
    for H in left_groups do
        for d in DivisorsInt(Size(H)) do
            if d > cap then AddSet(left_orders, d); fi;
        od;
    od;
    covered_orders := Set(List(covered_qids, q -> q[1]));
    for n in left_orders do
        if not IdGroupsAvailable(n) then
            # SmallGroups database does not include this order (e.g., 2160).
            # Skip: the forced-large lane already covers any Q of this order
            # that actually appears on the right side, which is the only case
            # that contributes orbits under Goursat.
            Print("    [promote] WARNING: order ", n,
                  " has no SmallGroups database; skipping ",
                  "(forced-large lane covers right-side Q's).\n");
            continue;
        fi;
        if NumberSmallGroups(n) > max_per_order then
            Print("    [promote] WARNING: order ", n, " has ",
                  NumberSmallGroups(n),
                  " SmallGroups (> max_per_order=", max_per_order,
                  "); skipping (forced-large lane covers right-side Q's).\n");
            continue;
        fi;
        for i in [1..NumberSmallGroups(n)] do
            candidate_Q := SmallGroup(n, i);
            qid := SafeId(candidate_Q);
            if qid in covered_qids then continue; fi;
            Add(qrecs_to_test, rec(Q := candidate_Q, qsize := n, qid := qid,
                                    source := "promoted"));
        od;
    od;
    if Length(qrecs_to_test) = 0 then return []; fi;
    Print("    [promote] testing ", Length(qrecs_to_test),
          " unknown-large candidates across ", Length(left_orders),
          " orders > cap=", cap, "\n");
    return ProcessForcedLargeQTypes(left_groups, qrecs_to_test);
end;

_EnumerateNormalsForQGroups := function(H, q_groups)
    local q_size_H, DH, abel_hom, A, result, Q, sz, p, max_subs, epi,
          qids_set, all_normals, K, qid_K, t_q,
          h_is_2group, small_qs, other_qs, pg_kernels, q_qid, q_size,
          c2_qid, pg_cache, same_rec, prime_recs, solv_kernels,
          small_recs, direct_recs;
    # Returns a list of records: rec(K := <kernel>, qsize := |H/K|, qid := SafeId(H/K)).
    # qid is propagated from each enumeration branch so that the downstream
    # orbit construction (_ComputeOrbitRecsFromKs) can skip the per-orbit
    # NaturalHomomorphismByNormalSubgroup + SafeId reconstruction.
    #
    # As of Stage B (2026-05-08): never calls NormalSubgroups(H).  The legacy
    # `q_groups = fail` (full enumeration) and `use_direct` (max(|Q|)>200)
    # branches are removed -- callers must always pass a concrete Q list, and
    # large Q's are routed per-Q via the existing PGroupQuotientKernelsCached
    # / abelianization / GQuotients paths below.
    if q_groups = fail then
        Error("EnumerateNormalsForQGroups requires non-fail q_groups; ",
              "the legacy NormalSubgroups discovery path has been removed. ",
              "|H|=", Size(H));
    fi;
    if Length(q_groups) = 0 then return []; fi;
    h_is_2group := ForAll(FactorsInt(Size(H)), p -> p = 2);
    if h_is_2group then
        small_qs := Filtered(q_groups, Q ->
            Size(Q) = 2
            or (Size(Q) = 4 and not IsCyclic(Q))
            or (Size(Q) = 8 and not IsAbelian(Q) and IdGroup(Q) = [8, 3]));
    else
        small_qs := Filtered(q_groups, Q -> Size(Q) = 2);
    fi;
    other_qs := Filtered(q_groups, Q -> not (Q in small_qs));
    result := [];
    if Length(small_qs) > 0 then
        Print("    [enum/L0/small] BEGIN |H|=", Size(H),
              " n_small=", Length(small_qs), "\n");
        t_q := Runtime();
        if h_is_2group then
            Append(result, Small2QuotientKernels(H, small_qs));
        else
            c2_qid := [2, 0, [2, 1]];
            Append(result, List(Index2SubgroupsViaAbelianization(H),
                                K -> rec(K := K, qsize := 2, qid := c2_qid)));
        fi;
        Print("    [enum/L0/small] END   |H|=", Size(H),
              " -> ", Length(result), " kernels in ", Runtime() - t_q, "ms\n");
    fi;
    if Length(other_qs) = 0 then return result; fi;
    q_size_H := Size(H);
    DH := DerivedSubgroup(H);
    if Size(DH) = q_size_H then
        abel_hom := fail; A := fail;
    else
        abel_hom := NaturalHomomorphismByNormalSubgroup(H, DH);
        A := Range(abel_hom);
    fi;
    pg_cache := rec(keys := [], vals := []);   # shared across all Q in other_qs
    for Q in other_qs do
        sz := Size(Q);
        if q_size_H mod sz <> 0 then continue; fi;
        q_qid := SafeId(Q);
        q_size := sz;
        t_q := Runtime();
        if not CheapQuotientPossiblePrepared(H, Q, DH, A) then
            if Runtime() - t_q >= 100 then
                Print("    [enum/cheap_skip] |H|=", Size(H), " Q=", q_qid,
                      " in ", Runtime() - t_q, "ms\n");
            fi;
            continue;
        fi;
        same_rec := SameOrderQuotientKernelRecord(H, Q, q_qid);
        if same_rec <> fail then
            if same_rec <> false then Add(result, same_rec); fi;
            if Runtime() - t_q >= 100 then
                Print("    [enum/same_order] |H|=", Size(H), " Q=", q_qid,
                      " in ", Runtime() - t_q, "ms\n");
            fi;
            continue;
        fi;
        prime_recs := PrimeKernelQuotientRecords(H, Q, q_qid);
        if prime_recs <> fail then
            Append(result, prime_recs);
            if Runtime() - t_q >= 100 then
                Print("    [enum/prime_kernel] |H|=", Size(H), " Q=", q_qid,
                      " -> ", Length(prime_recs), " kernels in ",
                      Runtime() - t_q, "ms\n");
            fi;
            continue;
        fi;
        # Small-H or tiny-kernel direct path: NormalSubgroups(H) bounded.
        small_recs := SmallKernelQuotientKernelRecords(H, Q, q_qid);
        if small_recs <> fail then
            Append(result, small_recs);
            if Runtime() - t_q >= 100 then
                Print("    [enum/small_kernel] |H|=", Size(H), " Q=", q_qid,
                      " -> ", Length(small_recs), " kernels in ",
                      Runtime() - t_q, "ms\n");
            fi;
            continue;
        fi;
        if IsPrimeInt(sz) then
            if abel_hom = fail then continue; fi;
            if Size(A) mod sz <> 0 then continue; fi;
            p := sz;
            max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = p);
            Append(result, List(max_subs,
                K -> rec(K := PreImage(abel_hom, K), qsize := q_size, qid := q_qid)));
            if Runtime() - t_q >= 100 then
                Print("    [enum/prime_abel] |H|=", Size(H), " Q=", q_qid,
                      " -> ", Length(max_subs), " kernels in ",
                      Runtime() - t_q, "ms\n");
            fi;
        elif IsPGroup(Q) and sz <= 256 then
            # Level 1: p-group Q (abelian or non-abelian) via memoized
            # PGroupQuotientKernelsCached.  HasQuotientType inside that
            # function gives a cheap top-level feasibility check (O(1
            # RelativePhi call) ≈ 10-30ms) that matches GQuotients' speed
            # on the no-quotient case, so non-abelian Q is now safe to
            # route here even when many H entries don't admit such a
            # quotient.  Memoization (#3) shares K0_set across siblings.
            Print("    [enum/L1/pgroup] BEGIN |H|=", Size(H),
                  " Q=[", sz, ",", IdGroup(Q)[2], "]\n");
            t_q := Runtime();
            pg_kernels := PGroupQuotientKernelsCached(H, Q, pg_cache);
            if pg_kernels <> fail then
                Append(result, pg_kernels);
                Print("    [enum/L1/pgroup] END   |H|=", Size(H),
                      " Q=[", sz, ",", IdGroup(Q)[2], "] -> ",
                      Length(pg_kernels), " kernels in ",
                      Runtime() - t_q, "ms\n");
            else
                Print("    [enum/L1/pgroup] FALLBACK |H|=", Size(H),
                      " Q=[", sz, ",", IdGroup(Q)[2], "]\n");
                if abel_hom <> fail then
                    for epi in GQuotients(A, Q) do
                        Add(result, rec(K := PreImage(abel_hom, Kernel(epi)),
                                        qsize := q_size, qid := q_qid));
                    od;
                fi;
            fi;
        elif IsAbelian(Q) then
            if abel_hom = fail then continue; fi;
            for epi in GQuotients(A, Q) do
                Add(result, rec(K := PreImage(abel_hom, Kernel(epi)),
                                qsize := q_size, qid := q_qid));
            od;
            if Runtime() - t_q >= 100 then
                Print("    [enum/abelian] |H|=", Size(H), " Q=", q_qid,
                      " in ", Runtime() - t_q, "ms\n");
            fi;
        else
            # Small mixed-solvable Q: GQuotients(H, Q) is the right tool.
            # Avoids the recursive SolvableQuotientKernelRecords ladder that
            # can hit pathological cases (e.g. Q=SmallGroup(48,50) on
            # H=TG[12,90] taking 130s).
            if IsSolvable(Q) and not IsPGroup(Q) and not IsAbelian(Q)
               and Size(H) <= 4096 and Size(Q) <= 1024 then
                direct_recs := DirectGQuotientsKernelRecords(H, Q, q_qid);
                Append(result, direct_recs);
                if Runtime() - t_q >= 100 then
                    Print("    [enum/direct_gq] |H|=", Size(H), " Q=", q_qid,
                          " -> ", Length(direct_recs), " kernels in ",
                          Runtime() - t_q, "ms\n");
                fi;
                continue;
            fi;
            solv_kernels := SolvableQuotientKernelRecords(H, Q, pg_cache);
            if solv_kernels <> fail then
                Append(result, solv_kernels);
                if Runtime() - t_q >= 100 then
                    Print("    [enum/solvable] |H|=", Size(H), " Q=", q_qid,
                          " -> ", Length(solv_kernels), " kernels in ",
                          Runtime() - t_q, "ms\n");
                fi;
                continue;
            fi;
            Print("    [enum/fallback/GQuot] BEGIN |H|=", Size(H),
                  " Q=[", sz, ",", IdGroup(Q)[2], "]\n");
            Append(result, List(Set(List(GQuotients(H, Q), Kernel)),
                                K -> rec(K := K, qsize := q_size, qid := q_qid)));
            Print("    [enum/fallback/GQuot] END   |H|=", Size(H),
                  " Q=[", sz, ",", IdGroup(Q)[2], "] in ",
                  Runtime() - t_q, "ms\n");
        fi;
    od;
    return result;
end;

# Cut 3 dispatcher: splits q_groups into linear-supported and legacy.
# For supported qids (C_2, V_4, D_8), calls Stage A/B prototypes directly
# (produces orbit recs in the right format with K_H_gens + Stab_NH_KH_gens).
# Returns the LINEAR orbit-recs as a list; caller is responsible for running
# the legacy path on the remaining q_groups.
_LinearOrbitsForSupportedQids := function(H, N_H, q_groups)
    local supported_qids, orbits, legacy_qs, Q, qid, sz, recs;
    # Fail-safe: if USE_LINEAR_ORBITS isn't defined in this driver template
    # (only GAP_DRIVER has it currently), default to legacy.
    if not IsBound(USE_LINEAR_ORBITS) or USE_LINEAR_ORBITS <> 1 then
        return rec(linear := [], legacy := q_groups);
    fi;
    supported_qids := [[2,0,[2,1]], [4,0,[4,2]], [8,0,[8,3]]];
    orbits := [];
    legacy_qs := [];
    for Q in q_groups do
        qid := SafeId(Q);
        sz := Size(Q);
        if qid = [2,0,[2,1]] then
            Append(orbits, LinearOrbitRecsCpa(H, N_H, 2, 1));
        elif qid = [4,0,[4,2]] then
            Append(orbits, LinearOrbitRecsCpa(H, N_H, 2, 2));
        elif qid = [8,0,[8,3]] then
            Append(orbits, LinearOrbitRecsD8(H, N_H));
        else
            Add(legacy_qs, Q);
        fi;
    od;
    return rec(linear := orbits, legacy := legacy_qs);
end;


_ComputeOrbitRecsFromKs := function(H, N_H, k_recs)
    local kbyqid, qid_str, key, bucket, normals, K_orbit, K_H, Stab_NH_KH,
          orbits, kr, q_size_v, q_qid_v;
    # k_recs is a list of rec(K, qsize, qid).  Bucket by qid (kernels with
    # different qids cannot be N_H-conjugate), orbit per bucket, and skip
    # the per-orbit NaturalHomomorphismByNormalSubgroup + SafeId rebuild —
    # the qid is propagated from the enumeration step.
    orbits := [];
    kbyqid := rec();
    for kr in k_recs do
        qid_str := String(kr.qid);
        if not IsBound(kbyqid.(qid_str)) then
            kbyqid.(qid_str) := rec(qsize := kr.qsize, qid := kr.qid, recs := []);
        fi;
        Add(kbyqid.(qid_str).recs, kr);
    od;
    for key in RecNames(kbyqid) do
        bucket := kbyqid.(key);
        normals := List(bucket.recs, kr -> kr.K);
        q_size_v := bucket.qsize;
        q_qid_v := bucket.qid;
        for K_orbit in Orbits(N_H, normals, ConjAction) do
            K_H := K_orbit[1];
            Stab_NH_KH := Stabilizer(N_H, K_H, ConjAction);
            Add(orbits, rec(
                K_H_gens := GeneratorsOfGroup(K_H),
                Stab_NH_KH_gens := GeneratorsOfGroup(Stab_NH_KH),
                qsize := q_size_v,
                qid := q_qid_v
            ));
        od;
    od;
    return orbits;
end;

ComputeHCacheEntry := function(H, S_M, q_groups)
    local N_H, k_recs, t0, t_norm, t_enum, t_orbit, result_orbits;
    t0 := Runtime();
    N_H := Normalizer(S_M, H);
    t_norm := Runtime() - t0;
    t0 := Runtime();
    k_recs := _EnumerateNormalsForQGroups(H, q_groups);
    t_enum := Runtime() - t0;
    t0 := Runtime();
    result_orbits := _ComputeOrbitRecsFromKs(H, N_H, k_recs);
    t_orbit := Runtime() - t0;
    if t_norm + t_enum + t_orbit >= 1000 then
        Print("    [ComputeHCacheEntry] |H|=", Size(H),
              " norm=", t_norm, "ms enum=", t_enum,
              "ms orbit=", t_orbit, "ms (n_kernels=",
              Length(k_recs), ")\n");
    fi;
    return rec(
        H_gens := GeneratorsOfGroup(H),
        N_H_gens := GeneratorsOfGroup(N_H),
        computed_q_ids := QIdsOfGroups(q_groups),
        orbits := result_orbits
    );
end;

ComputeHDataDirect := function(H, S_M, q_groups)
    local N_H, k_recs, t0, t_norm, t_enum, t_orbit, res, hom_triv,
          kbyqid, kr, qid_str, key, bucket, normals, K_orbit, K_H,
          Stab, i;
    t0 := Runtime();
    N_H := Normalizer(S_M, H);
    t_norm := Runtime() - t0;
    t0 := Runtime();
    k_recs := _EnumerateNormalsForQGroups(H, q_groups);
    t_enum := Runtime() - t0;

    res := rec(H := H, N := N_H,
        H_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_H := fail, shifted_H_gens_noid := fail,
        orbits := []);
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N_H, AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
        K_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_K_gens_noid := fail, c2_rep := fail, shifted_c2_rep := fail,
        H_ref := H));

    t0 := Runtime();
    kbyqid := rec();
    for kr in k_recs do
        qid_str := String(kr.qid);
        if not IsBound(kbyqid.(qid_str)) then
            kbyqid.(qid_str) := rec(qsize := kr.qsize, qid := kr.qid, recs := []);
        fi;
        Add(kbyqid.(qid_str).recs, kr);
    od;
    for key in RecNames(kbyqid) do
        bucket := kbyqid.(key);
        normals := List(bucket.recs, kr -> kr.K);
        for K_orbit in Orbits(N_H, normals, ConjAction) do
            K_H := K_orbit[1];
            Stab := Stabilizer(N_H, K_H, ConjAction);
            Add(res.orbits, rec(K := K_H, hom := fail, Q := fail,
                qsize := bucket.qsize, qid := bucket.qid,
                Stab := Stab, AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
                K_gens_noid := Filtered(GeneratorsOfGroup(K_H), g -> g <> ()),
                shifted_K_gens_noid := fail, c2_rep := fail, shifted_c2_rep := fail,
                H_ref := H));
        od;
    od;
    res.byqid := rec();
    for i in [1..Length(res.orbits)] do
        key := String(res.orbits[i].qid);
        if not IsBound(res.byqid.(key)) then res.byqid.(key) := []; fi;
        Add(res.byqid.(key), i);
    od;
    t_orbit := Runtime() - t0;
    if t_norm + t_enum + t_orbit >= 1000 then
        Print("    [ComputeHDataDirect] |H|=", Size(H),
              " norm=", t_norm, "ms enum=", t_enum,
              "ms orbit=", t_orbit, "ms (n_kernels=",
              Length(k_recs), ")\n");
    fi;
    return res;
end;

ExtendHCacheEntry := function(entry, S_M, additional_q_groups)
    local H, N_H, current, missing_groups, k_recs, new_orbits, all_normals,
          K, qid_K, _linear_split, _linear_t0, _linear_t1;
    if entry.computed_q_ids = fail then return entry; fi;
    H := SafeGroup(entry.H_gens, S_M);
    N_H := SafeGroup(entry.N_H_gens, S_M);
    current := entry.computed_q_ids;
    if additional_q_groups = fail then
        # Extend to FULL coverage: enumerate ALL normals; add only the K's
        # whose quotient iso-class is not already in current.
        all_normals := Filtered(NormalSubgroups(H), K -> K <> H);
        k_recs := [];
        for K in all_normals do
            qid_K := SafeId(H/K);
            if not (qid_K in current) then
                Add(k_recs, rec(K := K, qsize := Size(H)/Size(K), qid := qid_K));
            fi;
        od;
        new_orbits := _ComputeOrbitRecsFromKs(H, N_H, k_recs);
        Append(entry.orbits, new_orbits);
        entry.computed_q_ids := fail;
        return entry;
    fi;
    missing_groups := QGroupsMissing(current, additional_q_groups);
    if Length(missing_groups) = 0 then return entry; fi;
    # Cut 3: route supported qids ({C_2, V_4, D_8}) through Stage A/B (linear
    # orbit math; orbit recs returned directly).  Remaining qids go through
    # the legacy enumerate-then-orbit path.  When USE_LINEAR_ORBITS=0, all
    # qids go to legacy (no behavior change).
    _linear_t0 := Runtime();
    _linear_split := _LinearOrbitsForSupportedQids(H, N_H, missing_groups);
    _linear_t1 := Runtime();
    if Length(_linear_split.linear) > 0 then
        Append(entry.orbits, _linear_split.linear);
    fi;
    if Length(_linear_split.legacy) > 0 then
        k_recs := _EnumerateNormalsForQGroups(H, _linear_split.legacy);
        new_orbits := _ComputeOrbitRecsFromKs(H, N_H, k_recs);
        Append(entry.orbits, new_orbits);
    fi;
    UniteSet(entry.computed_q_ids, QIdsOfGroups(missing_groups));
    if IsBound(USE_LINEAR_ORBITS) and USE_LINEAR_ORBITS = 1
       and (_linear_t1 - _linear_t0) >= 1000 then
        Print("    [cut3/linear] |H|=", Size(H),
              " n_orbits=", Length(_linear_split.linear),
              " time=", _linear_t1 - _linear_t0, "ms\n");
    fi;
    return entry;
end;

# File-level coverage tag: union of computed_q_ids across all H_CACHE
# entries.  An m_r=2 build only covers the q-types of TG(2,*) plus the
# subgroups thereof; an extension to m_r=3,4,... unions in extra qids.
# Saving compares this tag against the on-disk one and only overwrites if
# our in-memory cache covers at least as much as the file does.
ComputeCoverageTag := function(h_cache)
    local tag, e;
    tag := Set([]);
    for e in h_cache do
        # Treat unbound and the `fail` sentinel (set by ExtendHCacheEntry
        # when full coverage was requested) as full coverage.  UniteSet on
        # `fail` would crash GAP, killing the worker silently.
        if not IsBound(e.computed_q_ids) or e.computed_q_ids = fail then
            return fail;
        fi;
        UniteSet(tag, e.computed_q_ids);
    od;
    return tag;
end;

# Read just the first line of a cache file to extract its coverage tag.
# Format: "# coverage_qids: <set>;\n" (or "# coverage_qids: fail;\n" for
# full coverage).  Returns:
#   "missing" - file does not exist
#   "unknown" - file has no header (legacy file written before this opt)
#   fail      - file marked as full coverage
#   <list>    - parsed coverage tag (a Set of qids)
ReadCoverageTagFromFile := function(path)
    local f, line, prefix, payload, n;
    if not IsExistingFile(path) then return "missing"; fi;
    f := InputTextFile(path);
    if f = fail then return "missing"; fi;
    line := ReadLine(f);
    CloseStream(f);
    if line = fail then return "unknown"; fi;
    n := Length(line);
    while n > 0 and line[n] in [' ', '\n', '\r', '\t'] do n := n - 1; od;
    line := line{[1..n]};
    prefix := "# coverage_qids: ";
    if Length(line) < Length(prefix) then return "unknown"; fi;
    if line{[1..Length(prefix)]} <> prefix then return "unknown"; fi;
    payload := line{[Length(prefix)+1..Length(line)]};
    if Length(payload) >= 1 and payload[Length(payload)] = ';' then
        payload := payload{[1..Length(payload)-1]};
    fi;
    if payload = "fail" then return fail; fi;
    return EvalString(payload);
end;

SaveHCacheList := function(path, h_cache)
    local tmp, mem_tag, disk_tag, header, header_stream;
    # Coverage-tagged save: overwrite iff in-memory cache strictly extends
    # (or equals) the on-disk coverage.  Header line is parsed without
    # touching the body, so the check is cheap on multi-MB files.  Files
    # without a header (legacy) always trigger overwrite, which gives them
    # a header on first save.  IsValidCacheFile guards against skipping
    # when the on-disk file is corrupt: we'd otherwise refuse to overwrite
    # a truncated cache and leave readers crashing forever.
    mem_tag := ComputeCoverageTag(h_cache);
    disk_tag := ReadCoverageTagFromFile(path);
    if disk_tag = fail and IsValidCacheFile(path) then
        return;  # on-disk has full coverage and is intact
    fi;
    if disk_tag <> "missing" and disk_tag <> "unknown" and disk_tag <> fail
       and mem_tag <> fail and IsSubset(disk_tag, mem_tag)
       and not IsSubset(mem_tag, disk_tag)
       and IsValidCacheFile(path) then
        # disk_tag STRICTLY dominates mem_tag (disk has q-types we don't).
        # Equal tags are NOT a skip case: during EXTEND, individual entries
        # gain q-ids even when the cross-entry UNION is unchanged (because
        # some other entry already had that q-id).  Skipping the save in
        # that case loses the per-entry progress, so the next epoch loads
        # the same stale cache and re-runs the same slow entry forever.
        return;
    fi;
    if mem_tag = fail then
        header := "# coverage_qids: fail;\n";
    else
        header := Concatenation("# coverage_qids: ", String(mem_tag), ";\n");
    fi;
    # Atomic write: PrintTo to a unique .tmp file, then `mv` to final path.
    # Unique tmp prevents two GAP workers from clobbering each other's
    # PrintTo when racing on the same cache file.
    tmp := Concatenation(path, ".tmp.", String(Runtime()), ".",
                          String(Random([1..1000000])));
    # Header via WriteAll (verbatim, no auto-wrap).  PrintTo would wrap the
    # `# coverage_qids: ...` comment at SizeScreen() chars with backslash-
    # newline, but GAP comments don't honor `\` continuation -- the wrapped
    # comment turns into invalid code on the next line and crashes Read on
    # the next worker spawn.  Body uses default PrintTo wrapping, which is
    # fine since wrapping happens inside expressions (parses correctly).
    header_stream := OutputTextFile(tmp, false);
    WriteAll(header_stream, header);
    CloseStream(header_stream);
    AppendTo(tmp, "H_CACHE := ", h_cache, ";\n");
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

# ---- Checkpoint-restart support (opt 8 extension to super-batches) ----
# Long-running super-batches accumulate the same heap pressure as regular
# batches.  At end-of-group, if Runtime() - WORKER_START exceeds the
# checkpoint interval, persist the next-group index and quit.  Python
# relaunches GAP, which reads RESUME_SUPER and starts at that index.
# Per-job pair-loop is NOT checkpointed within super-batches: super-batches
# are pre-filtered to short LEFTs (heavy_left routes to dedicated batches),
# so a single group should fit comfortably within the checkpoint interval.
STATE_FILE := "__STATE_FILE__";
CHECKPOINT_INTERVAL_MS := __CHECKPOINT_INTERVAL_MS__;
STATE_SAVE_INTERVAL_MS := __STATE_SAVE_INTERVAL_MS__;
LAST_STATE_SAVE_MS := 0;
BENCH_PHASES   := __BENCH_PHASES__;
BENCH_PHASES_OUT := "__BENCH_PHASES_OUT__";
BENCH_T := rec(t_iso := 0, t_ensure := 0, t_a1a2 := 0, t_dc := 0, t_swap := 0,
               t_emit_qsize1 := 0, t_emit_c2_fast := 0, t_emit_c2_safe := 0,
               t_emit_general := 0, t_shifted_hom := 0,
               t_grp_construct := 0, t_emit_write := 0,
               t_c2safe_shifted_hom := 0, t_c2safe_gbfp := 0,
               t_c2safe_emit_write := 0);
BENCH_N := rec(n_pairs := 0, n_saturated := 0, n_dc_call := 0,
               n_dc_orbits_total := 0, n_emit := 0, n_c2_safe_invocations := 0,
               n_dc_cache_hits := 0, n_dc_cache_misses := 0);
# Opt #5 canonical-Q registry.  qid_str -> rec(Q := canonical_Q,
# AutQ := Aut(Qcan)).  Populated lazily by EnsureAutQ.
QCAN_TABLE := rec();
WORKER_START := Runtime();

RESUME_GROUP_IDX := 1;
RESUME_SUPER_BUILD_NEXT_HI := 0;   # 0 = no mid-build resume
RESUME_SUPER_JOB_IDX := 1;          # 1 = no between-job resume (fresh group)
RESUME_SUPER_PAIR_I := 1;           # 1 = no mid-pair resume
RESUME_SUPER_PAIR_J := 1;
RESUME_SUPER_TOTAL_ORB := 0;
RESUME_SUPER_TOTAL_FIX := 0;
RESUME_SUPER_FP_LINES := [];
if STATE_FILE <> "" and IsExistingFile(STATE_FILE) then
    Read(STATE_FILE);
    if IsBound(RESUME_SUPER) then
        RESUME_GROUP_IDX := RESUME_SUPER.next_group_idx;
        if IsBound(RESUME_SUPER.build_next_hi) then
            RESUME_SUPER_BUILD_NEXT_HI := RESUME_SUPER.build_next_hi;
            Print("CHECKPOINT_RESUME_SUPER starting at group ",
                  RESUME_GROUP_IDX, "/", Length(GROUPS),
                  " mid-build next_hi=", RESUME_SUPER_BUILD_NEXT_HI, "\n");
        elif IsBound(RESUME_SUPER.pair_i) then
            # Mid-pair resume: implies next_job_idx and per-job state.
            RESUME_SUPER_JOB_IDX := RESUME_SUPER.next_job_idx;
            RESUME_SUPER_PAIR_I := RESUME_SUPER.pair_i;
            RESUME_SUPER_PAIR_J := RESUME_SUPER.pair_j;
            RESUME_SUPER_TOTAL_ORB := RESUME_SUPER.total_orb;
            RESUME_SUPER_TOTAL_FIX := RESUME_SUPER.total_fix;
            RESUME_SUPER_FP_LINES := RESUME_SUPER.fp_lines;
            Print("CHECKPOINT_RESUME_SUPER starting at group ",
                  RESUME_GROUP_IDX, "/", Length(GROUPS),
                  " mid-pair job=", RESUME_SUPER_JOB_IDX,
                  " pair_i=", RESUME_SUPER_PAIR_I,
                  " pair_j=", RESUME_SUPER_PAIR_J,
                  " orb=", RESUME_SUPER_TOTAL_ORB, "\n");
        elif IsBound(RESUME_SUPER.next_job_idx) then
            RESUME_SUPER_JOB_IDX := RESUME_SUPER.next_job_idx;
            Print("CHECKPOINT_RESUME_SUPER starting at group ",
                  RESUME_GROUP_IDX, "/", Length(GROUPS),
                  " mid-jobs next_job_idx=", RESUME_SUPER_JOB_IDX, "\n");
        else
            Print("CHECKPOINT_RESUME_SUPER starting at group ",
                  RESUME_GROUP_IDX, "/", Length(GROUPS), "\n");
        fi;
    fi;
fi;

META_CATALOG_PATH := "__META_CATALOG__";
H_TO_QS_MASTER_PATH := "__H_TO_QS_MASTER__";
H_TO_QS_FRAGMENT_PATH := "__H_TO_QS_FRAGMENT__";
H_TO_QS_FRAGMENTS_DIR := "__H_TO_QS_FRAGMENTS_DIR__";

global_t0 := Runtime();

for group_idx in [RESUME_GROUP_IDX..Length(GROUPS)] do
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

    # Read LEFT subgroup list eagerly; it is always needed to build/load H_CACHE.
    Print("  [t+", Runtime() - group_t0, "ms] reading subs_left.g: ",
          SUBS_LEFT_PATH, "\n");
    Read(SUBS_LEFT_PATH);
    SUBGROUPS_LEFT_RAW := SUBGROUPS;
    Print("  [t+", Runtime() - group_t0, "ms] subs_left.g loaded: ",
          Length(SUBGROUPS_LEFT_RAW), " entries\n");

    RIGHT_Q_GROUPS := [];
    seen_qids := Set([]);
    # Per-job specific Q-discovery: see BATCH_DRIVER comment.
    seen_tg_keys := Set([]);
    seen_subs_paths := Set([]);
    for hi in [1..Length(GROUP.jobs)] do
        if GROUP.jobs[hi].right_tg_d > 0 then
            key := Concatenation(String(GROUP.jobs[hi].right_tg_d), ",",
                                 String(GROUP.jobs[hi].right_tg_t));
            if not (key in seen_tg_keys) then
                AddSet(seen_tg_keys, key);
                T_for_qg := TransitiveGroup(GROUP.jobs[hi].right_tg_d,
                                            GROUP.jobs[hi].right_tg_t);
                for K in NormalSubgroups(T_for_qg) do
                    if Size(K) = Size(T_for_qg) then continue; fi;
                    Q := T_for_qg/K;
                    qid := SafeId(Q);
                    if not (qid in seen_qids) then
                        AddSet(seen_qids, qid);
                        if IdGroupsAvailable(Size(Q)) then
                            Add(RIGHT_Q_GROUPS, SmallGroup(Size(Q), IdGroup(Q)[2]));
                        else
                            Add(RIGHT_Q_GROUPS, Image(IsomorphismPermGroup(Q)));
                        fi;
                    fi;
                od;
            fi;
        fi;
        if GROUP.jobs[hi].subs_right <> "" and
           not (GROUP.jobs[hi].subs_right in seen_subs_paths) then
            AddSet(seen_subs_paths, GROUP.jobs[hi].subs_right);
            for Q in LoadOrComputeRightQGroupsFromSubs(
                    GROUP.jobs[hi].subs_right, GROUP.jobs[hi].cache_right) do
                qid := SafeId(Q);
                if not (qid in seen_qids) then
                    AddSet(seen_qids, qid);
                    Add(RIGHT_Q_GROUPS, Q);
                fi;
            od;
        fi;
    od;

    if Length(RIGHT_Q_GROUPS) = 0 then
        LEFT_Q_GROUPS := ComputeOrLoadLeftQGroups(
            SUBGROUPS_LEFT_RAW,
            Concatenation(CACHE_LEFT_PATH, ".qgroups.g"),
            META_CATALOG_PATH,
            Filtered(DuplicateFreeList(List(GROUP.jobs, j -> j.cache_right)),
                     p -> p <> ""),
            H_TO_QS_MASTER_PATH,
            H_TO_QS_FRAGMENT_PATH,
            H_TO_QS_FRAGMENTS_DIR);
        Print("  [t+", Runtime() - group_t0, "ms] LEFT-derived Q-groups: ",
              Length(LEFT_Q_GROUPS), " types, max |Q|=",
              Maximum(Concatenation([0], List(LEFT_Q_GROUPS, Size))), "\n");
    else
        LEFT_Q_GROUPS := RIGHT_Q_GROUPS;
        Print("  [t+", Runtime() - group_t0, "ms] RIGHT-bounded Q-groups: ",
              Length(LEFT_Q_GROUPS), " types, max |Q|=",
              Maximum(Concatenation([0], List(LEFT_Q_GROUPS, Size))), "\n");
    fi;

    # ---- Load LEFT side for this group ----
    # IS_BUILD_RESUME: this group was mid-build when a previous epoch
    # checkpointed.  The on-disk cache is PARTIAL; fall through to BUILD,
    # not EXTEND.
    IS_BUILD_RESUME := group_idx = RESUME_GROUP_IDX
                       and RESUME_SUPER_BUILD_NEXT_HI > 0;
    H_CACHE := fail;
    if CACHE_LEFT_PATH <> "" and IsValidCacheFile(CACHE_LEFT_PATH) then
        if IS_BUILD_RESUME then
            Print("  [t+", Runtime() - group_t0,
                  "ms] reading PARTIAL H_CACHE from disk (resuming build at ",
                  RESUME_SUPER_BUILD_NEXT_HI, "): ", CACHE_LEFT_PATH, "\n");
        else
            Print("  [t+", Runtime() - group_t0, "ms] reading H_CACHE from disk: ",
                  CACHE_LEFT_PATH, "\n");
        fi;
        Read(CACHE_LEFT_PATH);
        Print("  [t+", Runtime() - group_t0, "ms] H_CACHE read complete: ",
              Length(H_CACHE), " entries\n");
    fi;
    if H_CACHE <> fail and not IS_BUILD_RESUME then
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
            last_hb := Runtime();
            last_hb_count := 0;
            for hi in [1..Length(H_CACHE)] do
                missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
                if hi = 1 or hi - last_hb_count >= 500
                   or Runtime() - last_hb >= 60000 then
                    if missing = fail then
                        Print("    [t+", Runtime() - group_t0,
                              "ms] H_CACHE EXTEND ", hi, "/", Length(H_CACHE),
                              " n_missing=fail\n");
                    else
                        Print("    [t+", Runtime() - group_t0,
                              "ms] H_CACHE EXTEND ", hi, "/", Length(H_CACHE),
                              " n_missing=", Length(missing), "\n");
                    fi;
                    last_hb := Runtime();
                    last_hb_count := hi;
                fi;
                if missing = fail then
                    ExtendHCacheEntry(H_CACHE[hi], W_ML, LEFT_Q_GROUPS);
                elif Length(missing) > 0 then
                    ExtendHCacheEntry(H_CACHE[hi], W_ML, missing);
                fi;
                # Per-entry extend checkpoint: like BATCH_DRIVER, write a
                # placeholder state.g (no extra fields needed; on resume the
                # extend-needed loop re-derives missing entries from
                # computed_q_ids).
                # Soft state save (no exit) every STATE_SAVE_INTERVAL_MS.
                if STATE_FILE <> "" and STATE_SAVE_INTERVAL_MS > 0
                   and Runtime() - LAST_STATE_SAVE_MS >= STATE_SAVE_INTERVAL_MS
                   and hi < Length(H_CACHE)
                   and CACHE_LEFT_PATH <> "" then
                    SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
                    tmp := Concatenation(STATE_FILE, ".tmp");
                    PrintTo(tmp, "RESUME_SUPER := rec( next_group_idx := ",
                            group_idx, " );\n");
                    Exec(Concatenation("mv -f -- '", tmp, "' '",
                                       STATE_FILE, "'"));
                    LAST_STATE_SAVE_MS := Runtime();
                    Print("[soft_checkpoint] SUPER_EXTEND group=", group_idx,
                          " done_until=", hi, "/", Length(H_CACHE),
                          " elapsed_ms=", Runtime() - WORKER_START, "\n");
                fi;
                if STATE_FILE <> "" and CHECKPOINT_INTERVAL_MS > 0
                   and Runtime() - WORKER_START >= CHECKPOINT_INTERVAL_MS
                   and hi < Length(H_CACHE)
                   and CACHE_LEFT_PATH <> "" then
                    SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
                    tmp := Concatenation(STATE_FILE, ".tmp");
                    PrintTo(tmp, "RESUME_SUPER := rec( next_group_idx := ",
                            group_idx, " );\n");
                    Exec(Concatenation("mv -f -- '", tmp, "' '",
                                       STATE_FILE, "'"));
                    Print("CHECKPOINT_PAUSE_SUPER_EXTEND group=", group_idx,
                          " done_until=", hi, "/", Length(H_CACHE),
                          " elapsed_ms=", Runtime() - WORKER_START, "\n");
                    LogTo();
                    QuitGap();
                fi;
            od;
            if CACHE_LEFT_PATH <> "" then
                SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
            fi;
            Print("  [t+", Runtime() - group_t0, "ms] extension done\n");
        fi;
    fi;
    if H_CACHE = fail or IS_BUILD_RESUME then
        # SUBGROUPS_LEFT_RAW already loaded above for Q-type derivation.
        if H_CACHE = fail then
            Print("  [t+", Runtime() - group_t0, "ms] no cache; building from scratch\n");
            H_CACHE := [];
            BUILD_START_HI := 1;
        else
            BUILD_START_HI := RESUME_SUPER_BUILD_NEXT_HI;
        fi;
        Print("  [t+", Runtime() - group_t0, "ms] computing H_CACHE for ",
              Length(SUBGROUPS_LEFT_RAW), " subgroups (in W_ML)",
              " from entry ", BUILD_START_HI, "...\n");
        last_hb := Runtime();
        last_hb_count := 0;
        for hi in [BUILD_START_HI..Length(SUBGROUPS_LEFT_RAW)] do
            if hi = BUILD_START_HI or hi - last_hb_count >= 500
               or Runtime() - last_hb >= 60000 then
                Print("    [t+", Runtime() - group_t0, "ms] H_CACHE starting ",
                      hi, "/", Length(SUBGROUPS_LEFT_RAW),
                      " |H|=", Size(SUBGROUPS_LEFT_RAW[hi]), "\n");
                last_hb := Runtime();
                last_hb_count := hi;
            fi;
            Add(H_CACHE, ComputeHCacheEntry(SUBGROUPS_LEFT_RAW[hi], W_ML, LEFT_Q_GROUPS));
            # Per-entry build checkpoint: save partial cache + state.g with
            # group_idx + build_next_hi so the next epoch resumes here.
            # Soft state save (no exit) every STATE_SAVE_INTERVAL_MS.
            if STATE_FILE <> "" and STATE_SAVE_INTERVAL_MS > 0
               and Runtime() - LAST_STATE_SAVE_MS >= STATE_SAVE_INTERVAL_MS
               and hi < Length(SUBGROUPS_LEFT_RAW)
               and CACHE_LEFT_PATH <> "" then
                SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
                tmp := Concatenation(STATE_FILE, ".tmp");
                PrintTo(tmp, "RESUME_SUPER := rec( next_group_idx := ",
                        group_idx, ", build_next_hi := ", hi + 1, " );\n");
                Exec(Concatenation("mv -f -- '", tmp, "' '",
                                   STATE_FILE, "'"));
                LAST_STATE_SAVE_MS := Runtime();
                Print("[soft_checkpoint] SUPER_BUILD group=", group_idx,
                      " next_hi=", hi + 1, "/", Length(SUBGROUPS_LEFT_RAW),
                      " elapsed_ms=", Runtime() - WORKER_START, "\n");
            fi;
            if STATE_FILE <> "" and CHECKPOINT_INTERVAL_MS > 0
               and Runtime() - WORKER_START >= CHECKPOINT_INTERVAL_MS
               and hi < Length(SUBGROUPS_LEFT_RAW)
               and CACHE_LEFT_PATH <> "" then
                SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
                tmp := Concatenation(STATE_FILE, ".tmp");
                PrintTo(tmp, "RESUME_SUPER := rec( next_group_idx := ",
                        group_idx, ", build_next_hi := ", hi + 1, " );\n");
                Exec(Concatenation("mv -f -- '", tmp, "' '",
                                   STATE_FILE, "'"));
                Print("CHECKPOINT_PAUSE_SUPER_BUILD group=", group_idx,
                      " next_hi=", hi + 1, "/", Length(SUBGROUPS_LEFT_RAW),
                      " elapsed_ms=", Runtime() - WORKER_START, "\n");
                LogTo();
                QuitGap();
            fi;
        od;
        Print("  [t+", Runtime() - group_t0, "ms] H_CACHE compute done\n");
        if CACHE_LEFT_PATH <> "" then
            Print("  [t+", Runtime() - group_t0, "ms] writing H_CACHE to ",
                  CACHE_LEFT_PATH, "\n");
            SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
            Print("  [t+", Runtime() - group_t0, "ms] H_CACHE write done\n");
        fi;
        # Build done — clear the build-resume flag so subsequent groups
        # (or end-of-group) start cleanly.  Do NOT remove state.g here:
        # end-of-group checkpoint will rewrite it if needed.
        if IS_BUILD_RESUME then
            RESUME_SUPER_BUILD_NEXT_HI := 0;
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

    # If resuming mid-jobs in this exact group, start at the saved job index;
    # otherwise (any subsequent group, or no resume) start at 1.
    if group_idx = RESUME_GROUP_IDX and RESUME_SUPER_JOB_IDX > 1 then
        JOB_START_IDX := RESUME_SUPER_JOB_IDX;
    else
        JOB_START_IDX := 1;
    fi;

    # Per-job loop (same as BATCH_DRIVER's body)
    for job_idx in [JOB_START_IDX..Length(JOBS)] do
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

        H2DATA := fail;
        if JOB.right_tg_d > 0 then
            T_orig_j := TransitiveGroup(JOB.right_tg_d, JOB.right_tg_t);
            H2DATA := [ComputeHDataDirect(T_orig_j, S_MR, LEFT_Q_GROUPS)];
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
                            ExtendHCacheEntry(H_CACHE[hi], S_MR, LEFT_Q_GROUPS);
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
        if H2DATA = fail then
            Print("    [t+", Runtime() - job_t0, "ms] H_CACHE_R loaded (",
                  Length(H_CACHE_R), " entries), reconstructing...\n");
            H2DATA := List(H_CACHE_R, e -> ReconstructHData(e, S_MR));
            Print("    [t+", Runtime() - job_t0, "ms] ReconstructHData done\n");
        fi;

        # ---- Goursat counting + emission ----
        # In burnside_m2: emit only canonical (h2idx >= h1_orb_idx) iterations
        # so each unordered orbit-pair is emitted once.  No post-hoc swap-dedup.
        # Honor mid-pair resume only for the exact (group, job) we paused in.
        if group_idx = RESUME_GROUP_IDX and job_idx = RESUME_SUPER_JOB_IDX
           and (RESUME_SUPER_PAIR_I > 1 or RESUME_SUPER_PAIR_J > 1) then
            fp_lines := RESUME_SUPER_FP_LINES;
            i_resume_start := RESUME_SUPER_PAIR_I;
            j_resume_start := RESUME_SUPER_PAIR_J;
            resume_total_orb := RESUME_SUPER_TOTAL_ORB;
            resume_total_fix := RESUME_SUPER_TOTAL_FIX;
        else
            fp_lines := [];
            i_resume_start := 1;
            j_resume_start := 1;
            resume_total_orb := 0;
            resume_total_fix := 0;
        fi;

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

        EmitGenList := function(gens)
            local s;
            if Length(gens) > 0 then
                s := JoinStringsWithSeparator(List(gens, String), ",");
            else
                s := "";
            fi;
            Add(fp_lines, Concatenation("[", s, "]"));
        end;

        FiberProductGeneratorList := function(H1data, h1orb, h2orb, phi)
            local gens, g, img_q, preimg, gen, n;
            gens := [];
            for g in GeneratorsOfGroup(h1orb.H_ref) do
                img_q := Image(phi, Image(h1orb.hom, g));
                preimg := PreImagesRepresentative(h2orb.shifted_hom, img_q);
                gen := g * preimg;
                if gen <> () then Add(gens, gen); fi;
            od;
            for n in GeneratorsOfGroup(Kernel(h2orb.shifted_hom)) do
                if n <> () then Add(gens, n); fi;
            od;
            return gens;
        end;

        ProcessPairBatch := function(H1data, H2data, H1, H2)
            local total, swap_fixed, h1orb, h2idxs, h2idx, h2orb, key, isoTH,
                  isos, n, gensQ, KeyOf, idx, seen, n_orb, queue, j, phi,
                  alpha, beta, neighbor, nkey, k, fp, orbit_id, i, swap_phi,
                  swap_key, swap_iso_idx, swap_orbit_id,
                  h1_orb_idx, orbit_reps_phi, h_0, t_0, swap_orb_id_arr,
                  gens_for_fp,
                  dcs, A1, A2_in_h1, A2_in_h1_gens, tinv, g_swap,
          bench_t0, bench_t1, h2_shifted_hom;
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
                                EmitGenList(Concatenation(H1data.H_gens_noid,
                                                          H2data.shifted_H_gens_noid));
                            fi;
                            if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                                swap_fixed := swap_fixed + 1;
                            fi;
                        fi;
                    od;
                    continue;
                fi;

                if h1orb.qsize = 2 then
                    # Use the direct C_2 shortcut only when the RIGHT factor is
                    # literally degree 2.  For MR>2, keep the C_2 orbit shortcut
                    # but build the subgroup through the quotient homomorphisms.
                    if MR = 2 then
                        for h2idx in h2idxs do
                            h2orb := H2data.orbits[h2idx];
                            if h2orb.qsize <> 2 then continue; fi;
                            total := total + 1;
                            if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                                EnsureC2Representative(h1orb);
                                EnsureShiftedKGenerators(h2orb);
                                EnsureShiftedC2Representative(h2orb);
                                EmitGenList(Concatenation(
                                    h1orb.K_gens_noid,
                                    h2orb.shifted_K_gens_noid,
                                    [h1orb.c2_rep * h2orb.shifted_c2_rep]));
                            fi;
                            if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                                swap_fixed := swap_fixed + 1;
                            fi;
                        od;
                    else
                        for h2idx in h2idxs do
                            h2orb := H2data.orbits[h2idx];
                            if h2orb.qsize <> 2 then continue; fi;
                            total := total + 1;
                            if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                                EnsureHom(h1orb); EnsureHom(h2orb);
                                isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
                                if isoTH <> fail then
                                    EnsureShiftedHom(h2orb, H2);
                                    fp := _GoursatBuildFiberProduct(
                                        H1, H2, h1orb.hom,
                                        h2orb.shifted_hom,
                                        InverseGeneralMapping(isoTH),
                                        [1..ML], [ML+1..ML+MR]);
                                    if fp <> fail then EmitGen(fp); fi;
                                fi;
                            fi;
                            if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                                swap_fixed := swap_fixed + 1;
                            fi;
                        od;
                    fi;
                    continue;
                fi;

                for h2idx in h2idxs do
                    h2orb := H2data.orbits[h2idx];
                    if h2orb.qsize <> h1orb.qsize then continue; fi;
                    EnsureHom(h1orb); EnsureHom(h2orb);
                    EnsureShiftedHom(h2orb, H2);
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
                        if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                A1 := SafeSub(h1orb.AutQ, h1orb.A_gens);
                        # Use InducedAutomorphism to transport b to Aut(h1.Q).
                        # Opt #5: A_gens already in canonical Aut(Q); skip isoTH transport.
                        A2_in_h1 := SafeSub(h1orb.AutQ, h2orb.A_gens);
                        dcs := LookupOrComputeDC(h1orb, A1, A2_in_h1);
                        n_orb := Length(dcs);
                        orbit_reps_phi := List(dcs, dc ->
                    h2orb.iso_to_can * Representative(dc) * InverseGeneralMapping(h1orb.iso_to_can));
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
                            gens_for_fp := FiberProductGeneratorList(
                                H1data, h1orb, h2orb,
                                InverseGeneralMapping(orbit_reps_phi[i]));
                            EmitGenList(gens_for_fp);
                        od;
                    elif BURNSIDE_M2 = 1 and h2idx = h1_orb_idx then
                        # Self-pair: within-pair canonical (i <= swap_orb_id[i]).
                        for i in [1..n_orb] do
                            if swap_orb_id_arr[i] >= i then
                                gens_for_fp := FiberProductGeneratorList(
                                    H1data, h1orb, h2orb,
                                    InverseGeneralMapping(orbit_reps_phi[i]));
                                EmitGenList(gens_for_fp);
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

        TOTAL_ORB := resume_total_orb;
        TOTAL_FIX := resume_total_fix;
        last_hb_ms := Runtime() - job_t0;
        n_pairs_done := 0;
        n_pairs_total := Length(H1DATA_LIST) * Length(H2DATA);
        Print("    [t+", Runtime() - job_t0, "ms] starting H1xH2 loop: ",
              Length(H1DATA_LIST), " x ", Length(H2DATA),
              " = ", n_pairs_total, " pairs\n");
        # Optimization (4) 2026-04-28: precompute shifted RIGHT once per j.
        if BURNSIDE_M2 = 0 then
            for H2data_j in H2DATA do EnsureShiftedHData(H2data_j); od;
            H2_SHIFTED := List(H2DATA, hd -> hd.shifted_H);
        fi;
        for i in [i_resume_start..Length(H1DATA_LIST)] do
            H1data_j := H1DATA_LIST[i];
            H1_j := H1data_j.H;
            if BURNSIDE_M2 = 1 then H2DATA[1] := H1data_j; fi;
            j_lo := 1;
            if i = i_resume_start then j_lo := j_resume_start; fi;
            for j in [j_lo..Length(H2DATA)] do
                H2data_j := H2DATA[j];
                if BURNSIDE_M2 = 0 then
                    H2_j := H2_SHIFTED[j];
                else
                    EnsureShiftedHData(H2data_j);
                    H2_j := H2data_j.shifted_H;
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
                # Soft state save (no exit) every STATE_SAVE_INTERVAL_MS.
                # Caps work loss from unplanned crashes (OOM etc.) — without
                # this, the only state save is at CHECKPOINT_INTERVAL_MS (2h),
                # so a mid-epoch crash loses up to 2h of pair work.
                if STATE_FILE <> "" and STATE_SAVE_INTERVAL_MS > 0
                   and Runtime() - LAST_STATE_SAVE_MS >= STATE_SAVE_INTERVAL_MS
                   and (j < Length(H2DATA) or i < Length(H1DATA_LIST)) then
                    next_i := i;
                    next_j := j + 1;
                    if next_j > Length(H2DATA) then
                        next_i := i + 1;
                        next_j := 1;
                    fi;
                    tmp := Concatenation(STATE_FILE, ".tmp");
                    PrintTo(tmp, "RESUME_SUPER := rec(\n",
                        "  next_group_idx := ", group_idx, ",\n",
                        "  next_job_idx := ", job_idx, ",\n",
                        "  pair_i := ", next_i, ",\n",
                        "  pair_j := ", next_j, ",\n",
                        "  total_orb := ", TOTAL_ORB, ",\n",
                        "  total_fix := ", TOTAL_FIX, ",\n",
                        "  fp_lines := ", fp_lines, "\n",
                        ");\n");
                    Exec(Concatenation("mv -f -- '", tmp, "' '",
                                       STATE_FILE, "'"));
                    LAST_STATE_SAVE_MS := Runtime();
                    Print("[soft_checkpoint] SUPER_PAIR group=", group_idx,
                          " job=", job_idx,
                          " pair_i=", next_i, "/", Length(H1DATA_LIST),
                          " pair_j=", next_j,
                          " orb=", TOTAL_ORB,
                          " elapsed_ms=", Runtime() - WORKER_START, "\n");
                fi;
                # Per-pair checkpoint: bound heap to ~30 min of pair work even
                # within a single long JOB (closes the n_left small / pair-spike
                # pathology in SUPER too).
                if STATE_FILE <> "" and CHECKPOINT_INTERVAL_MS > 0
                   and Runtime() - WORKER_START >= CHECKPOINT_INTERVAL_MS
                   and (j < Length(H2DATA) or i < Length(H1DATA_LIST)) then
                    next_i := i;
                    next_j := j + 1;
                    if next_j > Length(H2DATA) then
                        next_i := i + 1;
                        next_j := 1;
                    fi;
                    tmp := Concatenation(STATE_FILE, ".tmp");
                    PrintTo(tmp, "RESUME_SUPER := rec(\n",
                        "  next_group_idx := ", group_idx, ",\n",
                        "  next_job_idx := ", job_idx, ",\n",
                        "  pair_i := ", next_i, ",\n",
                        "  pair_j := ", next_j, ",\n",
                        "  total_orb := ", TOTAL_ORB, ",\n",
                        "  total_fix := ", TOTAL_FIX, ",\n",
                        "  fp_lines := ", fp_lines, "\n",
                        ");\n");
                    Exec(Concatenation("mv -f -- '", tmp, "' '",
                                       STATE_FILE, "'"));
                    Print("CHECKPOINT_PAUSE_SUPER_PAIR group=", group_idx,
                          " job=", job_idx,
                          " next_pair_i=", next_i,
                          " next_pair_j=", next_j,
                          " orb=", TOTAL_ORB,
                          " elapsed_ms=", Runtime() - WORKER_START, "\n");
                    LogTo();
                    QuitGap();
                fi;
            od;
        od;

        if BURNSIDE_M2 = 1 then PREDICTED := (TOTAL_ORB + TOTAL_FIX) / 2;
        else PREDICTED := TOTAL_ORB; fi;
        elapsed_ms := Runtime() - job_t0;

        # Atomic per-combo write (see notes in BATCH_DRIVER above).
        # Stream-based for speed.
        TMP_OUT := Concatenation(OUTPUT_PATH, ".tmp");
        OUT_STREAM := OutputTextFile(TMP_OUT, false);
        SetPrintFormattingStatus(OUT_STREAM, false);
        WriteAll(OUT_STREAM, Concatenation(COMBO_HEADER, "\n"));
        WriteAll(OUT_STREAM, Concatenation("# candidates: ", String(PREDICTED), "\n"));
        WriteAll(OUT_STREAM, Concatenation("# deduped: ", String(PREDICTED), "\n"));
        WriteAll(OUT_STREAM, Concatenation("# elapsed_ms: ", String(elapsed_ms), "\n"));
        for line in fp_lines do
            WriteAll(OUT_STREAM, Concatenation(line, "\n"));
        od;
        CloseStream(OUT_STREAM);
        Exec(Concatenation("mv -f -- '", TMP_OUT, "' '", OUTPUT_PATH, "'"));

        Print("RESULT group=", group_idx, " job=", job_idx,
              " predicted=", PREDICTED, " orbits=", TOTAL_ORB,
              " swap_fixed=", TOTAL_FIX, " elapsed_ms=", elapsed_ms, "\n");

        # Between-JOB checkpoint: bound heap to one JOB's worth.  Pair-loop
        # checkpoint can't fire when n_left = 1 or 2, so this is the only
        # in-group heap reset for those cases.
        if STATE_FILE <> "" and CHECKPOINT_INTERVAL_MS > 0
           and Runtime() - WORKER_START >= CHECKPOINT_INTERVAL_MS
           and job_idx < Length(JOBS) then
            tmp := Concatenation(STATE_FILE, ".tmp");
            PrintTo(tmp, "RESUME_SUPER := rec( next_group_idx := ",
                    group_idx, ", next_job_idx := ", job_idx + 1, " );\n");
            Exec(Concatenation("mv -f -- '", tmp, "' '",
                               STATE_FILE, "'"));
            Print("CHECKPOINT_PAUSE_SUPER_JOB group=", group_idx,
                  " end_of_job=", job_idx,
                  " next_job_idx=", job_idx + 1, "/", Length(JOBS),
                  " elapsed_ms=", Runtime() - WORKER_START, "\n");
            LogTo();
            QuitGap();
        fi;
    od;

    Print("GROUP ", group_idx, " done in ", Runtime() - group_t0, "ms\n");

    # End-of-group checkpoint: if elapsed >= interval and there are more
    # groups, save state.g and quit.  Python relaunches with the new
    # group index.
    if STATE_FILE <> "" and CHECKPOINT_INTERVAL_MS > 0
       and Runtime() - WORKER_START >= CHECKPOINT_INTERVAL_MS
       and group_idx < Length(GROUPS) then
        tmp := Concatenation(STATE_FILE, ".tmp");
        PrintTo(tmp, "RESUME_SUPER := rec( next_group_idx := ",
                group_idx + 1, " );\n");
        Exec(Concatenation("mv -f -- '", tmp, "' '", STATE_FILE, "'"));
        Print("CHECKPOINT_PAUSE_SUPER next_group_idx=", group_idx + 1,
              "/", Length(GROUPS),
              " elapsed_ms=", Runtime() - WORKER_START, "\n");
        LogTo();
        QuitGap();
    fi;
od;

# All groups done — clear state.g if it exists from a prior epoch's checkpoint.
if STATE_FILE <> "" and IsExistingFile(STATE_FILE) then
    RemoveFile(STATE_FILE);
fi;

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
                "output_path": to_gap(Path(job["output_path"])),
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
                rec["subs_right"] = to_gap(subs_r_g)
                rec["cache_right"] = to_gap(cr)
            job_records.append(rec)
            flat_jobs.append({"combo": combo_filename(job["combo"]),
                              "mode": job["mode"]})

        gap_groups.append({
            "m_left": sum(d for d, _ in left_combo),
            "m_left_partition": partition_from_source(left_combo),
            "left_combo_str": combo_filename(left_combo),
            "subs_left": to_gap(subs_l_g),
            "cache_left": to_gap(cache_l),
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
    state_g = work_root / "state.g"
    # Note: do NOT delete state_g here — if it exists from a prior killed run,
    # we want to resume from it.  GAP removes it cleanly when all groups done.
    chkpt_ms = int(os.environ.get("CHECKPOINT_INTERVAL_MS", "7200000"))
    state_save_ms = int(os.environ.get("STATE_SAVE_INTERVAL_MS", "1800000"))
    bench_phases = int(os.environ.get("BENCH_PHASES", "0"))
    bench_phases_out = work_root / "bench_phases.txt" if bench_phases else None
    h_to_qs_master = to_gap(H_TO_QS_MASTER_PATH) if H_TO_QS_MASTER_PATH.parent.exists() else ""
    h_to_qs_fragment = to_gap(H_TO_QS_FRAGMENTS_DIR / f"{work_root.name}.g") if H_TO_QS_MASTER_PATH.parent.exists() else ""
    h_to_qs_dir = to_gap(H_TO_QS_FRAGMENTS_DIR) if H_TO_QS_MASTER_PATH.parent.exists() else ""
    if H_TO_QS_MASTER_PATH.parent.exists():
        H_TO_QS_FRAGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    run_g.write_text(
        SUPER_BATCH_DRIVER
        .replace("__LOG__", to_gap(log))
        .replace("__LIFTING_G__", to_gap(LIFTING_G))
        .replace("__USE_LINEAR_ORBITS__",
                 "0" if os.environ.get("PRED_USE_LINEAR_ORBITS") == "0" else "1")
        .replace("__STATE_FILE__", to_gap(state_g))
        .replace("__CHECKPOINT_INTERVAL_MS__", str(chkpt_ms))
        .replace("__STATE_SAVE_INTERVAL_MS__", str(state_save_ms))
        .replace("__META_CATALOG__", to_gap(META_CATALOG_PATH) if META_CATALOG_PATH.exists() else "")
        .replace("__H_TO_QS_MASTER__", h_to_qs_master)
        .replace("__H_TO_QS_FRAGMENT__", h_to_qs_fragment)
        .replace("__H_TO_QS_FRAGMENTS_DIR__", h_to_qs_dir)
        .replace("__BENCH_PHASES__", str(bench_phases))
        .replace("__BENCH_PHASES_OUT__", to_gap(bench_phases_out) if bench_phases_out else "")
        .replace("__GROUPS_ARRAY__", groups_array),
        encoding="utf-8"
    )

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 -L "{LIFTING_WS_CYG}" "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    # Checkpoint-restart loop (mirror of predict_batch).  GAP self-monitors
    # elapsed time and exits with a state.g when it crosses the threshold;
    # we re-invoke GAP, which reads RESUME_SUPER and continues from the
    # next group.  Loop exits when GAP completes all groups (state.g
    # removed by GAP itself).
    epoch = 0
    # GAP's LogTo() truncates on each epoch's startup, so RESULT lines
    # from previous epochs' completed groups would be wiped.  Preserve
    # each epoch's log in a separate file so the final scan sees every
    # group's RESULTs.
    preserved_log = work_root / "super_preserved.log"
    if preserved_log.exists():
        preserved_log.unlink()
    try:
        while True:
            epoch += 1
            _gap_run(cmd, env, timeout, diag_dir=work_root)
            if log.exists():
                with preserved_log.open("ab") as p, log.open("rb") as l:
                    p.write(l.read())
            if not state_g.exists():
                break
            # Use stderr — stdout is reserved for the JSON results that the
            # build_sn_topt orchestrator parses with json.loads().  A stray
            # text line before the JSON would break parsing.
            print(f"  [resume] {work_root.name} epoch={epoch} state.g present, re-invoking GAP", file=sys.stderr, flush=True)
    except subprocess.TimeoutExpired:
        return [{"error": "super_batch timeout"} for _ in flat_jobs]
    elapsed_total = round(time.time() - t0, 1)

    log_text = preserved_log.read_text(encoding="utf-8", errors="ignore") if preserved_log.exists() else ""
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
            "output_path": to_gap(out_path),
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
            record["subs_right"] = to_gap(subs_r_g)
            record["cache_right"] = to_gap(cr)
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
    state_g = work_root / "state.g"
    # Note: do NOT delete state_g here — if it exists from a prior killed run,
    # we want to resume from it.  GAP will remove it cleanly when all jobs done.
    left_part = partition_from_source(left_combo)
    # Restart interval: 120 min default (CHECKPOINT_INTERVAL_MS); 0 disables.
    # Soft state-save interval: 30 min default (STATE_SAVE_INTERVAL_MS); 0 disables.
    # In EXTEND/BUILD phases, soft saves persist partial cache + state.g without
    # exiting; restart fires only at CHECKPOINT_INTERVAL_MS.  Emit phase already
    # writes state.g after every pair, so STATE_SAVE_INTERVAL_MS is a no-op there.
    chkpt_ms = int(os.environ.get("CHECKPOINT_INTERVAL_MS", "7200000"))
    state_save_ms = int(os.environ.get("STATE_SAVE_INTERVAL_MS", "1800000"))
    bench_phases = int(os.environ.get("BENCH_PHASES", "0"))
    bench_phases_out = work_root / "bench_phases.txt" if bench_phases else None
    h_to_qs_master = to_gap(H_TO_QS_MASTER_PATH) if H_TO_QS_MASTER_PATH.parent.exists() else ""
    h_to_qs_fragment = to_gap(H_TO_QS_FRAGMENTS_DIR / f"{work_root.name}.g") if H_TO_QS_MASTER_PATH.parent.exists() else ""
    h_to_qs_dir = to_gap(H_TO_QS_FRAGMENTS_DIR) if H_TO_QS_MASTER_PATH.parent.exists() else ""
    if H_TO_QS_MASTER_PATH.parent.exists():
        H_TO_QS_FRAGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    run_g.write_text(
        BATCH_DRIVER
        .replace("__LOG__", to_gap(log))
        .replace("__LIFTING_G__", to_gap(LIFTING_G))
        .replace("__USE_LINEAR_ORBITS__",
                 "0" if os.environ.get("PRED_USE_LINEAR_ORBITS") == "0" else "1")
        .replace("__M_LEFT__", str(first_inputs["m_left"]))
        .replace("__M_LEFT_PARTITION__", "[" + ",".join(str(d) for d in left_part) + "]")
        .replace("__SUBS_L__", to_gap(subs_l_g))
        .replace("__CACHE_L__", to_gap(cache_l))
        .replace("__STATE_FILE__", to_gap(state_g))
        .replace("__CHECKPOINT_INTERVAL_MS__", str(chkpt_ms))
        .replace("__STATE_SAVE_INTERVAL_MS__", str(state_save_ms))
        .replace("__META_CATALOG__", to_gap(META_CATALOG_PATH) if META_CATALOG_PATH.exists() else "")
        .replace("__H_TO_QS_MASTER__", h_to_qs_master)
        .replace("__H_TO_QS_FRAGMENT__", h_to_qs_fragment)
        .replace("__H_TO_QS_FRAGMENTS_DIR__", h_to_qs_dir)
        .replace("__BENCH_PHASES__", str(bench_phases))
        .replace("__BENCH_PHASES_OUT__", to_gap(bench_phases_out) if bench_phases_out else "")
        .replace("__JOBS_ARRAY__", jobs_array),
        encoding="utf-8"
    )

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 -L "{LIFTING_WS_CYG}" "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    # Opt 8: checkpoint-restart loop.  GAP self-monitors elapsed time and
    # exits with a state file when it crosses CHECKPOINT_INTERVAL_MS.  We
    # detect the state file's presence and re-invoke GAP, which reads the
    # state on startup and resumes the pair loop.  When all jobs complete,
    # GAP removes the state file, so the loop exits.
    #
    # GAP's LogTo() truncates the log on each new epoch's startup, so
    # RESULT lines from already-completed jobs would be wiped after a
    # checkpoint.  Concatenate each epoch's log into a preserved file
    # so the final RESULT-line scan sees every job's record.
    preserved_log = work_root / "batch_preserved.log"
    if preserved_log.exists():
        preserved_log.unlink()
    epoch = 0
    try:
        while True:
            epoch += 1
            _gap_run(cmd, env, timeout, diag_dir=work_root)
            if log.exists():
                with preserved_log.open("ab") as p, log.open("rb") as l:
                    p.write(l.read())
            if not state_g.exists():
                break
            # Use stderr — stdout is reserved for the JSON results that the
            # build_sn_topt orchestrator parses with json.loads().  A stray
            # text line before the JSON would break parsing.
            print(f"  [resume] {work_root.name} epoch={epoch} state.g present, re-invoking GAP", file=sys.stderr, flush=True)
    except subprocess.TimeoutExpired:
        return [{"error": "batch timeout", "elapsed_s": time.time() - t0}] * len(jobs)
    elapsed_total = round(time.time() - t0, 1)

    # Parse RESULT lines from preserved log (covers all epochs).
    log_text = preserved_log.read_text(encoding="utf-8", errors="ignore") if preserved_log.exists() else ""
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
    joined_lines = [
        line for line in _join_gap_continuations(raw_gens_lines)
        if line.startswith("[")
    ]
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
            force=False, timeout=3600, extend_only=False):
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

    # Checkpoint state file (shared with checkpoint-aware GAP_DRIVER).  Its
    # presence after GAP exits indicates "GAP checkpointed; relaunch and resume".
    state_g = work / "state.g"

    # Resume-aware fps.g handling: if state.g exists and gen_path exists, scan
    # gen_path for the last "# checkpoint i=K j=L" marker and truncate to right
    # after it.  GAP will read state.g, get (next_i, next_j), and resume.  If
    # NEITHER state.g exists NOR markers found, treat as fresh start.
    if gen_path is not None:
        if state_g.exists() and gen_path.exists():
            # Truncate fps.g to the byte position right after the last "#
            # checkpoint" marker line.  This guarantees fps.g ends at a clean
            # pair boundary (no half-emitted pair from a crash).
            data = gen_path.read_bytes()
            last_marker = data.rfind(b"# checkpoint ")
            if last_marker >= 0:
                # Find end of that line (the \n after the marker).
                end_of_marker_line = data.find(b"\n", last_marker)
                if end_of_marker_line >= 0:
                    truncate_to = end_of_marker_line + 1
                    if truncate_to < len(data):
                        with gen_path.open("r+b") as f:
                            f.truncate(truncate_to)
            # If no marker found, fall through to fresh-start truncation below.
        elif gen_path.exists():
            # No state.g — fresh start; remove any stale fps.g.
            gen_path.unlink()
    # Fresh-start state cleanup.
    if not state_g.exists() and gen_path is not None and gen_path.exists():
        # state.g absent + fps.g present means we crashed without checkpoint;
        # truncate to last marker if any (above), else start fresh.
        pass

    left_part = partition_from_source(inputs["left_combo"])
    if inputs["right_tg"] is not None:
        right_part = [inputs["right_tg"][0]]
    elif inputs["right_combo"] is not None:
        right_part = partition_from_source(inputs["right_combo"])
    else:
        right_part = [inputs["m_right"]]

    chkpt_ms = int(os.environ.get("CHECKPOINT_INTERVAL_MS", "7200000"))
    state_save_ms = int(os.environ.get("STATE_SAVE_INTERVAL_MS", "1800000"))
    bench_phases = int(os.environ.get("BENCH_PHASES", "0"))
    bench_phases_out = work / "bench_phases.txt" if bench_phases else None
    if H_TO_QS_MASTER_PATH.parent.exists():
        H_TO_QS_FRAGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    run_g = work / "run.g"
    run_g.write_text(
        GAP_DRIVER
        .replace("__LOG__", to_gap(log))
        .replace("__LIFTING_G__", to_gap(LIFTING_G))
        .replace("__M_LEFT__", str(inputs["m_left"]))
        .replace("__M_RIGHT__", str(inputs["m_right"]))
        .replace("__M_LEFT_PARTITION__", "[" + ",".join(str(d) for d in left_part) + "]")
        .replace("__M_RIGHT_PARTITION__", "[" + ",".join(str(d) for d in right_part) + "]")
        .replace("__SUBS_L__", to_gap(subs_l_g))
        .replace("__SUBS_R__", to_gap(subs_r_g) if sr else "")
        .replace("__CACHE_L__", to_gap(cache_l))
        .replace("__CACHE_R__", to_gap(cache_r) if cache_r else "")
        .replace("__TG_D__", str(inputs["right_tg"][0]) if inputs["right_tg"] else "0")
        .replace("__TG_T__", str(inputs["right_tg"][1]) if inputs["right_tg"] else "0")
        .replace("__BURNSIDE_M2__", "1" if inputs["burnside_m2"] else "0")
        .replace("__GEN_PATH__", to_gap(gen_path) if gen_path else "")
        .replace("__STATE_FILE__", to_gap(state_g))
        .replace("__CHECKPOINT_INTERVAL_MS__", str(chkpt_ms))
        .replace("__STATE_SAVE_INTERVAL_MS__", str(state_save_ms))
        .replace("__EXTEND_ONLY__", "1" if extend_only else "0")
        .replace("__USE_LINEAR_ORBITS__",
                 "0" if os.environ.get("PRED_USE_LINEAR_ORBITS") == "0" else "1")
        .replace("__META_CATALOG__", to_gap(META_CATALOG_PATH) if META_CATALOG_PATH.exists() else "")
        .replace("__H_TO_QS_MASTER__", to_gap(H_TO_QS_MASTER_PATH) if H_TO_QS_MASTER_PATH.parent.exists() else "")
        .replace("__H_TO_QS_FRAGMENT__", to_gap(H_TO_QS_FRAGMENTS_DIR / f"{work.name}.g") if H_TO_QS_MASTER_PATH.parent.exists() else "")
        .replace("__H_TO_QS_FRAGMENTS_DIR__", to_gap(H_TO_QS_FRAGMENTS_DIR) if H_TO_QS_MASTER_PATH.parent.exists() else "")
        .replace("__BENCH_PHASES__", str(bench_phases))
        .replace("__BENCH_PHASES_OUT__", to_gap(bench_phases_out) if bench_phases_out else ""),
        encoding="utf-8"
    )

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 -L "{LIFTING_WS_CYG}" "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    # Checkpoint-restart loop.  GAP self-monitors elapsed time and exits with
    # state.g still present when it crosses CHECKPOINT_INTERVAL_MS.  We detect
    # state.g and re-invoke GAP, which reads state.g + the fps.g (Python
    # truncated to last "# checkpoint" marker) and resumes from (i, j+1).  GAP
    # removes state.g on full completion, which is how this loop exits.
    preserved_log = work / "run_preserved.log"
    if preserved_log.exists():
        preserved_log.unlink()
    epoch = 0
    try:
        while True:
            epoch += 1
            _gap_run(cmd, env, timeout, diag_dir=work)
            if log.exists():
                with preserved_log.open("ab") as p, log.open("rb") as l:
                    p.write(l.read())
            if not state_g.exists():
                break
            # Resume: scan fps.g for last marker, truncate, re-launch.
            if gen_path is not None and gen_path.exists():
                data = gen_path.read_bytes()
                last_marker = data.rfind(b"# checkpoint ")
                if last_marker >= 0:
                    end_of_marker_line = data.find(b"\n", last_marker)
                    if end_of_marker_line >= 0:
                        truncate_to = end_of_marker_line + 1
                        if truncate_to < len(data):
                            with gen_path.open("r+b") as f:
                                f.truncate(truncate_to)
            print(f"  [resume] {target_str} epoch={epoch} state.g present, "
                  f"re-invoking GAP", file=sys.stderr, flush=True)
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "elapsed_s": time.time() - t0}
    elapsed = round(time.time() - t0, 1)
    log_text = (preserved_log.read_text(encoding="utf-8", errors="ignore")
                if preserved_log.exists() else
                (log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""))
    if extend_only:
        # Extend-only mode: GAP exits after cache save (no RESULT line, no fps.g).
        # Verify the [extend_only] marker is present so we know it ran the
        # extension path and didn't error out earlier.
        if "[extend_only]" not in log_text:
            return {"error": "extend_only ran but [extend_only] marker missing",
                    "log_tail": log_text[-2000:], "elapsed_s": elapsed}
        return {"combo": combo_filename(combo), "mode": mode,
                "extend_only": True, "elapsed_s": elapsed,
                "left_combo": combo_filename(inputs["left_combo"]),
                "right": (f"TG({inputs['right_tg'][0]},{inputs['right_tg'][1]})"
                          if inputs["right_tg"] else combo_filename(inputs["right_combo"]))}
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
    ap.add_argument("--extend-only", action="store_true",
                    help="run cache extension+save then exit, no emit; "
                         "use for preflight to fully extend a LEFT cache "
                         "(serially across all expected RIGHTs) before "
                         "concurrent emit-only dispatches")
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
                     force=args.force, timeout=args.timeout,
                     extend_only=args.extend_only)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
