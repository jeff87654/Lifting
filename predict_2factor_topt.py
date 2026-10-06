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
    diag_dir/_gap_diag.txt for post-mortem inspection.

    stdin=DEVNULL: a GAP Error() drops into the break loop, which reads
    stdin.  With an inherited (open, silent) stdin the session hangs until
    the subprocess timeout instead of dying; with stdin at EOF the break
    loop exits immediately, so every die-loudly Error() in the drivers is a
    fast clean death rather than a wedge."""
    if timeout is None or timeout <= 0 or timeout >= 86400 * 30:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL)
    else:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=timeout)
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


def drop_cache_if_corrupt(cache_path):
    """Delete an existing H-cache file if it contains non-ASCII bytes -- the
    signature of an OOM-interrupted / torn write that IsValidCacheFile's
    tail-only check (trailing ']];') cannot detect.  Such a file passes the
    tail check but makes GAP's Read abort mid-parse ("Variable: 'k' must have a
    value" -> H_CACHE := fail -> no RESULT), and the corrupt file then survives
    every retry round.  Dropping it here lets the driver's own rebuild path
    regenerate it cleanly instead.  Fast C-level scan (~1-2s/GB), negligible
    next to the multi-second GAP Read that follows.  No-op for "" (TG RIGHT)
    or absent files.  Returns True iff a corrupt file was removed."""
    if not cache_path:
        return False
    p = Path(cache_path)
    if not p.is_file():
        return False
    allowed = bytes(sorted(set(range(32, 127)) | {9, 10, 13}))  # printable + tab/LF/CR
    corrupt = False
    try:
        with p.open("rb") as f:
            while True:
                chunk = f.read(1 << 22)
                if not chunk:
                    break
                if chunk.translate(None, allowed):   # any byte left over => corrupt
                    corrupt = True
                    break
    except OSError:
        return False   # can't read it -> let the driver attempt it (no worse than before)
    # Unlink ONLY after the file handle is closed: on Windows, deleting an open
    # file raises PermissionError, which would otherwise be silently swallowed
    # and leave the corrupt cache in place (making this guard a no-op).
    if corrupt:
        try:
            p.unlink()
            print(f"  [cache-guard] corrupt H-cache deleted (will rebuild): {p}",
                  file=sys.stderr, flush=True)
            return True
        except OSError:
            return False
    return False


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
#
# predict_2factor splits a combo into a LEFT 2-factor input and a RIGHT input.
# The split geometry is one of exactly THREE modes, chosen from the combo's
# species multiplicities:
#
#   "distinguished"  some species occurs once  -> pivot it to RIGHT as TG(d,t)
#   "split"          factors partition into disjoint LEFT/RIGHT sets (>= 2
#                    clusters, or a single species peeled a+b)  -> RIGHT is a
#                    subgroup-list
#   "burnside_m2"    an equal same-species pair T^2  -> both sides TG(d,t),
#                    with the canonical-emission gate
#
# Each mode resolves to one concrete STRATEGY consumed by resolve_inputs() (and
# emitted as the job's mode string): "distinguished", "holt_split",
# "peel_c2_pair", or "burnside_m2".  "distinguished"/"burnside_m2" name both a
# mode and its strategy; "split" fans out to "holt_split"/"peel_c2_pair".  The
# fine-grained strategy names are ALSO accepted directly as --mode aliases (so
# existing --mode holt_split|peel_c2_pair callers keep working) -- see
# resolve_strategy().
MODE_DISTINGUISHED = "distinguished"
MODE_SPLIT = "split"
MODE_BURNSIDE_M2 = "burnside_m2"
CLEAN_MODES = (MODE_DISTINGUISHED, MODE_SPLIT, MODE_BURNSIDE_M2)
_STRATEGIES = ("distinguished", "holt_split", "peel_c2_pair", "burnside_m2")


def classify(combo):
    """Transparent split-geometry taxonomy: map a combo to one of the three
    MODES (or "unsupported").  Depends only on species multiplicities."""
    clusters = Counter(combo)
    if any(mult == 1 for mult in clusters.values()):
        return MODE_DISTINGUISHED            # a unique factor exists
    if len(clusters) >= 2:
        return MODE_SPLIT                     # >= 2 distinct clusters, none unique
    # Single species, all blocks identical.
    (_, mult), = clusters.items()
    if mult == 2:
        return MODE_BURNSIDE_M2               # equal pair T^2
    if mult >= 3:
        return MODE_SPLIT                     # single-species a+b self-split
    return "unsupported"


def _split_strategy(combo):
    """Concrete strategy for SPLIT mode, preserving the exact original gate.

    Peel both (2,1)s to RIGHT when (2,1) occurs EXACTLY twice alongside at least
    one other cluster -- the heavy remainder lands on LEFT where H_CACHE/entry is
    much cheaper (confirmed 6.6x on [2,1]_[2,1]_[8,22]_[8,22]: 4.7h holt_split ->
    42min peel_c2_pair).  GATE FIXED 2026-05-23: mult EXACTLY 2; `>= 2` over-counted
    mult=3 cases like [2,1]^3 [3,1]^2 (+2) / [2,1]^3 [3,2]^2 (+38) because peeling 2
    of 3 strands a [2,1] on LEFT.  Otherwise use the inter-cluster (>= 2 species)
    or single-species a+b Holt split.  NOTE: the single-species split emits
    N_LEFT x N_RIGHT-deduped (over-counted) candidates; the final dedup under the
    full N_{S_n}(partition) is applied downstream by the orchestrator's
    wreath_via_2factor step 2 (see runner/route.py)."""
    clusters = Counter(combo)
    if clusters.get((2, 1), 0) == 2 and len(clusters) >= 2:
        return "peel_c2_pair"
    return "holt_split"


def resolve_strategy(combo, requested):
    """Map a requested --mode to the concrete resolve_inputs strategy.  Accepts
    "auto", the three clean mode names, and the legacy fine-grained strategy
    names as aliases."""
    if requested == "auto":
        requested = classify(combo)
    if requested in _STRATEGIES:
        # An explicit strategy / alias, or the "distinguished"/"burnside_m2"
        # modes which share their strategy name.
        return requested
    if requested == MODE_SPLIT:
        return _split_strategy(combo)
    if requested == "unsupported":
        return "unsupported"
    raise ValueError(f"unknown mode: {requested}")


def auto_mode(combo):
    """Back-compat shim: the concrete strategy auto-selected for `combo`.
    Equivalent to resolve_strategy(combo, "auto")."""
    return resolve_strategy(combo, "auto")


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
        # Swap so the side with MORE subgroups (= the heavier H_CACHE build)
        # lands on LEFT, where it is built once and reused across all RIGHT
        # pairs.  GENERALIZED 2026-05-29: previously gated on `all(d<=4)`, which
        # left a degree-6+ RIGHT cluster (e.g. [3,1]_[3,1]_[6,11]_[6,11]) on the
        # RIGHT and hit the slow per-combo RIGHT-cache path (~30-44 min/combo on
        # the n=18 v3-only build).  Now fires whenever the RIGHT source is
        # larger, for any holt_split combo.  The swap is conjugation-invariant
        # (count-preserving) and A/B-verified win-or-neutral; see memory
        # holt_split_v2_routing_removed.  PREDICT_FORCE_SWAP_LR=1 forces it.
        force_swap = os.environ.get("PREDICT_FORCE_SWAP_LR") == "1"
        no_swap = os.environ.get("PREDICT_NO_SWAP") == "1"   # debug: force original orientation
        left_n_subs = len(parse_combo_file(source_path(left)))
        right_n_subs = len(parse_combo_file(source_path(right)))
        if not no_swap and (force_swap or right_n_subs > left_n_subs):
            left, right = right, left
            reason = ("PREDICT_FORCE_SWAP_LR" if force_swap
                      else f"heavier RIGHT source ({right_n_subs}>{left_n_subs})")
            print(f"[resolve_inputs] swapped LEFT/RIGHT ({reason}): "
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

    if mode == "peel_c2_pair":
        # Combo has (2,1) with mult >= 2 and at least one other cluster.
        # Peel both (2,1)s to RIGHT as a subgroup-list, leaving the heavy
        # remainder on LEFT.  This swaps the holt_split orientation so the
        # 334-entry-class side becomes LEFT (cheaper H_CACHE/entry).  See the
        # [2,1]_[2,1]_[8,22]_[8,22] case: 4.7h holt_split -> 42min peel_c2_pair.
        c2 = (2, 1)
        if clusters.get(c2, 0) != 2:
            raise ValueError("peel_c2_pair mode requires (2,1) with mult EXACTLY 2")
        if len(clusters) < 2:
            raise ValueError("peel_c2_pair mode requires at least one non-(2,1) cluster")
        c_left = list(combo); c_left.remove(c2); c_left.remove(c2)
        c_left = tuple(sorted(c_left))
        right_combo = (c2, c2)
        return {
            "left_combo": c_left,
            "right_combo": right_combo,
            "right_tg": None,
            "m_left": sum(d for d, _ in c_left),
            "m_right": 4,
            "burnside_m2": False,
        }

    raise ValueError(f"unknown mode: {mode}")


# ---- GAP driver ---------------------------------------------------------

# ---- Shared GAP driver components (de-duplicated; see plan) ----
# _SHARED_HELPERS is GAP_DRIVER's helper region verbatim; it is a strict
# superset of the batch/super region by inert comments + a guarded
# idempotent Read, so all three drivers share one definition.
_PREAMBLE_GAP = r"""
LogTo("__LOG__");
SCRIPT_START := Runtime();        # startup-phase timer (see BENCH_STARTUP)
BENCH_STARTUP := __BENCH_STARTUP__;   # 1 = emit [PHASE t=...] prints at session-startup checkpoints
if BENCH_STARTUP = 1 then
    Print("[PHASE t=", SCRIPT_START, "ms] gap_startup_done (gap-startup + run.g parse cost)\n");
fi;

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
FRAMED_CACHE := __FRAMED_CACHE__;   # 1 => write windowable framed cache (+ .idx)
# Streaming H-cache build (PRED_STREAM_HCACHE_BUILD; requires FRAMED_CACHE=1).
# See BuildHCacheStreaming in the shared helpers.
STREAM_HCACHE_BUILD := __STREAM_HCACHE_BUILD__;
BUILD_TOKEN := "__BUILD_TOKEN__";            # process-private .building suffix
HCACHE_BUILD_VER := "__HCACHE_BUILD_VER__";  # entry-content version marker
STREAM_WINDOW_MIN := __STREAM_WINDOW_MIN__;  # (windowed pair loop is BATCH-only)
STATE_FILE    := "__STATE_FILE__";   # checkpoint state path; "" disables
CHECKPOINT_INTERVAL_MS := __CHECKPOINT_INTERVAL_MS__;
STATE_SAVE_INTERVAL_MS := __STATE_SAVE_INTERVAL_MS__;
LAST_STATE_SAVE_MS := 0;
EXTEND_ONLY    := __EXTEND_ONLY__;   # 1 = exit after cache extension+save (skip emit)
# Cut 3: when 1, ExtendHCacheEntry / ComputeHCacheEntry / ComputeHDataDirect
# dispatch to LinearOrbitRecsCpa / LinearOrbitRecsD8 / LinearOrbitRecsS3
# (Stage A/B/C prototypes) for qids in {C_2, C_3, V_4, S_3, D_8}, producing
# N_H-orbit records directly without enumerating-all-kernels-then-orbiting.
# Other qids fall back to the legacy
# _EnumerateNormalsForQGroups + _ComputeOrbitRecsFromKs path.  Default ON;
# set env var PRED_USE_LINEAR_ORBITS=0 to force legacy path for a single run.
USE_LINEAR_ORBITS := __USE_LINEAR_ORBITS__;
USE_STAGE_D := __USE_STAGE_D__;
if USE_LINEAR_ORBITS = 1 then
    Print("[USE_LINEAR_ORBITS=1] loading Stage A/B/C prototypes...\n");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_a.g");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_b.g");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_c.g");
    if USE_STAGE_D = 1 then
        Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_d.g");
    fi;
fi;
if BENCH_STARTUP = 1 then
    Print("[PHASE t=", Runtime() - SCRIPT_START, "ms] after_prototype_loads\n");
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
# Wall-clock baseline for the hard checkpoint-restart trigger.  Runtime() is CPU
# time, which stalls when a bloated worker thrashes on page faults -- so a
# CPU-keyed 2h restart can never fire on the exact heavy jobs it must bound.
# NanosecondsSinceEpoch() is monotonic wall time, immune to iowait starvation.
WORKER_START_WALL := NanosecondsSinceEpoch();

# Resume state — set by reading STATE_FILE if it exists.  Python wrapper has
# already truncated EMIT_GENS_PATH to the byte position right after the last
# "# checkpoint" marker line for the (i, j) we're resuming from.
i_resume_start := 1;
j_resume_start := 1;
resume_total_orb := 0;
resume_total_fix := 0;
resume_total_cs := 0;
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
        # class_sum (labelled harvest) must survive resume too, else a combo
        # that checkpoints mid-emit undercounts its # class_sum by the pairs
        # processed before the checkpoint.  IsBound guard: old state files
        # (pre-fix) lack it -> resume_total_cs stays 0 (same as old behavior).
        if IsBound(RESUME_STATE.total_cs_sum) then
            resume_total_cs := RESUME_STATE.total_cs_sum;
        fi;
        Print("RESUMING from i=", i_resume_start, " j=", j_resume_start,
              " orb=", resume_total_orb, "\n");
    fi;
fi;

Print("predict_2factor: ml=", ML, " mr=", MR, " target_n=", TARGET_N,
      " burnside_m2=", BURNSIDE_M2, "\n");

# ---- helpers ----
"""
_SHARED_HELPERS = r"""# === Pre-declare globals to silence parser warnings ============================
# GAP's parser emits "Unbound global variable" for any forward reference,
# even when the variable is bound at runtime by file Read() or by a top-level
# assignment later in this driver source.  Pre-declaring them below makes
# the parser see them as bound, eliminating 51 warning prints per session
# (~3s of session-startup cost per fresh GAP invocation -- significant for
# small combos and for orchestrator restarts).  IdempotentIfNotBound idiom
# preserves "load once across multiple Read()s in the same session".
if not IsBound(SCRIPT_START)                     then SCRIPT_START := Runtime(); fi;
if not IsBound(BENCH_STARTUP)                    then BENCH_STARTUP := 0; fi;
# Lazy DEFEND (2026-05-29): when 1, ReconstructHData does NOT trust the cached
# Stab_NH_KH_size; ProcessPair recomputes Size(Stab) fresh from gens at point-
# of-use (lazy => only paired orbits).  Guards against the transient cache
# corruption that undercounted n=18 labelled counts.  Default ON.
if not IsBound(LAZY_STAB)                        then LAZY_STAB := 1; fi;
# Lazy LEFT reconstruction (BATCH driver, PRED_LAZY_LEFT_RECON): when 1, skip
# the eager H1DATA_LIST build and reconstruct each H1data per-i inside the pair
# loop, bounding the reconstructed-group footprint to O(1) instead of
# O(N_LEFT).  Production default 1 since 2026-06-09 (env opt-out =0); the
# IsBound fallback stays 0 for ad-hoc Reads.  See _LOOP_BATCH.  (GAP_DRIVER is
# already lazy.)
if not IsBound(LAZY_LEFT_RECON)                  then LAZY_LEFT_RECON := 0; fi;
# Framed (windowable) cache writing (PRED_FRAMED_CACHE): when 1, SaveHCacheList
# writes the per-entry framed format + a .idx byte-offset sidecar, so a pair-loop
# resume can read only its LEFT slice via OpenHCacheWindow/GetHCacheEntry instead
# of parsing the whole cache.  Production default 1 since 2026-06-09 (env
# opt-out =0); the IsBound fallback stays 0 for ad-hoc Reads.  New code READS
# both formats regardless of this flag.  See SaveHCacheFramed / GetHCacheEntry.
if not IsBound(FRAMED_CACHE)                     then FRAMED_CACHE := 0; fi;
# Windowed-LEFT state: set per-job when a complete framed cache is opened for a
# pair-loop resume; the pair loop then reads each LEFT entry on demand.
if not IsBound(USE_WINDOWED_LEFT)                then USE_WINDOWED_LEFT := false; fi;
if not IsBound(HCW_STREAM)                       then HCW_STREAM := fail; fi;
if not IsBound(HCW_OFFSETS)                      then HCW_OFFSETS := fail; fi;
if not IsBound(HCW_COUNT)                        then HCW_COUNT := 0; fi;
# Streaming H-cache build (PRED_STREAM_HCACHE_BUILD; requires FRAMED_CACHE=1):
# see BuildHCacheStreaming below.  Values assigned by each driver's preamble;
# pre-declared here for parser warnings + ad-hoc Read()s of the helpers.
if not IsBound(STREAM_HCACHE_BUILD)              then STREAM_HCACHE_BUILD := 0; fi;
if not IsBound(BUILD_TOKEN)                      then BUILD_TOKEN := "default"; fi;
if not IsBound(HCACHE_BUILD_VER)                 then HCACHE_BUILD_VER := "1"; fi;
if not IsBound(STREAM_WINDOW_MIN)                then STREAM_WINDOW_MIN := 20000; fi;
# fail => BuildHCacheStreaming computes fresh; a <path> => it reads+extends that
# old framed cache one entry at a time (memory-bounded extend).  The extend
# wiring sets it just before the call and resets it after.
if not IsBound(STREAM_EXTEND_FROM)               then STREAM_EXTEND_FROM := fail; fi;
# Stage D (O_p-split glue quotients, PRED_STAGE_D; 2026-06-09): the real
# symbols are bound by prototype_stage_d.g, Read in the preamble when
# USE_LINEAR_ORBITS=1 and USE_STAGE_D=1.  Pre-declare so the dispatcher
# below parses without warnings when Stage D is off.
if not IsBound(USE_STAGE_D)                      then USE_STAGE_D := 0; fi;
if not IsBound(StageDEntryForQid)                then StageDEntryForQid := fail; fi;
if not IsBound(LinearOrbitRecsStageDMulti)       then LinearOrbitRecsStageDMulti := fail; fi;
# LEFT-realizability Q-prune gate (2026-06-03).  In each driver's `else` branch
# (RIGHT_Q_GROUPS non-empty) LEFT_Q_GROUPS is the candidate set of common Goursat
# quotient types.  RIGHT_Q_GROUPS bounds these to RIGHT-realizable types passing
# |Q| | |H_L|, but that order test is only NECESSARY: a rigid LEFT (simple/perfect
# -- A9, S9, ...) realises almost none of them, yet without a LEFT-realizability
# test the per-job RIGHT enumeration grinds for hours on Q-types that can never
# pair (Goursat) -- the n=21 [9,33]/[9,34] x [12,*] hang.  The prune keeps only Q
# that some LEFT subgroup actually surjects onto, tested EXACTLY via GQuotients
# (deliberately NOT HasQuotientType, whose p-group necessary-conditions have
# undercounted before -- an exact test can never drop a real Q).  It is
# COUNT-NEUTRAL by construction (a Q no LEFT subgroup realises contributes zero
# Goursat pairings), so this gate is a PERFORMANCE knob ONLY and never changes the
# result: it just bounds the |SUBGROUPS_LEFT_RAW| x |RIGHT_Q_GROUPS| GQuotients
# scan to the cheap regime -- few LEFT subgroups, i.e. the rigid distinguished
# LEFTs that need it.  Rich large-LEFT clusters (2-groups, thousands of subgroups)
# exceed the gate and keep the over-approximation, which is already tight there
# (their many quotients ARE realised, so little would be pruned anyway).  Set 0
# to disable the prune.
# SOLVABLE-LEFT GUARD (2026-06-05): the `<=QPRUNE_MAXSUBS` count gate alone also
# catches SMALL *solvable* clusters (e.g. [4,3]_[8,3] = D8 x C2^3, 5 reps), where
# GQuotients(2-group, 2-group-Q) is EXPONENTIAL and wedged the n=20 build for hours
# in LEFT-setup -- the opposite of the cheap A9/S9 case (simple LEFT => few normal
# subgroups => trivial GQuotients).  So the prune now also requires the LEFT to be
# NON-solvable (`not ForAll(SUBGROUPS_LEFT_RAW, IsSolvableGroup)`): rigid simple
# LEFTs (A_n/S_n/...) get the prune (cheap + needed); solvable/2-group LEFTs keep
# the over-approximation (cheap + already tight).  Still count-neutral.
if not IsBound(QPRUNE_MAXSUBS)                   then QPRUNE_MAXSUBS := 16; fi;
# LEFT-realizable fast prune (2026-06-21): when every LEFT subgroup is a natural
# A_n/S_n or simple group its quotient lattice is tiny, so the LEFT-realizable
# Q-type set is read straight off NormalSubgroups(LEFT) and used to filter RIGHT
# Q-discovery BEFORE the (IdGroup-less) pairwise IsomorphismGroups dedup in
# QTypeIsNew.  COUNT-IDENTICAL to the GQuotients prune below (Q realizable by HL
# <=> GQuotients(HL,Q)<>[]), but ms vs hours once RIGHT_Q_GROUPS is unioned over a
# whole batch -- THE S8/S10-single-block-LEFT n=22 wedge.  Set 0 to disable.
if not IsBound(USE_LEFT_REALIZABLE)              then USE_LEFT_REALIZABLE := 1; fi;
if not IsBound(shift_R)                          then shift_R := fail; fi;
if not IsBound(H_CACHE)                          then H_CACHE := fail; fi;
if not IsBound(SUBGROUPS)                        then SUBGROUPS := fail; fi;
if not IsBound(LEFT_Q_GROUPS)                    then LEFT_Q_GROUPS := fail; fi;
if not IsBound(LEFT_Q_GROUPS_SAVED_OK)           then LEFT_Q_GROUPS_SAVED_OK := false; fi;
if not IsBound(RIGHT_QGROUPS_FROM_SUBS)          then RIGHT_QGROUPS_FROM_SUBS := fail; fi;
if not IsBound(RIGHT_QGROUPS_FROM_SUBS_SAVED_OK) then RIGHT_QGROUPS_FROM_SUBS_SAVED_OK := false; fi;
if not IsBound(REQUIRED_QGROUPS_CACHED)          then REQUIRED_QGROUPS_CACHED := fail; fi;
if not IsBound(REQUIRED_QGROUPS_CACHED_SAVED_OK) then REQUIRED_QGROUPS_CACHED_SAVED_OK := false; fi;
if not IsBound(_REQUIRED_QGROUPS_CACHE)          then _REQUIRED_QGROUPS_CACHE := rec(); fi;
if not IsBound(META_Q_CATALOG)                   then META_Q_CATALOG := []; fi;
if not IsBound(META_Q_CATALOG_SAVED_OK)          then META_Q_CATALOG_SAVED_OK := false; fi;
if not IsBound(META_H_TO_QS)                     then META_H_TO_QS := []; fi;
if not IsBound(META_H_TO_QS_SAVED_OK)            then META_H_TO_QS_SAVED_OK := false; fi;
if not IsBound(META_H_TO_QS_NEW)                 then META_H_TO_QS_NEW := []; fi;
if not IsBound(META_H_TO_QS_NEW_SAVED_OK)        then META_H_TO_QS_NEW_SAVED_OK := false; fi;
# Forward-referenced functions: bind a placeholder; the real definition later
# in this source replaces it.  Placeholder returns fail so calls would fail
# noisily if (somehow) invoked before redefinition.
if not IsBound(HasQuotientType)           then HasQuotientType           := function(arg) return fail; end; fi;
if not IsBound(IsValidCacheFile)          then IsValidCacheFile          := function(arg) return fail; end; fi;
if not IsBound(ForcedQRepsFromHCache)     then ForcedQRepsFromHCache     := function(arg) return fail; end; fi;
if not IsBound(ProcessForcedLargeQTypes)  then ProcessForcedLargeQTypes  := function(arg) return fail; end; fi;
if not IsBound(PromoteUnknownLargeOrders) then PromoteUnknownLargeOrders := function(arg) return fail; end; fi;
# ==============================================================================

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

# === Iso-class dedup for quotient groups Q (2026-05-26) ====================
# SafeId(Q) is a COMPLETE iso-invariant only when qid[2] = 0 (a SmallGroups id
# is available).  When qid[2] = 1 (the order has no SmallGroups library -- e.g.
# 1024, or > 2000), SafeId is only a COARSE invariant (order + abelian
# invariants + derived-series sizes); distinct iso-classes can collide.  A raw
# `SafeId(Q) in seen` dedup then silently drops a real Q-type from discovery,
# or wrongly marks it covered in the H-cache -> missed Goursat fiber products
# -> undercount.
#
# QTypeIsNew buckets unsafe Q's by their coarse id and disambiguates WITHIN a
# bucket with a real IsomorphismGroups test.  Safe Q's keep the cheap exact
# path (no isomorphism test, so no cost in the common case).  Use one fresh
# state record per discovery loop (NewQTypeState).
NewQTypeState := function()
    return rec(exact_seen := Set([]), unsafe_seen := rec());
end;

QTypeIsNew := function(state, Q)
    local qid, key, R;
    qid := SafeId(Q);
    if qid[2] = 0 then
        key := String(qid);
        if key in state.exact_seen then return false; fi;
        AddSet(state.exact_seen, key);
        return true;
    fi;
    key := SanitizeHidStr(String(qid));
    if not IsBound(state.unsafe_seen.(key)) then
        state.unsafe_seen.(key) := [];
    fi;
    for R in state.unsafe_seen.(key) do
        if Size(R) = Size(Q) and IsomorphismGroups(Q, R) <> fail then
            return false;
        fi;
    od;
    Add(state.unsafe_seen.(key), Q);
    return true;
end;

# --- LEFT-realizable Q-type fast path (see USE_LEFT_REALIZABLE) ----------------
# Realizable nontrivial quotient TYPES of the LEFT subgroups, { HL/N : N normal in
# HL, N <> HL }, deduped up to isomorphism -- but ONLY when every HL is a natural
# A_n / S_n or a simple group (tiny normal lattice => NormalSubgroups is instant).
# Returns fail otherwise (caller keeps the generic GQuotients prune).  This set is
# exactly { Q : some HL surjects onto Q } = the GQuotients-prune survivor set
# (Q realizable by HL  <=>  GQuotients(HL,Q) <> []), so filtering RIGHT discovery
# to membership here is COUNT-IDENTICAL while skipping the lethal IsomorphismGroups
# dedup of every (huge, IdGroup-less) RIGHT quotient type.
LeftRealizableQTypesIfCheap := function(subs_left)
    local reps, HL, N, Q, r, isnew;
    if Length(subs_left) = 0 then return fail; fi;
    for HL in subs_left do
        if not (IsNaturalSymmetricGroup(HL) or IsNaturalAlternatingGroup(HL)
                or IsSimpleGroup(HL)) then
            return fail;
        fi;
    od;
    reps := [];
    for HL in subs_left do
        for N in NormalSubgroups(HL) do
            if Size(N) = Size(HL) then continue; fi;   # N = HL -> trivial quotient
            Q := HL / N;
            isnew := true;
            for r in reps do
                if Size(r) = Size(Q) and IsomorphismGroups(r, Q) <> fail then
                    isnew := false; break;
                fi;
            od;
            if isnew then Add(reps, Q); fi;
        od;
    od;
    return reps;
end;

# True iff Q is isomorphic to some group in reps (cheap Size pre-filter first).
QTypeInRepList := function(reps, Q)
    local r;
    for r in reps do
        if Size(r) = Size(Q) and IsomorphismGroups(r, Q) <> fail then
            return true;
        fi;
    od;
    return false;
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
    local sidecar, tmp, R, K, Q, qstate, result;
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
    qstate := NewQTypeState();
    for R in SUBGROUPS do
        for K in NormalSubgroups(R) do
            if Size(K) = Size(R) then continue; fi;
            Q := R/K;
            if QTypeIsNew(qstate, Q) then
                Add(result, Q);
            fi;
        od;
    od;
    # Normalize FactorGroup objects (their abstract f1, f2 generator names
    # would not be re-bindable on Read of the cached sidecar).
    result := List(result, function(q)
        local n, q_id, P;
        n := Size(q);
        if IdGroupsAvailable(n) then
            q_id := IdGroup(q);
            # SmallGroup(n,id) is a pc group -> serializes as Group([f1,f2])
            # (unbound globals on Read).  Convert to a perm rep so PrintTo
            # emits a re-readable Group([<perms>]).
            P := Image(IsomorphismPermGroup(SmallGroup(n, q_id[2])));
        else
            P := Image(IsomorphismPermGroup(q));
        fi;
        return GroupByGenerators(GeneratorsOfGroup(P));
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
    local H, N, N_size, res, orbit_data, K, Stab, Stab_size, i, key, hom_triv;
    H := SafeGroup(entry.H_gens, S_M);
    N := SafeGroup(entry.N_H_gens, S_M);
    # Compute |N| once and tag it on N so any other code path benefits.
    N_size := Size(N);
    res := rec(H := H, N := N, N_size := N_size,
        H_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_H := fail, shifted_H_gens_noid := fail,
        orbits := []);
    # Trivial-quotient orbit (always present; hom is fast for H/H).
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N, Stab_size := N_size, AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
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
        # HARVEST: prefer the cached Stab_NH_KH_size (newer cache builds).
        # Older caches lack it -> set to fail; ProcessPair falls back to Size().
        # LAZY_STAB=1 (default): do NOT trust the cached size (it can be
        # corrupted by a transient cache-extend; see 2026-05-29 n=18 labelled
        # undercount) -- leave Stab_size = fail so ProcessPair recomputes
        # Size(Stab) fresh from the gens at point-of-use, only for paired orbits.
        if LAZY_STAB = 1 then
            Stab_size := fail;
        elif IsBound(orbit_data.Stab_NH_KH_size) then
            Stab_size := orbit_data.Stab_NH_KH_size;
            SetSize(Stab, Stab_size);
        else
            Stab_size := fail;
        fi;
        Add(res.orbits, rec(K := K, hom := fail, Q := fail,
            qsize := orbit_data.qsize, qid := orbit_data.qid,
            Stab := Stab, Stab_size := Stab_size, AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
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
    local qid_str, bucket, can_entry, cand, iso, raw_a_gens;
    if orb.AutQ <> fail then return; fi;
    if orb.qsize <= 1 then return; fi;   # trivial Q has no auto
    EnsureHom(orb);   # AutQ depends on Q
    # Opt #5: canonical Q registry.  Each qid keys a LIST of canonical reps,
    # one per ISO-CLASS seen under that qid (2026-06-09; was a single slot).
    # For IdGroup-unavailable orders SafeId is a heuristic, and since the
    # 2026-05-26 QTypeIsNew fix, non-isomorphic Q-types LEGITIMATELY share a
    # coarse qid.  The old single slot's defensive fallback REPLACED the
    # canonical entry when IsomorphismGroups failed, so already-ensured
    # orbits kept A_gens in the OLD Aut(Q) while later orbits used the NEW
    # one -- SafeSub(h1orb.AutQ, h2orb.A_gens) then mixed automorphism
    # parents (hard GAP error -> combo lost with only a retry WARNING), and
    # collided buckets flip-flopped for the rest of the session.  Bucket
    # entries are pairwise non-isomorphic and NEVER replaced: every orbit of
    # one iso-class shares the same stable Q/AutQ objects, so a genuine
    # isoTH match in the pair loop implies both sides used the SAME
    # canonical entry.  Safe qids (exact IdGroup) keep exactly one entry and
    # pay the same single IsomorphismGroups call as before.
    qid_str := String(orb.qid);
    if not IsBound(QCAN_TABLE.(qid_str)) then
        QCAN_TABLE.(qid_str) := [];
    fi;
    bucket := QCAN_TABLE.(qid_str);
    can_entry := fail;
    for cand in bucket do
        iso := IsomorphismGroups(orb.Q, cand.Q);
        if iso <> fail then
            can_entry := cand;
            orb.iso_to_can := iso;
            break;
        fi;
    od;
    if can_entry = fail then
        # First orbit of this iso-class: register its Q as the class's
        # canonical rep (appended; earlier classes keep their entries).
        can_entry := rec(Q := orb.Q, AutQ := AutomorphismGroup(orb.Q));
        Add(bucket, can_entry);
        orb.iso_to_can := IdentityMapping(orb.Q);
        if Length(bucket) > 1 then
            Print("    [qcan] unsafe-qid collision: qid ", qid_str,
                  " now has ", Length(bucket), " iso-classes\n");
        fi;
    fi;
    orb.AutQ := can_entry.AutQ;
    raw_a_gens := InducedAutoGens(orb.Stab, orb.H_ref, orb.hom);
    orb.raw_A_gens := raw_a_gens;
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
if not IsBound(DC_GLOBAL) then
    DC_GLOBAL := rec(auts := [], caches := [], n_hit := 0, n_miss := 0);
fi;

LookupOrComputeDC := function(h1orb, A1, A2_in_h1)
    local entry, dcs, gpos, gcache, s1, s2;
    if h1orb.dc_cache = fail then h1orb.dc_cache := []; fi;
    for entry in h1orb.dc_cache do
        if entry[1] = A2_in_h1 then
            if BENCH_PHASES = 1 then BENCH_N.n_dc_cache_hits := BENCH_N.n_dc_cache_hits + 1; fi;
            return entry[2];
        fi;
    od;
    # bench v4: GLOBAL cache keyed by (canonical AutQ object identity, A1,
    # A2) with |.| prefilter.  Sound: DoubleCosets depends only on the
    # subgroup sets; any transversal is valid for emit, Length is
    # count-exact, membership tests are set-based.  Post-qcan all orbits of
    # a qid share ONE AutQ object, so cross-h1orb reuse is well-defined.
    gpos := PositionProperty(DC_GLOBAL.auts, A -> IsIdenticalObj(A, h1orb.AutQ));
    if gpos = fail then
        Add(DC_GLOBAL.auts, h1orb.AutQ);
        Add(DC_GLOBAL.caches, []);
        gpos := Length(DC_GLOBAL.auts);
    fi;
    gcache := DC_GLOBAL.caches[gpos];
    s1 := Size(A1); s2 := Size(A2_in_h1);
    for entry in gcache do
        if entry[3] = s1 and entry[4] = s2
           and entry[1] = A1 and entry[2] = A2_in_h1 then
            DC_GLOBAL.n_hit := DC_GLOBAL.n_hit + 1;
            Add(h1orb.dc_cache, [A2_in_h1, entry[5]]);
            return entry[5];
        fi;
    od;
    if BENCH_PHASES = 1 then BENCH_N.n_dc_cache_misses := BENCH_N.n_dc_cache_misses + 1; fi;
    DC_GLOBAL.n_miss := DC_GLOBAL.n_miss + 1;
    dcs := DoubleCosets(h1orb.AutQ, A2_in_h1, A1);
    Add(h1orb.dc_cache, [A2_in_h1, dcs]);
    if Length(gcache) < 5000 then
        Add(gcache, [A1, A2_in_h1, s1, s2, dcs]);
    fi;
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
    local result, qstate, t, T, K, Q, key, cache_path, slash, i, t0;
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
    qstate := NewQTypeState();
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
            if QTypeIsNew(qstate, Q) then
                Add(result, Q);
            fi;
        od;
    od;
    # Normalize for safe re-Read (FactorGroup uses unbound generator names).
    result := List(result, function(q)
        local n, q_id, P;
        n := Size(q);
        if IdGroupsAvailable(n) then
            q_id := IdGroup(q);
            # SmallGroup(n,id) is a pc group -> serializes as Group([f1,f2])
            # (unbound globals on Read).  Convert to a perm rep so PrintTo
            # emits a re-readable Group([<perms>]).
            P := Image(IsomorphismPermGroup(SmallGroup(n, q_id[2])));
        else
            P := Image(IsomorphismPermGroup(q));
        fi;
        return GroupByGenerators(GeneratorsOfGroup(P));
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
          pos, qstate;
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
    qstate := NewQTypeState();
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
            if QTypeIsNew(qstate, Q) then
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
          forced_qrecs_dedup, qstate, qr, forced_qgroups,
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
    qstate := NewQTypeState();
    forced_qrecs_dedup := [];
    for qr in forced_qrecs do
        if QTypeIsNew(qstate, qr.Q) then
            Add(forced_qrecs_dedup, qr);
        fi;
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
        local n, q_id, P;
        n := Size(q);
        if IdGroupsAvailable(n) then
            q_id := IdGroup(q);
            # SmallGroup(n,id) is a pc group -> serializes as Group([f1,f2])
            # (unbound globals on Read).  Convert to a perm rep so PrintTo
            # emits a re-readable Group([<perms>]).
            P := Image(IsomorphismPermGroup(SmallGroup(n, q_id[2])));
        else
            P := Image(IsomorphismPermGroup(q));
        fi;
        return GroupByGenerators(GeneratorsOfGroup(P));
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

# Current GAP workspace size in KB (GASMAN total).  GASMAN("collect") populates
# the .full stats and frees dead bags; the workspace itself only grows within a
# session (with -o 0 it is never returned to the OS), so totalkb tracks the
# process memory high-water -- the right signal for a memory-based checkpoint.
# Returns 0 if stats unavailable (callers treat 0 as "under limit").
CurrentWorkspaceKB := function()
    local s;
    GASMAN("collect");
    s := GasmanStatistics();
    if IsBound(s.full) then return s.full.totalkb; fi;
    return 0;
end;

QIdsOfGroups := function(q_groups)
    if q_groups = fail then return fail; fi;
    return Set(List(q_groups, SafeId));
end;

# Actual Q representatives (perm groups, re-Readable) for the UNSAFE (qid[2]=1)
# members of a q_groups list.  Stored in H-cache entries as
# computed_q_unsafe_reps so coverage tests can run a real IsomorphismGroups
# check -- SafeId alone collides for these orders.  Safe Q's need no rep (their
# qid is an exact iso-classifier).
_UnsafeQReps := function(q_groups)
    local out, Q, P;
    out := [];
    for Q in q_groups do
        if SafeId(Q)[2] = 1 then
            # Re-derive a fresh, NAME-FREE perm group so the cached rep
            # serializes as Group([<perms>]) and re-reads cleanly.  A named
            # library group (e.g. "A7"/"S7") would PrintTo as its bare name,
            # and a pc group as Group([f1,f2]) -- both unbound globals on Read,
            # which aborts the cache load (H_CACHE := fail) and crashes the job.
            P := Image(IsomorphismPermGroup(Q));
            Add(out, GroupByGenerators(GeneratorsOfGroup(P)));
        fi;
    od;
    return out;
end;

# Unsafe reps of an H-cache entry, or `fail` for legacy entries that predate
# the field.  A `fail` return makes QTypeCovered fall back to coarse-qid
# coverage -- identical to pre-2026-05-26 behavior, so loading an old cache
# never regresses (and never over-claims a NEW field it does not have).
_UnsafeRepsOf := function(entry)
    if IsBound(entry.computed_q_unsafe_reps) then
        return entry.computed_q_unsafe_reps;
    fi;
    return fail;
end;

# Is quotient-type Q already covered by (have_ids, have_unsafe_reps)?
# Safe Q (qid[2]=0): exact qid membership.  Unsafe Q (qid[2]=1): real
# isomorphism test against the stored reps; or, when have_unsafe_reps = fail
# (legacy entry), coarse qid membership as a best-effort fallback.
QTypeCovered := function(have_ids, have_unsafe_reps, Q)
    local qid, R;
    qid := SafeId(Q);
    if qid[2] = 0 then return qid in have_ids; fi;
    if have_unsafe_reps <> fail then
        for R in have_unsafe_reps do
            if Size(R) = Size(Q) and IsomorphismGroups(R, Q) <> fail then
                return true;
            fi;
        od;
        return false;
    fi;
    return qid in have_ids;
end;

QGroupsMissing := function(have_ids, have_unsafe_reps, want_groups)
    # want_groups = fail means "full coverage needed". have_ids = fail
    # means "already full coverage". Return values:
    #   []   -- nothing missing (no extension needed)
    #   fail -- need full extension (caller should extend to fail)
    #   list -- specific Q-groups to add via tiered enumeration
    # have_unsafe_reps: the entry's computed_q_unsafe_reps (or fail for a
    # legacy entry) -- lets unsafe Q-types be matched by real isomorphism
    # rather than by a collision-prone SafeId.
    if want_groups = fail then
        if have_ids = fail then return []; fi;
        return fail;
    fi;
    if have_ids = fail then return []; fi;
    return Filtered(want_groups,
                    Q -> not QTypeCovered(have_ids, have_unsafe_reps, Q));
end;

NormalizeHCacheEntry := function(entry)
    # Detect OLD-format cache (pre-Stage-A): had `computed_q_sizes` instead of
    # `computed_q_ids`.  QGroupsMissing treats computed_q_ids=fail as "full
    # coverage", so silently setting fail here would silently drop missing
    # qids and produce undercounts.  Error loudly instead so callers fix the
    # cache path (likely PREDICT_H_CACHE_DIR pointing at a stale cache).
    if IsBound(entry.computed_q_sizes)
       and not IsBound(entry.computed_q_ids) then
        Error("H_CACHE entry uses OLD format (computed_q_sizes only); ",
              "post-Stage-A code requires computed_q_ids. ",
              "Likely cause: PREDICT_H_CACHE_DIR points at a stale cache. ",
              "Use the orchestrator's _h_cache_b_power (or rebuild).");
    fi;
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
          DQ_inv, phidh_rank, dq_rank, DH_ab_inv;
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
        # Necessary condition (a): a surjection H ->> Q maps D_H onto D_Q,
        # hence D_H^ab ->> D_Q^ab, so p-rank(D_H^ab) >= p-rank(D_Q^ab).
        DH_ab_inv := AbelianInvariants(D_H / DerivedSubgroup(D_H));
        DQ_inv := AbelianInvariants(D_Q / DerivedSubgroup(D_Q));
        if Length(Filtered(DH_ab_inv, x -> x mod p = 0))
           < Length(Filtered(DQ_inv, x -> x mod p = 0)) then return false; fi;
        # Necessary condition (b), H-equivariant: D_H/Phi(D_H) ->> D_Q/Phi(D_Q)
        # as GF(p)[H]-modules (H acting on D_Q via H ->> Q), so taking
        # H-coinvariants (right-exact) gives dim((D_H/Phi)_H) >= dim((D_Q/Phi)_Q).
        # dim((D_H/Phi)_H) = relative-Frattini rank of D_H in H; dim((D_Q/Phi)_Q)
        # = relative-Frattini rank of D_Q in Q.  Earlier code compared the LHS
        # against the FULL rank of D_Q^ab (= dim(D_Q/Phi), NOT Q-coinvariants),
        # which over-rejected whenever D_Q^ab carried a nontrivial action --
        # e.g. TG(12,263) ->> SmallGroup(32,6)/(64,34) had LHS=1 but
        # full-rank(D_Q^ab)=2, returning false for genuine quotients so
        # PGroupQuotientKernels dropped them (the 2026-05 n=20 undercount).
        Phi_DH := RelativePhiSubgroup(H, D_H, p);
        phidh_rank := LogInt(Size(D_H) / Size(Phi_DH), p);
        dq_rank := LogInt(Size(D_Q) / Size(RelativePhiSubgroup(Q, D_Q, p)), p);
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
    local out, qstate, entry, orb, Q, key, saved_H_CACHE, right_cache, H, K;
    out := [];
    qstate := NewQTypeState();
    if cache_path = "" or not IsExistingFile(cache_path) then return out; fi;
    if IsFramedCacheFile(cache_path) then
        right_cache := ReadHCacheFramedFull(cache_path);
        if not IsList(right_cache) then return out; fi;
    else
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
    fi;
    for entry in right_cache do
        for orb in entry.orbits do
            if orb.qsize <= cap then continue; fi;
            if orb.qid[2] = 0 then
                # Exact id (SmallGroups library): the qid string IS a
                # complete iso-invariant -- cheap string dedup, no group
                # construction on repeats.
                key := String(orb.qid);
                if key in qstate.exact_seen then continue; fi;
                AddSet(qstate.exact_seen, key);
                Q := SmallGroup(orb.qid[3]);
            else
                # Coarse id (no SmallGroups library, e.g. order 512/1024/
                # 1536/>2000): distinct iso-classes can share the qid string,
                # so a raw string dedup silently drops real Q-types (the
                # 2026-05-26 QTypeIsNew bug class).  Reconstruct Q := H/K and
                # disambiguate with the exact in-bucket IsomorphismGroups
                # test.
                H := Group(entry.H_gens);
                K := Subgroup(H, orb.K_H_gens);
                Q := Image(IsomorphismPermGroup(
                    Range(NaturalHomomorphismByNormalSubgroup(H, K))));
                if not QTypeIsNew(qstate, Q) then continue; fi;
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
          small_recs, direct_recs,
          ea_a, ea_Ap, ea_homV, ea_V, ea_pcgsV, ea_rk, ea_W, ea_U, ea_row, ea_i,
          ea_qid, flt_unsafe_qs, n_flt_before;
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
        # Abelian Q: every kernel of an H->Q surjection contains [H,H], so the
        # kernels biject with GQuotients(A, Q) on the (tiny) abelianization
        # A = H/[H,H] -- no NormalSubgroups(H) needed.  This is the SAME math as
        # the large-H `elif IsAbelian(Q)` branch below (line ~2533), pulled ahead
        # of SmallKernelQuotientKernelRecords so it also fires for |H| <= 4096.
        # WHY: for 2-group LEFT clusters the cyclic Q = C_4 ([4,1]) is excluded
        # from both the linear-orbit fast path (only C2/C3/V4/S3/D8) and the
        # 2-group `small_qs` set (cyclic size-4), so it fell to SmallKernel's
        # NormalSubgroups(H) over a 2-group's huge normal lattice -- 2s/entry at
        # |H|=384, up to 6s at |H|=768, x42234 LEFT entries ~= 4h just to build
        # the LEFT H-cache for [2,1]_[3,2]_[4,3]_[4,3]_[4,3] (the reported case).
        # GQuotients(A, C4) on |A|<=~32 is tens of ms.  Count-neutral: abelian
        # quotients of H biject with quotients of its abelianization.
        if IsAbelian(Q) then
            if abel_hom = fail then continue; fi;
            # Trivial Q: the unique kernel is H itself.  Must be handled before
            # the elementary-abelian branch (IsElementaryAbelian(trivial) = true
            # but Factors(1) = [1] would feed p=1 into LogInt -> error).  The
            # old GQuotients(A, Q) path returned exactly one epimorphism here.
            if sz = 1 then
                Add(result, rec(K := H, qsize := 1, qid := q_qid));
                continue;
            fi;
            # Elementary-abelian Q = C_p^a: the kernels of A -> Q biject with the
            # corank-a subspaces of the GF(p) space A/A^p.  Enumerate them via
            # Subspaces() (cheap finite-field linear algebra) instead of
            # GQuotients, whose Aut(Q) = GL(a,p) backtrack is catastrophic for
            # C_2^3 / C_2^4: measured 17.9 s (C2^4->C2^3) and 152.7 s
            # (C2^4->C2^4) on a |H|=16 group, vs <1 ms here -- this is the
            # [2,1]^3 H-cache-build stall ([enum/abel_early] Q=[8,5]/[16,14]
            # 16-290 s/entry).  Count-neutral: identical kernel set (verified vs
            # GQuotients in _validate_elab_kernels.g / _validate_elab_edge.g).
            if IsElementaryAbelian(Q) then
                p := FactorsInt(sz)[1];
                ea_a := LogInt(sz, p);
                ea_Ap := SubgroupNC(A, List(GeneratorsOfGroup(A), g -> g^p));
                ea_homV := NaturalHomomorphismByNormalSubgroup(A, ea_Ap);
                ea_V := Range(ea_homV);
                ea_pcgsV := Pcgs(ea_V);
                ea_rk := Length(ea_pcgsV);
                if ea_rk >= ea_a then
                    for ea_W in Subspaces(GF(p)^ea_rk, ea_rk - ea_a) do
                        ea_U := SubgroupNC(ea_V, List(BasisVectors(Basis(ea_W)),
                            ea_row -> Product([1..ea_rk],
                                ea_i -> ea_pcgsV[ea_i]^IntFFE(ea_row[ea_i]))));
                        Add(result, rec(
                            K := PreImage(abel_hom, PreImage(ea_homV, ea_U)),
                            qsize := q_size, qid := q_qid));
                    od;
                fi;
                if Runtime() - t_q >= 100 then
                    Print("    [enum/abel_early/elab] |H|=", Size(H), " Q=", q_qid,
                          " p=", p, " a=", ea_a, " rk=", ea_rk,
                          " in ", Runtime() - t_q, "ms\n");
                fi;
                continue;
            fi;
            # General (non-elementary) abelian Q (C4, C4xC2, C8, C6, C2xC4, ...):
            # the kernels K <= A with A/K =~ Q are exactly the index-|Q| subgroups
            # of the small abelianization A whose quotient is =~ Q.  Enumerate them
            # from A's (memoized) subgroup lattice -- far faster than GQuotients(A,Q)
            # for the mixed-cyclic glue quotients that dominate [8,*] / degree-8
            # builds (measured C4xC2 on |A|=96: GQuotients 8.7 s -> AllSubgroups
            # 62 ms; this is the 6/6 abel_early regression for non-elementary Q).
            # Count-neutral: identical kernel set, verified vs GQuotients.  Guarded
            # by A's elementary rank so the lattice can't blow up (rank<=5 ~0.7 s,
            # rank 7 ~82 s); rare high-rank non-elementary cases fall back to
            # GQuotients (no worse than before, and usually empty there).
            # Iso test via AbelianInvariants, NOT IdGroup: for abelian groups the
            # invariants are a complete isomorphism invariant, defined at EVERY
            # order — IdGroup raises a hard GAP error for orders 512/1024/1536/
            # >2000 (verified on GAP 4.15.1), which forced-large abelian glue
            # quotients (lane 2, unbounded size) can reach.  Also cheaper.
            ea_rk := Maximum(Concatenation([0], List(Set(FactorsInt(Size(A))),
                         p -> Number(AbelianInvariants(A), x -> x mod p = 0))));
            if ea_rk <= 5 then
                ea_qid := AbelianInvariants(Q);
                for ea_U in AllSubgroups(A) do
                    if Index(A, ea_U) = sz and AbelianInvariants(A / ea_U) = ea_qid then
                        Add(result, rec(K := PreImage(abel_hom, ea_U),
                                        qsize := q_size, qid := q_qid));
                    fi;
                od;
                if Runtime() - t_q >= 100 then
                    Print("    [enum/abel_early/lattice] |H|=", Size(H), " Q=", q_qid,
                          " rk=", ea_rk, " in ", Runtime() - t_q, "ms\n");
                fi;
                continue;
            fi;
            for epi in GQuotients(A, Q) do
                Add(result, rec(K := PreImage(abel_hom, Kernel(epi)),
                                qsize := q_size, qid := q_qid));
            od;
            if Runtime() - t_q >= 100 then
                Print("    [enum/abel_early] |H|=", Size(H), " Q=", q_qid,
                      " in ", Runtime() - t_q, "ms\n");
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
               and Size(H) <= 65536 and Size(Q) <= 1024 then
                # |H| gate raised 4096 -> 65536 (2026-05-31): a degree-16 RIGHT
                # group like TG(16,1686) has |H|=6144 > 4096, so it was EXCLUDED
                # from this fast direct-GQuotients path and fell through to the
                # SolvableQuotientKernelRecords ladder -- which stalled 37+ min on
                # a single [4,5]_[16,*] job ([16,4] slowdown vs legacy).  Measured
                # DirectGQuotients on |H|=6144: S4=1.6s, all other Q <150ms (~2s
                # total vs the ladder's 30+ min).  The real cost guard is the
                # small |Q| (<=1024, here LEFT-bounded to <=24); raising the |H|
                # bound just lets these moderate degree-16/17 RIGHT groups use the
                # fast path.  Count-neutral: GQuotients kernels == ladder kernels.
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
            # q_qid (SafeId) in the prints, not IdGroup(Q)[2]: Q reaching this
            # fallback can have an order where group identification is
            # unavailable (512/1024/1536/>2000) and IdGroup would Error.
            Print("    [enum/fallback/GQuot] BEGIN |H|=", Size(H),
                  " Q=", q_qid, "\n");
            Append(result, List(Set(List(GQuotients(H, Q), Kernel)),
                                K -> rec(K := K, qsize := q_size, qid := q_qid)));
            Print("    [enum/fallback/GQuot] END   |H|=", Size(H),
                  " Q=", q_qid, " in ",
                  Runtime() - t_q, "ms\n");
        fi;
    od;
    # (2026-06-09) Exact-iso CHOKEPOINT filter for unsafe-qid records.  The
    # coarse `SafeId(H/K) = q_qid` accept-filters above (PrimeKernel /
    # SmallKernel / NonAbelianSimple / AlmostSimple / solvable ladder) can
    # return kernels whose quotient is a DIFFERENT iso-class that merely
    # shares the coarse id (legitimate since the 2026-05-26 QTypeIsNew fix
    # keeps colliding unsafe Q-types as distinct coverage entries; e.g.
    # SafeId(A8) = SafeId(PSL(3,4)) = [20160,1,[],[20160]], so on
    # H = A8 x PSL(3,4) a request for the A8 class also coarse-matched the
    # PSL(3,4)-quotient kernel).  Returning those breaks the cache invariant
    # `entry.orbits == classes recorded in computed_q_ids/_unsafe_reps`:
    # the entry silently carries UNREQUESTED-class orbits, and a later
    # ExtendHCacheEntry for that class re-enumerates and re-appends them --
    # the pair loop then counts/emits those orbits twice (silent OVERCOUNT).
    # Keep only records whose quotient is isomorphic to a REQUESTED Q.
    # Safe-qid records are exact by construction (IdGroup classifies), so
    # the IsomorphismGroups probe runs only on the rare unsafe records.
    if ForAny(result, kr -> kr.qid[2] = 1) then
        flt_unsafe_qs := Filtered(q_groups, Q -> SafeId(Q)[2] = 1);
        n_flt_before := Length(result);
        result := Filtered(result, function(kr)
            local QK;
            if kr.qid[2] = 0 then return true; fi;
            QK := H / kr.K;
            return ForAny(flt_unsafe_qs, Q -> SafeId(Q) = kr.qid
                          and IsomorphismGroups(QK, Q) <> fail);
        end);
        if Length(result) < n_flt_before then
            Print("    [enum/unsafe_iso_filter] |H|=", Size(H), " dropped ",
                  n_flt_before - Length(result),
                  " coarse-collision kernel(s) not isomorphic to any ",
                  "requested Q\n");
        fi;
    fi;
    return result;
end;

# Cut 3 dispatcher: splits q_groups into linear-supported and legacy.
# For supported qids (C_2, C_3, V_4, S_3, D_8), calls Stage A/B/C prototypes
# directly (produces orbit recs in the right format with K_H_gens +
# Stab_NH_KH_gens).  Returns the LINEAR orbit-recs as a list; caller is
# responsible for running the legacy path on the remaining q_groups.
_LinearOrbitsForSupportedQids := function(H, N_H, q_groups)
    local supported_qids, orbits, legacy_qs, Q, qid, sz, recs, sd_jobs,
          sd_e, sd_res;
    # Fail-safe: if USE_LINEAR_ORBITS isn't set to 1 (PRED_USE_LINEAR_ORBITS=0,
    # or an ad-hoc driver that never defines it), default to legacy.  All three
    # production drivers (GAP/BATCH/SUPER) set it and load the Stage A/B/C
    # prototypes, so this only trips on the explicit opt-out.
    if not IsBound(USE_LINEAR_ORBITS) or USE_LINEAR_ORBITS <> 1 then
        return rec(linear := [], legacy := q_groups);
    fi;
    supported_qids := [[2,0,[2,1]], [3,0,[3,1]], [4,0,[4,2]],
                       [6,0,[6,1]], [8,0,[8,3]]];
    orbits := [];
    legacy_qs := [];
    sd_jobs := [];
    for Q in q_groups do
        qid := SafeId(Q);
        sz := Size(Q);
        if qid = [2,0,[2,1]] then
            Append(orbits, LinearOrbitRecsCpa(H, N_H, 2, 1));
        elif qid = [3,0,[3,1]] then
            Append(orbits, LinearOrbitRecsCpa(H, N_H, 3, 1));
        elif qid = [4,0,[4,2]] then
            Append(orbits, LinearOrbitRecsCpa(H, N_H, 2, 2));
        elif qid = [6,0,[6,1]] then
            Append(orbits, LinearOrbitRecsS3(H, N_H));
        elif qid = [8,0,[8,3]] then
            Append(orbits, LinearOrbitRecsD8(H, N_H));
        elif USE_STAGE_D = 1 and StageDEntryForQid <> fail then
            # Stage D (2026-06-09): O_p-split glue family (D12, S4, C2xS4,
            # S3xS3, A4, ...).  Collect and run as ONE batch after the loop
            # so sibling targets share outer-layer and per-L module data.
            sd_e := StageDEntryForQid(qid);
            if sd_e <> fail then
                Add(sd_jobs, rec(Q := Q, entry := sd_e));
            else
                Add(legacy_qs, Q);
            fi;
        else
            Add(legacy_qs, Q);
        fi;
    od;
    if Length(sd_jobs) > 0 then
        sd_res := LinearOrbitRecsStageDMulti(H, N_H, sd_jobs);
        Append(orbits, sd_res.recs);
        # Hom-guard fallbacks re-run on the legacy path (count-neutral).
        Append(legacy_qs, sd_res.legacy);
    fi;
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
                # |Stab| = |N_H| / |orbit of K under N_H|.  Cheap from the
                # already-enumerated K_orbit; avoids fresh Schreier-Sims on
                # Stab later in the labelled-subgroup harvest.
                Stab_NH_KH_size := Size(N_H) / Length(K_orbit),
                qsize := q_size_v,
                qid := q_qid_v
            ));
        od;
    od;
    return orbits;
end;

CountSubsGroupLines := function(path)
    # Count the subgroup entries of a subs_*.g file WITHOUT Read()ing it --
    # Read would construct every Group object (seconds for 40k+ entries).
    # Both writers (write_subs_g / _subs_g_text) emit exactly one
    # `  Group(...)` line per subgroup; generator strings are permutation
    # lists and can never contain the substring "Group(".  Used by the
    # RIGHT-side completeness check so the cache-hit fast path stays cheap.
    local f, line, n;
    f := InputTextFile(path);
    if f = fail then return fail; fi;
    n := 0;
    line := ReadLine(f);
    while line <> fail do
        if PositionSublist(line, "Group(") <> fail then n := n + 1; fi;
        line := ReadLine(f);
    od;
    CloseStream(f);
    return n;
end;

EnsureHCacheComplete := function(cache, subs, amb, q_groups, path, label)
    # Self-heal an orphaned partial LEFT cache.  A force-killed cache build can
    # leave a partial cache FILE on disk while losing its RESUME_BUILD state, so
    # a later run reads it as if complete.  The on-disk cache covers a
    # deterministic PREFIX of `subs` (SUBGROUPS_*_RAW is built / checkpoint-saved
    # strictly in index order), so append the missing tail to cover every
    # subgroup.  Without this the pair loop iterates only Length(cache) LEFT
    # entries -> N_LEFT short -> SILENT UNDERCOUNT (the 2026-06-06 n=21 [3,2]xD8
    # undercount: 31705 of 42234 LEFT entries).  Mutates `cache`; re-saves to
    # `path` so the file self-heals for future loads.
    local hi, n0, nfull;
    n0 := Length(cache);
    nfull := Length(subs);
    if n0 > nfull then
        # An OVER-length cache cannot be healed: the prefix invariant is broken
        # (duplicated build-resume tail, or a regenerated/shorter source file).
        # Iterating it would count subgroups twice -> silent OVERCOUNT.  Fail
        # loudly instead; the operator deletes the cache file and the next run
        # rebuilds it.  (2026-06-09 review hardening.)
        Error("H_CACHE (", label, ") has ", n0, " entries but the source has ",
              nfull, " subgroups -- over-length/desynced cache; delete '",
              path, "' and re-run");
    fi;
    if n0 = nfull then return; fi;
    Print("WARNING ", label, ": partial H_CACHE ", n0, " < ", nfull,
          " subgroups -- completing tail (orphaned partial cache from an ",
          "interrupted build)\n");
    for hi in [n0 + 1 .. nfull] do
        Add(cache, ComputeHCacheEntry(subs[hi], amb, q_groups));
    od;
    if path <> "" then SaveHCacheList(path, cache); fi;
end;

ComputeHCacheEntry := function(H, S_M, q_groups)
    local N_H, k_recs, t0, t_norm, t_orbit, result_orbits,
          _linear_split, _n_linear;
    t0 := Runtime();
    N_H := Normalizer(S_M, H);
    t_norm := Runtime() - t0;
    # Cut 3: route supported qids ({C_2, C_3, V_4, S_3, D_8}) through Stage
    # A/B/C linear orbit math (N_H-orbit recs produced directly, skipping the
    # enumerate-all-kernels-then-Orbits(N_H,...) dedup).  Remaining qids fall
    # back to the legacy path.  When USE_LINEAR_ORBITS<>1,
    # _LinearOrbitsForSupportedQids returns everything as legacy (no behavior
    # change).  Mirrors ExtendHCacheEntry's Cut-3 dispatch; this builder serves
    # both LEFT (W_ML) and the multi-block RIGHT cluster (W_MR/S_MR), so the
    # speedup (~2.5x where orbit-dedup of C_2/C_3/V_4/S_3/D_8 kernels dominates)
    # applies symmetrically to both sides.
    t0 := Runtime();
    _linear_split := _LinearOrbitsForSupportedQids(H, N_H, q_groups);
    result_orbits := ShallowCopy(_linear_split.linear);
    _n_linear := Length(_linear_split.linear);
    if Length(_linear_split.legacy) > 0 then
        k_recs := _EnumerateNormalsForQGroups(H, _linear_split.legacy);
        Append(result_orbits, _ComputeOrbitRecsFromKs(H, N_H, k_recs));
    else
        k_recs := [];
    fi;
    t_orbit := Runtime() - t0;
    if t_norm + t_orbit >= 1000 then
        Print("    [ComputeHCacheEntry] |H|=", Size(H),
              " norm=", t_norm, "ms enum+orbit=", t_orbit,
              "ms (n_linear_orbits=", _n_linear,
              " n_legacy_kernels=", Length(k_recs), ")\n");
    fi;
    return rec(
        H_gens := GeneratorsOfGroup(H),
        N_H_gens := GeneratorsOfGroup(N_H),
        computed_q_ids := QIdsOfGroups(q_groups),
        computed_q_unsafe_reps := _UnsafeQReps(q_groups),
        orbits := result_orbits
    );
end;

ComputeHDataDirect := function(H, S_M, q_groups)
    local N_H, k_recs, t0, t_norm, t_enum, t_orbit, res, hom_triv,
          kbyqid, kr, qid_str, key, bucket, normals, K_orbit, K_H,
          Stab, i, _linear_split, _n_linear, lr, K_lin, Stab_lin;
    t0 := Runtime();
    N_H := Normalizer(S_M, H);
    t_norm := Runtime() - t0;
    # Cut 3: route supported qids ({C_2, C_3, V_4, S_3, D_8}) through the Stage
    # A/B/C linear orbit math (mirrors ComputeHCacheEntry / ExtendHCacheEntry);
    # only the remaining qids hit the legacy enumerate-then-Orbits(N_H) path.
    # When USE_LINEAR_ORBITS<>1, _LinearOrbitsForSupportedQids returns
    # everything as legacy, so the behaviour is unchanged.
    # RESTORED 2026-06-06: the 2026-06-05 revert blamed this dispatch for the n=20
    # [4,2]_[8,*] undercount (-78254 -> 88,171,109 vs correct 88,249,363), but the
    # true cause was a STALE reused H-cache (coverage tag in flux across the QPRUNE
    # window), NOT this integration -- a fresh --h-cache rebuild gives the correct
    # 88,249,363 with linear ON ([4,2]_[8,29]_[8,35]=19694), and the kernel-diff
    # test proved per-qid linear orbit counts == legacy exactly.  See memory
    # hcache_reuse_across_code_changes_unsafe.  Always validate with a FRESH cache.
    t0 := Runtime();
    _linear_split := _LinearOrbitsForSupportedQids(H, N_H, q_groups);
    _n_linear := Length(_linear_split.linear);
    k_recs := _EnumerateNormalsForQGroups(H, _linear_split.legacy);
    t_enum := Runtime() - t0;

    res := rec(H := H, N := N_H,
        H_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_H := fail, shifted_H_gens_noid := fail,
        orbits := []);
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N_H, Stab_size := Size(N_H), AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
        K_gens_noid := Filtered(GeneratorsOfGroup(H), g -> g <> ()),
        shifted_K_gens_noid := fail, c2_rep := fail, shifted_c2_rep := fail,
        H_ref := H));

    t0 := Runtime();
    # Cut 3: convert the linear orbit recs (C_2/C_3/V_4/S_3/D_8) directly into
    # the H2DATA orbit-rec shape, skipping the enumerate-then-Orbits(N_H) dedup.
    # Added BEFORE the byqid index is built below so they are indexed too.
    for lr in _linear_split.linear do
        K_lin := SubgroupNC(H, lr.K_H_gens);
        Stab_lin := SubgroupNC(N_H, lr.Stab_NH_KH_gens);
        Add(res.orbits, rec(K := K_lin, hom := fail, Q := fail,
            qsize := lr.qsize, qid := lr.qid,
            Stab := Stab_lin,
            Stab_size := lr.Stab_NH_KH_size,
            AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
            K_gens_noid := Filtered(lr.K_H_gens, g -> g <> ()),
            shifted_K_gens_noid := fail, c2_rep := fail, shifted_c2_rep := fail,
            H_ref := H));
    od;
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
                Stab := Stab,
                # |Stab| = |N_H| / |orbit of K under N_H| -- free from K_orbit.
                Stab_size := Size(N_H) / Length(K_orbit),
                AutQ := fail, A_gens := [], full_aut := fail, iso_to_can := fail, dc_cache := fail, shifted_hom := fail,
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
              "ms orbit=", t_orbit, "ms (n_linear_orbits=", _n_linear,
              " n_legacy_kernels=", Length(k_recs), ")\n");
    fi;
    return res;
end;

ExtendHCacheEntry := function(entry, S_M, additional_q_groups)
    local H, N_H, current, entry_unsafe_reps, Q_K, missing_groups, k_recs,
          new_orbits, all_normals, K, qid_K, _linear_split, _linear_t0,
          _linear_t1;
    if entry.computed_q_ids = fail then return entry; fi;
    H := SafeGroup(entry.H_gens, S_M);
    N_H := SafeGroup(entry.N_H_gens, S_M);
    current := entry.computed_q_ids;
    entry_unsafe_reps := _UnsafeRepsOf(entry);
    if additional_q_groups = fail then
        # Extend to FULL coverage: enumerate ALL normals; add only the K's
        # whose quotient iso-class is not already in current.
        all_normals := Filtered(NormalSubgroups(H), K -> K <> H);
        k_recs := [];
        for K in all_normals do
            Q_K := H/K;
            if not QTypeCovered(current, entry_unsafe_reps, Q_K) then
                Add(k_recs, rec(K := K, qsize := Size(H)/Size(K),
                                qid := SafeId(Q_K)));
            fi;
        od;
        new_orbits := _ComputeOrbitRecsFromKs(H, N_H, k_recs);
        Append(entry.orbits, new_orbits);
        entry.computed_q_ids := fail;
        return entry;
    fi;
    missing_groups := QGroupsMissing(current, entry_unsafe_reps, additional_q_groups);
    if Length(missing_groups) = 0 then return entry; fi;
    # Cut 3: route supported qids ({C_2, C_3, V_4, S_3, D_8}) through Stage
    # A/B/C (linear orbit math; orbit recs returned directly).  Remaining qids
    # go through the legacy enumerate-then-orbit path.  When USE_LINEAR_ORBITS=0,
    # all qids go to legacy (no behavior change).
    _linear_t0 := Runtime();
    _linear_split := _LinearOrbitsForSupportedQids(H, N_H, missing_groups);
    _linear_t1 := Runtime();
    if Length(_linear_split.linear) > 0 then
        Append(entry.orbits, _linear_split.linear);
    fi;
    if Length(_linear_split.legacy) > 0 then
        # NOTE (2026-06-09): _EnumerateNormalsForQGroups now guarantees
        # exactly-requested kernels (its end-of-function exact-iso filter for
        # unsafe-qid records), so the orbits appended here are precisely the
        # missing classes recorded in computed_q_ids/computed_q_unsafe_reps
        # below -- a later extension for a collision-sibling cannot duplicate.
        k_recs := _EnumerateNormalsForQGroups(H, _linear_split.legacy);
        new_orbits := _ComputeOrbitRecsFromKs(H, N_H, k_recs);
        Append(entry.orbits, new_orbits);
    fi;
    UniteSet(entry.computed_q_ids, QIdsOfGroups(missing_groups));
    # Keep computed_q_unsafe_reps in sync (only for new-format entries that
    # already carry the field; legacy entries stay on coarse-qid coverage).
    if IsBound(entry.computed_q_unsafe_reps) then
        Append(entry.computed_q_unsafe_reps, _UnsafeQReps(missing_groups));
    fi;
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

# === Framed (windowable) H-cache format =======================================
# Layout (written when FRAMED_CACHE=1):
#   line 1 : # coverage_qids: <tag>;          (same header as monolithic)
#   line 2 : # hcache_framed: count=<N>
#   lines 3..N+2 : one String(entry) per line (String() never wraps -> 1/line)
# Sidecar <path>.idx : HCACHE_OFFSETS := [ o_1,..,o_N, o_{N+1} ];  byte offset of
#   each entry's line start (o_{N+1}=EOF).  ASCII content + '\n'=1 byte => exact.
# A pair-loop resume reads only its slice via SeekPositionStream (GetHCacheEntry);
# build/extend full-load via ReadHCacheFramedFull.  Validated in _proto/bench_*.py.
SaveHCacheFramed := function(path, h_cache, header)
    local fullhdr, tmp, idxtmp, stream, off, offs, k, s, rnd;
    rnd := Concatenation(String(Runtime()), ".", String(Random([1..1000000])));
    fullhdr := Concatenation(header, "# hcache_framed: count=",
                             String(Length(h_cache)),
                             " ver=", HCACHE_BUILD_VER, "\n");
    tmp := Concatenation(path, ".tmp.", rnd);
    stream := OutputTextFile(tmp, false);
    SetPrintFormattingStatus(stream, false);
    WriteAll(stream, fullhdr);
    off := Length(fullhdr);
    offs := [];
    for k in [1..Length(h_cache)] do
        Add(offs, off);
        s := String(h_cache[k]);
        WriteAll(stream, s);
        WriteAll(stream, "\n");
        off := off + Length(s) + 1;
    od;
    Add(offs, off);   # EOF sentinel
    CloseStream(stream);
    # Publish sidecar first, then the main file: a reader treats the cache as
    # framed only when the main file's marker AND the .idx are both present, and
    # OpenHCacheWindow cross-checks count= vs the sidecar length, so any torn
    # intermediate state falls back to a full read (never wrong data).
    idxtmp := Concatenation(path, ".idxtmp.", rnd);
    PrintTo(idxtmp, "HCACHE_OFFSETS := ", offs, ";\n");
    Exec(Concatenation("mv -f -- '", idxtmp, "' '", path, ".idx'"));
    Exec(Concatenation("mv -f -- '", tmp, "' '", path, "'"));
    # Verify the publish (Exec surfaces no return code): a silently-failed
    # mv would leave a stale same-count cache at the canonical path, which
    # downstream count checks alone cannot distinguish from ours.
    if ReadEntryCountFromFile(path) <> Length(h_cache) then
        Error("SaveHCacheFramed: publish verification failed at ", path,
              " (mv failed silently?)");
    fi;
end;

# True iff path is a framed cache: line 2 marker present AND sidecar exists.
IsFramedCacheFile := function(path)
    local f, l1, l2, prefix;
    if not IsExistingFile(path) then return false; fi;
    # Detect framed by the .g marker ALONE -- do NOT require the .idx, which can
    # be transiently absent during a save's non-atomic mv (Cygwin unlink+rename).
    # A framed .g without its .idx still reads correctly via ReadHCacheFramedFull
    # (full load); only the windowed path needs the .idx, and OpenHCacheWindow
    # falls back when it's absent.  (Previously a missing .idx here made callers
    # mis-read a framed .g as monolithic -> crash.)
    f := InputTextFile(path);
    if f = fail then return false; fi;
    l1 := ReadLine(f);
    l2 := ReadLine(f);
    CloseStream(f);
    prefix := "# hcache_framed:";
    return l2 <> fail and Length(l2) >= Length(prefix)
           and l2{[1..Length(prefix)]} = prefix;
end;

ReadEntryCountFromFile := function(path)
    # Cheap on-disk H-cache entry count from the line-2 header:
    #   framed     : "# hcache_framed: count=<N>[ ver=<V>]"
    #   monolithic : "# hcache_count: <N>[ ver=<V>]"
    # Returns fail when the file is missing or carries no count header
    # (legacy monolithic file written before the count-aware save).
    # The optional ver= stamp (written since 2026-07-02) is ENFORCED here:
    # a cache produced by a different HCACHE_BUILD_VER carries entries whose
    # content the current enumeration code would compute differently, and
    # silently reusing it is the stale-cache undercount class (see the
    # hcache_reuse_across_code_changes lesson).  Legacy stamp-less files are
    # grandfathered (all pre-stamp content is ver-1 compatible).
    local f, l1, l2, prefix, payload, p, sp, vtok;
    if not IsExistingFile(path) then return fail; fi;
    f := InputTextFile(path);
    if f = fail then return fail; fi;
    l1 := ReadLine(f); l2 := ReadLine(f);
    CloseStream(f);
    if l2 = fail then return fail; fi;
    for prefix in ["# hcache_framed: count=", "# hcache_count: "] do
        if Length(l2) >= Length(prefix) and l2{[1..Length(prefix)]} = prefix then
            payload := l2{[Length(prefix)+1..Length(l2)]};
            p := Length(payload);
            while p > 0 and payload[p] in [' ', '\n', '\r', '\t'] do p := p - 1; od;
            if p = 0 then return fail; fi;
            payload := payload{[1..p]};
            sp := Position(payload, ' ');
            if sp <> fail then
                vtok := payload{[sp+1..Length(payload)]};
                payload := payload{[1..sp-1]};
                if Length(vtok) > 4 and vtok{[1..4]} = "ver="
                   and vtok{[5..Length(vtok)]} <> HCACHE_BUILD_VER then
                    Error("H-cache at ", path, " was built by enum version ",
                          vtok{[5..Length(vtok)]}, " but this code is version ",
                          HCACHE_BUILD_VER, ".  Entry content is not ",
                          "compatible across versions -- delete the cache ",
                          "file (or use a fresh --h-cache dir) and rerun.");
                fi;
            fi;
            return Int(payload);
        fi;
    od;
    return fail;
end;

# Full-load a framed cache into a list (build/extend path).  Slurp body + one
# EvalString -- same parse cost as a monolithic Read; entries normalized by caller.
ReadHCacheFramedFull := function(path)
    local f, content, p1, p2, body, n, entries, hdr_count;
    f := InputTextFile(path);
    content := ReadAll(f);
    CloseStream(f);
    p1 := Position(content, '\n');
    if p1 = fail then return []; fi;
    p2 := Position(content, '\n', p1);
    if p2 = fail then return []; fi;
    body := content{[p2+1..Length(content)]};
    n := Length(body);
    while n > 0 and body[n] in [' ', '\n', '\r', '\t'] do n := n - 1; od;
    if n = 0 then return []; fi;
    body := body{[1..n]};
    entries := EvalString(Concatenation("[", ReplacedString(body, "\n", ","), "]"));
    # (2026-06-09) Cross-check the parsed entry count against the line-2
    # `count=` header: a framed file truncated at an exact line boundary
    # (external copy/backup truncation) parses cleanly but short.  Warn only
    # -- downstream loaders (EnsureHCacheComplete on LEFT, the RIGHT-side
    # completeness check) verify against the subs list and self-heal.
    hdr_count := ReadEntryCountFromFile(path);
    if hdr_count <> fail and hdr_count <> Length(entries) then
        Print("WARNING ReadHCacheFramedFull: parsed ", Length(entries),
              " entries but header says count=", hdr_count, " at ", path,
              " (truncated framed cache?)\n");
    fi;
    return entries;
end;

# Format-agnostic full load of an H-cache file into a list (framed or monolithic).
# Replaces a bare `Read(path)` that set the global H_CACHE; callers assign the
# return to H_CACHE.  (Monolithic Read sets global H_CACHE, which we return.)
ReadHCacheAuto := function(path)
    ReadEntryCountFromFile(path);   # side effect: Errors on a ver= mismatch
    if IsFramedCacheFile(path) then return ReadHCacheFramedFull(path); fi;
    Read(path);
    return H_CACHE;
end;

# Open a framed cache for windowed (on-demand per-entry) reads.  Sets HCW_* and
# returns true; returns false (caller must full-load) on a torn write where the
# header count= disagrees with the sidecar length.
OpenHCacheWindow := function(path)
    local f, l1, l2, prefix, marker_count, k;
    if not IsExistingFile(Concatenation(path, ".idx")) then return false; fi;
    Read(Concatenation(path, ".idx"));   # -> HCACHE_OFFSETS
    if not IsBound(HCACHE_OFFSETS) or HCACHE_OFFSETS = fail
       or Length(HCACHE_OFFSETS) < 1 then return false; fi;
    HCW_OFFSETS := HCACHE_OFFSETS;
    HCW_COUNT := Length(HCW_OFFSETS) - 1;
    # Require the framed marker specifically (a monolithic file paired with
    # a stale sidecar must not window), then reuse ReadEntryCountFromFile
    # for the count parse -- it also ENFORCES the ver= stamp (Errors loudly
    # on an enum-version mismatch rather than falling back to a full read
    # of stale entries).
    f := InputTextFile(path);
    if f = fail then return false; fi;
    l1 := ReadLine(f); l2 := ReadLine(f); CloseStream(f);
    prefix := "# hcache_framed: count=";
    if l2 = fail or Length(l2) < Length(prefix)
       or l2{[1..Length(prefix)]} <> prefix then return false; fi;
    marker_count := ReadEntryCountFromFile(path);
    if marker_count = fail or marker_count <> HCW_COUNT then return false; fi;
    HCW_STREAM := InputTextFile(path);
    if HCW_STREAM = fail then return false; fi;
    # Probe-parse the first and last entries.  The publish is two separate
    # `mv`s (.idx then .g, Exec rc unchecked), so a torn or silently-failed
    # publish can leave a NEW sidecar over an OLD same-count .g (or vice
    # versa) that passes the count cross-check while its offsets point
    # mid-line.  A failed probe returns false -> callers fall back to the
    # full read (ReadHCacheFramedFull ignores the sidecar), never trusting
    # misaligned windowed seeks.
    if HCW_COUNT > 0 then
        for k in Set([1, HCW_COUNT]) do
            SeekPositionStream(HCW_STREAM, HCW_OFFSETS[k]);
            if not _StreamHCacheValidLine(ReadLine(HCW_STREAM)) then
                CloseStream(HCW_STREAM);
                HCW_STREAM := fail;
                return false;
            fi;
        od;
    fi;
    return true;
end;

# Read+reconstruct one LEFT entry on demand (seek to its byte offset).  Mirrors
# the per-load NormalizeHCacheEntry the full path applies.
GetHCacheEntry := function(i)
    local line, e;
    SeekPositionStream(HCW_STREAM, HCW_OFFSETS[i]);
    line := ReadLine(HCW_STREAM);
    e := EvalString(Chomp(line));
    NormalizeHCacheEntry(e);
    return e;
end;

CloseHCacheWindow := function()
    if HCW_STREAM <> fail then CloseStream(HCW_STREAM); HCW_STREAM := fail; fi;
end;

# Probe a sample of windowed entries to verify every entry actually carries the
# requested q-coverage.  Guards EPOCH-1 (non-resume) windowing against a
# HETEROGENEOUS cache from a crashed mid-extend: ComputeCoverageTag UNIONs the
# per-entry computed_q_ids, so the file's coverage header OVER-CLAIMS when a
# partial extend left a short tail -- the header/coverage-tag check alone would
# accept it and the windowed pair loop would silently undercount those entries.
# Build and extend fill entries strictly in index order, so any shortfall is a
# SUFFIX => the LAST entry is the definitive witness; we also sample the first
# entry and an even spread for defense in depth against non-suffix corruption.
# O(sample) seeks (~9 EvalStrings) -- negligible vs the full load it replaces.
# Returns false on ANY probed entry missing a requested qid, so the caller falls
# back to the self-healing full load (per-entry scan + EnsureHCacheComplete +
# extend).  Requires the window to be OPEN (OpenHCacheWindow set HCW_*).
WindowedCacheUniformlyCovered := function(q_groups)
    local n, idxs, i, e, miss;
    n := HCW_COUNT;
    if n <= 0 then return true; fi;
    idxs := Set([1, n]);
    for i in [1..7] do
        AddSet(idxs, Maximum(1, Minimum(n, QuoInt(i * n, 8))));
    od;
    for i in idxs do
        e := GetHCacheEntry(i);
        miss := QGroupsMissing(e.computed_q_ids, _UnsafeRepsOf(e), q_groups);
        if miss = fail or Length(miss) > 0 then
            return false;
        fi;
    od;
    return true;
end;

SaveHCacheList := function(path, h_cache)
    local tmp, mem_tag, disk_tag, header, header_stream, mem_n, disk_n;
    # Coverage-tagged save: overwrite iff in-memory cache strictly extends
    # (or equals) the on-disk coverage.  Header line is parsed without
    # touching the body, so the check is cheap on multi-MB files.  Files
    # without a header (legacy) always trigger overwrite, which gives them
    # a header on first save.  IsValidCacheFile guards against skipping
    # when the on-disk file is corrupt: we'd otherwise refuse to overwrite
    # a truncated cache and leave readers crashing forever.
    #
    # (2026-06-09) COUNT-AWARE rules on top of the coverage rules.  The cache
    # file is shared across workers and roles (LEFT builds soft-save PARTIALS
    # to the same path other jobs load as RIGHT), and coverage tags alone
    # cannot distinguish a partial from a complete cache (a partial's entries
    # each carry the full q-coverage).  Two additional invariants:
    #   * never SKIP a save when memory holds MORE entries than the known
    #     on-disk count (a completed build/heal must replace a partial);
    #   * never CLOBBER a known-longer on-disk file with a shorter list (a
    #     concurrent partial soft-save must not replace a complete cache).
    # Files with no count header (legacy) keep the pre-2026-06-09 semantics
    # and gain a count header on their next overwrite.
    mem_tag := ComputeCoverageTag(h_cache);
    disk_tag := ReadCoverageTagFromFile(path);
    mem_n := Length(h_cache);
    disk_n := ReadEntryCountFromFile(path);
    if not (disk_n <> fail and mem_n > disk_n) then
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
        if disk_n <> fail and mem_n < disk_n and IsValidCacheFile(path) then
            # Refuse to clobber a longer (more complete) on-disk cache with a
            # shorter list: this is the partial-soft-save-over-complete race.
            # Losing our per-entry extend progress on a shorter prefix is a
            # perf cost; losing the disk file's tail entries is a correctness
            # risk (N short -> silent undercount on the next reader).
            Print("[SaveHCacheList] SKIP: in-memory ", mem_n,
                  " entries < on-disk ", disk_n, " at ", path, "\n");
            return;
        fi;
    fi;
    if mem_tag = fail then
        header := "# coverage_qids: fail;\n";
    else
        header := Concatenation("# coverage_qids: ", String(mem_tag), ";\n");
    fi;
    if FRAMED_CACHE = 1 then
        SaveHCacheFramed(path, h_cache, header);
        return;
    fi;
    # Monolithic write (default).  Drop any stale framed sidecar so a later
    # windowed read won't pair this monolithic file with an out-of-date .idx.
    if IsExistingFile(Concatenation(path, ".idx")) then
        RemoveFile(Concatenation(path, ".idx"));
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
    # Line 2 = "# hcache_count: N" (comments are ignored by Read), so
    # ReadEntryCountFromFile can count-check without touching the body.
    header_stream := OutputTextFile(tmp, false);
    WriteAll(header_stream, header);
    WriteAll(header_stream, Concatenation("# hcache_count: ",
                                          String(mem_n),
                                          " ver=", HCACHE_BUILD_VER, "\n"));
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
    # Framed cache: validated cheaply by the marker + existing sidecar (the
    # count= vs sidecar-length cross-check is done in OpenHCacheWindow).  Avoids
    # ReadAll-ing a multi-GB file just to validate.
    if IsFramedCacheFile(path) then return true; fi;
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

# === Streaming H-cache build (PRED_STREAM_HCACHE_BUILD) ========================
# O(1)-memory fresh LEFT-cache build: each entry is String()-serialized and
# appended to a process-private <path>.building.<BUILD_TOKEN> file (framed
# layout, header included) the moment it is computed, with its byte offset
# appended to <bpath>.idx (one decimal per line -- appendable, unlike the
# canonical single-statement HCACHE_OFFSETS format).  Durability = periodic
# close+reopen flushes; the legacy 30-min SaveHCacheList soft-saves (which
# re-serialized the WHOLE partial: ~75% of build wall-time and ~32 GB resident
# on the 250k-entry S21 monsters) do not exist on this path.  On completion
# the file is published onto <path> with the same idx-first atomic-mv
# discipline as SaveHCacheFramed and is byte-identical to what
# SaveHCacheFramed would have written for the same entries -- every existing
# reader (ReadHCacheAuto / OpenHCacheWindow / EnsureHCacheComplete / coverage
# tags) works unchanged, and the canonical path only ever carries COMPLETE
# caches (kills the partial-clobber / partial-as-RIGHT undercount hazard at
# the source instead of healing it downstream).
#
# Resume: a .building file carrying our BUILD_TOKEN (left by a previous epoch
# of this worker, or claimed for us by the Python wrapper's
# _claim_stale_building after a ver+count+staleness check on a dead worker's
# orphan) is adopted -- the offset sidecar is reconciled against the .g bytes
# (sidecar-ahead offsets dropped, .g-ahead lines re-indexed, any partial tail
# truncated via Cygwin `truncate`; stdio flush ordering between the two
# streams is not synchronized across a crash, so both directions occur), and
# the build continues at the first missing entry.  Lines are only trusted if
# they end in '\n' AND EvalString cleanly.  A header mismatch (different
# coverage tag / source count / HCACHE_BUILD_VER) discards the file: never mix
# entries computed by different enumeration code or against a different Q-set
# (the hcache_reuse_across_code_changes lesson).

# A complete, parseable entry line: must end in '\n' and EvalString cleanly.
# BreakOnError is dropped around the probe: a syntax error inside EvalString
# raises Error("Could not evaluate string"), and with BreakOnError=true that
# enters the break loop (= session death non-interactively) DESPITE the
# CALL_WITH_CATCH.  Scoped save/restore so production Errors elsewhere keep
# their die-loudly semantics (profile_slow_combo.py precedent).
_StreamHCacheValidLine := function(line)
    local r, prev;
    if line = fail or Length(line) = 0 or line[Length(line)] <> '\n' then
        return false;
    fi;
    prev := BreakOnError;
    BreakOnError := false;
    r := CALL_WITH_CATCH(EvalString, [Chomp(line)]);
    BreakOnError := prev;
    return r[1] = true;
end;

# Guard against a false claim of a LIVE builder's file: if another worker
# renamed our .building away (claim = rename), our next append re-creates an
# empty header-less file -- detect that here (cheap: two ReadLines) and die
# loudly BEFORE any corrupt bytes can be published.  The claimer owns the
# renamed file; aborting is correct, not data loss.
_StreamBuildingHeaderOk := function(bpath, header)
    local f, l1, l2;
    if not IsExistingFile(bpath) then return false; fi;
    f := InputTextFile(bpath);
    if f = fail then return false; fi;
    l1 := ReadLine(f);
    l2 := ReadLine(f);
    CloseStream(f);
    return l1 <> fail and l2 <> fail and Concatenation(l1, l2) = header;
end;

BuildHCacheStreaming := function(subs, amb, q_groups, path, label,
                                 ckpt_check, ckpt_quit)
    # When the global STREAM_EXTEND_FROM = fail, compute each entry fresh
    # (ComputeHCacheEntry).  When it is a <path>, read each OLD entry from that
    # framed cache (in index order, O(1) memory) and ExtendHCacheEntry it to
    # q_groups instead of recomputing -- so a multi-GB cache is extended without
    # ever full-loading it (the extend full-load was a 40 GB+ balloon; this
    # bounds it to one entry at a time).  A global avoids changing the 3
    # fresh-build callers (which pass no extend arg).
    local n_expected, tag, header, bpath, ipath, ihdr, n_done, offs, write_pos,
          gstream, istream, hi, s, f, l1, l2, line, k, last_flush,
          last_flush_hi, last_hb, last_hb_count, disk_n, disk_tag, do_publish,
          rnd, idxtmp, adopt_ok, extend_stream, ee, emiss;
    n_expected := Length(subs);
    tag := QIdsOfGroups(q_groups);
    if tag = fail then
        header := "# coverage_qids: fail;\n";
    else
        header := Concatenation("# coverage_qids: ", String(tag), ";\n");
    fi;
    # Identical to the SaveHCacheList+SaveHCacheFramed header for a fresh
    # build: every ComputeHCacheEntry below sets computed_q_ids :=
    # QIdsOfGroups(q_groups), so ComputeCoverageTag(entries) = this tag.
    header := Concatenation(header, "# hcache_framed: count=",
                            String(n_expected),
                            " ver=", HCACHE_BUILD_VER, "\n");
    bpath := Concatenation(path, ".building.", BUILD_TOKEN);
    ipath := Concatenation(bpath, ".idx");
    ihdr := Concatenation("# hcache_building: ver=", HCACHE_BUILD_VER,
                          " count=", String(n_expected), "\n");
    n_done := 0;
    offs := [];
    write_pos := Length(header);
    if IsExistingFile(bpath) and IsExistingFile(ipath) then
        # ---- adopt a previous epoch's / claimed orphan's partial ----
        adopt_ok := true;
        f := InputTextFile(ipath);
        line := ReadLine(f);
        if line = fail or line <> ihdr then
            adopt_ok := false;       # stale ver or different source count
        else
            line := ReadLine(f);
            while line <> fail do
                k := Int(Chomp(line));
                if k = fail then break; fi;    # partial garbage tail
                Add(offs, k);
                line := ReadLine(f);
            od;
        fi;
        CloseStream(f);
        if adopt_ok then
            f := InputTextFile(bpath);
            l1 := ReadLine(f);
            l2 := ReadLine(f);
            if l1 = fail or l2 = fail or Concatenation(l1, l2) <> header then
                # foreign coverage tag (another batch's Q-set) or count drift
                adopt_ok := false;
                CloseStream(f);
            else
                # Drop sidecar-ahead offsets: keep only offsets that point at
                # a complete, parseable line.
                while Length(offs) > 0 do
                    SeekPositionStream(f, offs[Length(offs)]);
                    if _StreamHCacheValidLine(ReadLine(f)) then break; fi;
                    Remove(offs);
                od;
                if Length(offs) > 0 then
                    SeekPositionStream(f, offs[Length(offs)]);
                    line := ReadLine(f);
                    write_pos := offs[Length(offs)] + Length(line);
                else
                    write_pos := Length(header);
                fi;
                # Re-index complete .g-ahead lines the sidecar missed.
                SeekPositionStream(f, write_pos);
                line := ReadLine(f);
                while Length(offs) < n_expected
                      and _StreamHCacheValidLine(line) do
                    Add(offs, write_pos);
                    write_pos := write_pos + Length(line);
                    line := ReadLine(f);
                od;
                CloseStream(f);
                n_done := Length(offs);
                # Truncate any partial/unvalidated tail so appends resume at a
                # clean entry boundary.
                Exec(Concatenation("truncate -s ", String(write_pos),
                                   " -- '", bpath, "'"));
                # Regenerate the sidecar to exactly mirror the kept prefix.
                istream := OutputTextFile(ipath, false);
                SetPrintFormattingStatus(istream, false);
                WriteAll(istream, ihdr);
                for k in offs do
                    WriteAll(istream, String(k));
                    WriteAll(istream, "\n");
                od;
                CloseStream(istream);
                Print("  [", label, "] STREAM-BUILD: adopted .building with ",
                      n_done, "/", n_expected, " entries\n");
            fi;
        fi;
        if not adopt_ok then
            Print("  [", label, "] STREAM-BUILD: discarding stale .building ",
                  "(ver/count/coverage mismatch)\n");
            RemoveFile(bpath);
            RemoveFile(ipath);
            offs := [];
            n_done := 0;
            write_pos := Length(header);
        fi;
    fi;
    if n_done = 0 then
        gstream := OutputTextFile(bpath, false);
        SetPrintFormattingStatus(gstream, false);
        WriteAll(gstream, header);
        istream := OutputTextFile(ipath, false);
        SetPrintFormattingStatus(istream, false);
        WriteAll(istream, ihdr);
    else
        gstream := OutputTextFile(bpath, true);
        SetPrintFormattingStatus(gstream, false);
        istream := OutputTextFile(ipath, true);
        SetPrintFormattingStatus(istream, false);
    fi;
    # Extend mode: open the OLD framed cache for sequential reads, positioned at
    # entry n_done+1 (seek via the old .idx so a resume skips the prefix in O(1)).
    extend_stream := fail;
    if STREAM_EXTEND_FROM <> fail then
        extend_stream := InputTextFile(STREAM_EXTEND_FROM);
        if n_done = 0 then
            ReadLine(extend_stream); ReadLine(extend_stream);   # skip 2 header lines
        else
            Read(Concatenation(STREAM_EXTEND_FROM, ".idx"));   # -> HCACHE_OFFSETS
            SeekPositionStream(extend_stream, HCACHE_OFFSETS[n_done + 1]);
        fi;
    fi;
    last_hb := Runtime();
    last_hb_count := n_done;
    last_flush := Runtime();
    last_flush_hi := n_done;
    for hi in [n_done + 1 .. n_expected] do
        if hi = n_done + 1 or hi - last_hb_count >= 500
           or Runtime() - last_hb >= 60000 then
            Print("  [", label, "] H_CACHE starting ", hi, "/", n_expected,
                  " |H|=", Size(subs[hi]), " (streaming)\n");
            last_hb := Runtime();
            last_hb_count := hi;
        fi;
        if STREAM_EXTEND_FROM = fail then
            s := String(ComputeHCacheEntry(subs[hi], amb, q_groups));
        else
            # Read the OLD entry hi (next line, in order) and extend it to
            # q_groups -- same ExtendHCacheEntry the full-load path uses, so the
            # result is identical, but only one entry is in memory at a time.
            ee := EvalString(Chomp(ReadLine(extend_stream)));
            NormalizeHCacheEntry(ee);
            emiss := QGroupsMissing(ee.computed_q_ids, _UnsafeRepsOf(ee), q_groups);
            if emiss = fail then
                ExtendHCacheEntry(ee, amb, q_groups);
            elif Length(emiss) > 0 then
                ExtendHCacheEntry(ee, amb, emiss);
            fi;
            s := String(ee);
        fi;
        WriteAll(gstream, s);
        WriteAll(gstream, "\n");
        WriteAll(istream, String(write_pos));
        WriteAll(istream, "\n");
        Add(offs, write_pos);
        write_pos := write_pos + Length(s) + 1;
        # Durability flush: close+reopen both streams (O(1)); this replaces
        # the legacy O(N)-re-serialization soft-save entirely.
        if hi - last_flush_hi >= 500 or Runtime() - last_flush >= 60000 then
            CloseStream(gstream);
            CloseStream(istream);
            if not _StreamBuildingHeaderOk(bpath, header) then
                Error("STREAM-BUILD (", label, "): .building file vanished ",
                      "or lost its header (claimed by another worker?) -- ",
                      "aborting; the claimer owns these entries now");
            fi;
            gstream := OutputTextFile(bpath, true);
            SetPrintFormattingStatus(gstream, false);
            istream := OutputTextFile(ipath, true);
            SetPrintFormattingStatus(istream, false);
            last_flush := Runtime();
            last_flush_hi := hi;
        fi;
        # Driver-specific hard checkpoint (the 2h GAP-degradation bound; now
        # nearly free -- no O(N) re-serialization).  The quit closure writes
        # its driver's state.g and QuitGap's; the next epoch adopts the
        # .building file (its offsets are authoritative -- the state.g
        # next_hi is only the orchestrator's relaunch signal).
        if ckpt_check <> fail and hi < n_expected and ckpt_check() then
            CloseStream(gstream);
            CloseStream(istream);
            ckpt_quit(hi);
        fi;
    od;
    CloseStream(gstream);
    CloseStream(istream);
    if extend_stream <> fail then CloseStream(extend_stream); fi;
    if Length(offs) <> n_expected then
        Error("STREAM-BUILD (", label, "): wrote ", Length(offs),
              " entries but the source has ", n_expected,
              " subgroups -- refusing to publish a partial cache");
    fi;
    if not _StreamBuildingHeaderOk(bpath, header) then
        Error("STREAM-BUILD (", label, "): .building header invalid at ",
              "publish time (claimed by another worker?) -- aborting");
    fi;
    Add(offs, write_pos);   # EOF sentinel (canonical HCACHE_OFFSETS format)
    # Publish gate -- mirror SaveHCacheList's referee rules: never clobber a
    # complete same-count cache whose coverage strictly dominates ours.  (A
    # shorter/absent/corrupt on-disk file is always replaced: our cache is
    # complete by construction.)
    do_publish := true;
    disk_n := ReadEntryCountFromFile(path);
    if disk_n <> fail and disk_n = n_expected and IsValidCacheFile(path) then
        disk_tag := ReadCoverageTagFromFile(path);
        if disk_tag = fail and tag <> fail then
            do_publish := false;
        elif disk_tag <> "missing" and disk_tag <> "unknown"
             and disk_tag <> fail and tag <> fail
             and IsSubset(disk_tag, tag) and not IsSubset(tag, disk_tag) then
            do_publish := false;
        fi;
    fi;
    if do_publish then
        rnd := Concatenation(String(Runtime()), ".",
                             String(Random([1..1000000])));
        idxtmp := Concatenation(path, ".idxtmp.", rnd);
        PrintTo(idxtmp, "HCACHE_OFFSETS := ", offs, ";\n");
        Exec(Concatenation("mv -f -- '", idxtmp, "' '", path, ".idx'"));
        Exec(Concatenation("mv -f -- '", bpath, "' '", path, "'"));
        RemoveFile(ipath);
        # Verify the publish (Exec surfaces no return code): a silently-
        # failed mv leaves the OLD cache at the canonical path -- for an
        # EXTEND republish it has the SAME count, so count checks alone
        # would window the coverage-short entries (silent undercount).
        if ReadEntryCountFromFile(path) <> n_expected then
            Error("STREAM-BUILD (", label, "): publish verification failed",
                  " at ", path, " (mv failed silently?)");
        fi;
        Print("  [", label, "] STREAM-BUILD published ", n_expected,
              " entries -> ", path, "\n");
    else
        RemoveFile(bpath);
        RemoveFile(ipath);
        Print("  [", label, "] STREAM-BUILD skip publish: on-disk cache is ",
              "complete with dominating coverage\n");
    fi;
    STREAM_EXTEND_FROM := fail;   # never leak extend-mode into a later fresh build
    return n_expected;
end;
"""
_TAIL_GAP = r"""
# ---- Load LEFT side ----
S_ML := SymmetricGroup(ML);
W_ML := BlockWreathFromPartition(LEFT_PARTITION);   # block-wreath ambient

# Read LEFT subgroup list eagerly; it is always needed to build/load H_CACHE.
Print("reading subs_left.g: ", SUBS_LEFT_PATH, "\n");
Read(SUBS_LEFT_PATH);
SUBGROUPS_LEFT_RAW := SUBGROUPS;
Print("subs_left.g loaded: ", Length(SUBGROUPS_LEFT_RAW), " entries\n");
if BENCH_STARTUP = 1 then
    Print("[PHASE t=", Runtime() - SCRIPT_START, "ms] subs_left_loaded\n");
fi;

RIGHT_Q_GROUPS := [];
qstate := NewQTypeState();
# LEFT-order bound: a Goursat common quotient Q must be a quotient of some LEFT
# subgroup, so |Q| divides some |H_L|.  Pruning by this BEFORE QTypeIsNew avoids
# forming + IsomorphismGroups-deduping the RIGHT's order-1024 (unsafe-SafeId)
# quotients when the LEFT cannot reach that order -- e.g. a C_2 LEFT vs a
# degree-16 2-group RIGHT (order 2048), whose ~order-1024 quotients would
# otherwise trigger pairwise IG on 2-groups (catastrophically slow -> silent
# OOM/crash).  Order-1024 IG is then done only when the LEFT truly reaches it.
LEFT_ORDERS := Set(List(SUBGROUPS_LEFT_RAW, Size));
if USE_LEFT_REALIZABLE = 1 then
    LEFT_REALIZABLE := LeftRealizableQTypesIfCheap(SUBGROUPS_LEFT_RAW);
else
    LEFT_REALIZABLE := fail;
fi;
# Per-(d,t) Q-discovery: avoid the slow RequiredQGroups(MR) union.
if RIGHT_TG_D > 0 then
    T_for_qg := TransitiveGroup(RIGHT_TG_D, RIGHT_TG_T);
    for K in NormalSubgroups(T_for_qg) do
        if Size(K) = Size(T_for_qg) then continue; fi;
        if not ForAny(LEFT_ORDERS, o -> o mod (Size(T_for_qg)/Size(K)) = 0) then continue; fi;
        Q := T_for_qg/K;
        if LEFT_REALIZABLE <> fail and not QTypeInRepList(LEFT_REALIZABLE, Q) then continue; fi;
        if QTypeIsNew(qstate, Q) then
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
        # LEFT-order bound (2026-05-31): see BATCH_DRIVER note. |Q| must divide
        # some |H_L| or Q cannot be a common quotient -- skip impossible types.
        if not ForAny(LEFT_ORDERS, o -> o mod Size(Q) = 0) then continue; fi;
        if LEFT_REALIZABLE <> fail and not QTypeInRepList(LEFT_REALIZABLE, Q) then continue; fi;
        if QTypeIsNew(qstate, Q) then
            Add(RIGHT_Q_GROUPS, Q);
        fi;
    od;
fi;

if Length(RIGHT_Q_GROUPS) = 0 and (RIGHT_TG_D > 0 or SUBS_RIGHT_PATH <> "") then
    # COPRIME short-circuit (2026-05-31): a RIGHT WAS processed (TG or subs) but
    # produced no surviving Q-type -- every RIGHT quotient was LEFT-order-filtered,
    # i.e. LEFT and RIGHT share NO nontrivial common quotient (e.g. 3-group LEFT
    # [9,17]_[9,17] vs C_2 RIGHT [2,1]).  The only valid Goursat pairing is then
    # trivial-Q (= direct products), which ReconstructHData always provides via the
    # K=H orbit.  So LEFT_Q_GROUPS := [] is correct AND avoids the
    # ComputeOrLoadLeftQGroups fallback below, which enumerated + IsomorphismGroups-
    # deduped EVERY LEFT quotient (28+ min hang on 3-group quotients) -- all wasted
    # since none can match the RIGHT.  Count-neutral.
    LEFT_Q_GROUPS := [];
    Print("COPRIME (no common Q) for M_R=", MR, ": LEFT_Q_GROUPS := [] ",
          "(trivial-Q pairing only)\n");
elif Length(RIGHT_Q_GROUPS) = 0 then
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
    # LEFT-realizability Q-prune (see QPRUNE_MAXSUBS in _SHARED_HELPERS): keep only
    # the candidate quotient types some LEFT subgroup actually surjects onto, tested
    # exactly via GQuotients.  Count-neutral; the gate is a perf knob (small LEFT =
    # the rigid distinguished LEFTs where the scan is cheap and the win is large).
    if LEFT_REALIZABLE <> fail then
        # RIGHT_Q_GROUPS was already filtered to LEFT-realizable types during
        # discovery, so it IS the prune result (count-identical to GQuotients).
        LEFT_Q_GROUPS := RIGHT_Q_GROUPS;
    elif QPRUNE_MAXSUBS > 0 and Length(SUBGROUPS_LEFT_RAW) <= QPRUNE_MAXSUBS
       and not ForAll(SUBGROUPS_LEFT_RAW, IsSolvableGroup) then
        LEFT_Q_GROUPS := Filtered(RIGHT_Q_GROUPS, Q ->
            ForAny(SUBGROUPS_LEFT_RAW, HL -> Length(GQuotients(HL, Q)) > 0));
    else
        LEFT_Q_GROUPS := RIGHT_Q_GROUPS;
    fi;
    Print("RIGHT-bounded Q-groups for M_R=", MR, ": ", Length(LEFT_Q_GROUPS),
          " types (from ", Length(RIGHT_Q_GROUPS), " RIGHT, LEFT-pruned), max |Q|=",
          Maximum(Concatenation([0], List(LEFT_Q_GROUPS, Size))), "\n");
fi;
if BENCH_STARTUP = 1 then
    Print("[PHASE t=", Runtime() - SCRIPT_START, "ms] left_q_groups_computed\n");
fi;
Print("LEFT block-wreath W_ML order=", Size(W_ML), " (vs |S_ML|=", Factorial(ML), ")\n");
H_CACHE := fail;
if CACHE_LEFT_PATH <> "" and IsValidCacheFile(CACHE_LEFT_PATH) then
    H_CACHE := ReadHCacheAuto(CACHE_LEFT_PATH);
fi;
if H_CACHE <> fail then
    # Backward compat + check if cached coverage is sufficient
    for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
    extend_needed := false;
    for hi in [1..Length(H_CACHE)] do
        missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, _UnsafeRepsOf(H_CACHE[hi]), LEFT_Q_GROUPS);
        if missing = fail or Length(missing) > 0 then
            extend_needed := true;
        fi;
    od;
    if extend_needed then
        Print("extending H_CACHE for new Q-sizes...\n");
        last_hb := Runtime();
        last_hb_count := 0;
        for hi in [1..Length(H_CACHE)] do
            missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, _UnsafeRepsOf(H_CACHE[hi]), LEFT_Q_GROUPS);
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
    if STREAM_HCACHE_BUILD = 1 and FRAMED_CACHE = 1 and CACHE_LEFT_PATH <> ""
       and Length(SUBGROUPS_LEFT_RAW) > 0 then
        # Streaming build (PRED_STREAM_HCACHE_BUILD=1): O(1) memory, entries
        # appended to a private .building file and published complete.  No
        # checkpointing in the single-combo driver (mirrors the legacy loop).
        Print("computing left H_CACHE for ", Length(SUBGROUPS_LEFT_RAW),
              " subgroups (in W_ML, streaming)...\n");
        BuildHCacheStreaming(SUBGROUPS_LEFT_RAW, W_ML, LEFT_Q_GROUPS,
                             CACHE_LEFT_PATH, "GAP-LEFT", fail, fail);
        H_CACHE := ReadHCacheAuto(CACHE_LEFT_PATH);
        for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
    else
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
EnsureHCacheComplete(H_CACHE, SUBGROUPS_LEFT_RAW, W_ML, LEFT_Q_GROUPS, CACHE_LEFT_PATH, "GAP-LEFT");
H_CACHE_L := H_CACHE;
Print("LEFT: ", Length(H_CACHE_L), " entries\n");
if BENCH_STARTUP = 1 then
    Print("[PHASE t=", Runtime() - SCRIPT_START, "ms] left_hcache_built\n");
fi;

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
        H_CACHE := ReadHCacheAuto(CACHE_RIGHT_PATH);
        for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
        # RIGHT-side completeness check (2026-06-09; mirrors the LEFT
        # EnsureHCacheComplete call): the cache file is shared between LEFT and
        # RIGHT roles and LEFT builds soft-save PARTIAL caches to it every
        # ~30 min, so a partial loaded here would silently shorten the pair
        # loop (N_RIGHT short -> SILENT UNDERCOUNT).  Cheap textual count on
        # the hit path; group objects are only constructed when healing.
        n_subs_right_chk := CountSubsGroupLines(SUBS_RIGHT_PATH);
        if n_subs_right_chk <> fail and Length(H_CACHE) <> n_subs_right_chk then
            Read(SUBS_RIGHT_PATH);
            SUBGROUPS_RIGHT_RAW := SUBGROUPS;
            EnsureHCacheComplete(H_CACHE, SUBGROUPS_RIGHT_RAW, W_MR,
                                 LEFT_Q_GROUPS, CACHE_RIGHT_PATH, "GAP-RIGHT");
        fi;
        # Extend RIGHT cache to cover LEFT_Q_GROUPS.  RIGHT side needs orbit
        # data for every Q-iso-class that LEFT may enumerate (otherwise
        # H2data.byqid lookups miss for those qids -> undercounting).
        extend_needed := false;
        for hi in [1..Length(H_CACHE)] do
            missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, _UnsafeRepsOf(H_CACHE[hi]), LEFT_Q_GROUPS);
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
                missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, _UnsafeRepsOf(H_CACHE[hi]), LEFT_Q_GROUPS);
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
if BENCH_STARTUP = 1 then
    Print("[PHASE t=", Runtime() - SCRIPT_START, "ms] right_hcache_built\n");
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

# ---- V_4 fast-path (v4opt, 2026-05-18) ---- See BATCH_DRIVER comment.
EnsureLinearADataV4 := function(H1data)
    local A_data;
    if IsBound(H1data.linear_A_data) then
        return H1data.linear_A_data <> fail;
    fi;
    if not IsBound(USE_LINEAR_ORBITS) or USE_LINEAR_ORBITS <> 1 then
        H1data.linear_A_data := fail; return false;
    fi;
    A_data := ElemAbPQuotient(H1data.H, 2);
    if A_data.d < 2 then
        H1data.linear_A_data := fail; return false;
    fi;
    H1data.linear_A_data := A_data;
    H1data.linear_gen_exps := List(H1data.H_gens_noid, g ->
        ExponentsOfPcElement(A_data.pcgs,
                             Image(A_data.hom, g)) * One(GF(2)));
    return true;
end;

EnsureV4FastPathH1 := function(h1orb, H1data)
    local A_data, d, U_vecs, U_basis, pivots, complement, k, v, pcgs_can;
    if IsBound(h1orb.v4_gen_exps) then
        return h1orb.v4_gen_exps <> fail;
    fi;
    # ElemAbPQuotient gating: only fire when H/U has F_2-dim 2 (= V_4 quotient).
    if not EnsureLinearADataV4(H1data) then
        h1orb.v4_gen_exps := fail; return false;
    fi;
    A_data := H1data.linear_A_data;
    d := A_data.d;
    U_vecs := List(h1orb.K_gens_noid, g ->
        ExponentsOfPcElement(A_data.pcgs,
                             Image(A_data.hom, g)) * One(GF(2)));
    U_vecs := Filtered(U_vecs, v -> not IsZero(v));
    if Length(U_vecs) = 0 then
        U_basis := [];
    else
        U_basis := TriangulizedMat(U_vecs);
        U_basis := Filtered(U_basis, v -> not IsZero(v));
    fi;
    if d - Length(U_basis) <> 2 then
        h1orb.v4_gen_exps := fail; return false;
    fi;
    # Fix 2026-05-21: compute v4_gen_exps in CANONICAL Q's pcgs basis (via
    # h1orb.iso_to_can), not LEFT's complement basis.  The old code used
    # A_data.pcgs which is LEFT's own ElemAbPQuotient ordering; that's
    # typically swap-related to canonical pcgs, breaking the fiber-product
    # alignment in V4FiberProductGeneratorList_M (which indexes preimg_table
    # by canonical pcgs).  EnsureAutQ guarantees h1orb.iso_to_can is set.
    EnsureAutQ(h1orb);
    pcgs_can := Pcgs(Range(h1orb.iso_to_can));
    h1orb.v4_gen_exps := List(H1data.H_gens_noid, g ->
        ExponentsOfPcElement(pcgs_can,
            Image(h1orb.iso_to_can,
                  Image(h1orb.hom, g))));
    h1orb.v4_pcgs_can := pcgs_can;
    return true;
end;

EnsureV4FastPathH2 := function(h2orb, H2_shifted)
    local pcgs_Q, pcgs_can, can_Q, table, a, b, q_can, q_local;
    if IsBound(h2orb.v4_preimg_table) then
        return h2orb.v4_preimg_table <> fail;
    fi;
    EnsureShiftedHom(h2orb, H2_shifted);
    pcgs_Q := Pcgs(h2orb.Q);
    if pcgs_Q = fail or Length(pcgs_Q) <> 2 then
        h2orb.v4_preimg_table := fail; return false;
    fi;
    # Fix 2026-05-21: index preimg_table by CANONICAL Q's pcgs basis so it
    # matches A_1, A_2 matrices and exp_vec from h1orb side (which use
    # canonical basis via iso_to_can).  Bug it fixes: for [2,1]_[2,1]_[6,9]
    # the LEFT V_4's local pcgs (e.g. [(3,4), (1,2)]) is swap-related to
    # canonical_Q's pcgs, so without basis-alignment the (a, b) coordinates
    # produced on each side don't match.
    EnsureAutQ(h2orb);
    can_Q := Range(h2orb.iso_to_can);
    pcgs_can := Pcgs(can_Q);
    table := EmptyPlist(4);
    for a in [0..1] do
        for b in [0..1] do
            q_can := pcgs_can[1]^a * pcgs_can[2]^b;        # in canonical_Q
            q_local := PreImagesRepresentative(h2orb.iso_to_can, q_can);
            table[2*a + b + 1] :=
                PreImagesRepresentative(h2orb.shifted_hom, q_local);
        od;
    od;
    h2orb.v4_preimg_table := table;
    h2orb.v4_shifted_kernel_gens_noid := Filtered(
        GeneratorsOfGroup(Kernel(h2orb.shifted_hom)),
        n -> n <> ());
    h2orb.v4_pcgs_can := pcgs_can;
    return true;
end;

V4FiberProductGeneratorList := function(H1data, h1orb, h2orb)
    local gens, idx, g, exp_vec, a, b, table_idx, preimg, gen;
    gens := [];
    for idx in [1..Length(H1data.H_gens_noid)] do
        g := H1data.H_gens_noid[idx];
        exp_vec := h1orb.v4_gen_exps[idx];
        a := exp_vec[1]; b := exp_vec[2];
        table_idx := 2*a + b + 1;
        preimg := h2orb.v4_preimg_table[table_idx];
        gen := g * preimg;
        if gen <> () then Add(gens, gen); fi;
    od;
    Append(gens, h2orb.v4_shifted_kernel_gens_noid);
    return gens;
end;

# ---- V_4 fast-path generalization (non-saturated h2 case, 2026-05-19) ----
V4_GL2_ALL := function()
    local F, all, a, b, c, d, MM;
    F := GF(2);
    all := [];
    for a in [0,1] do for b in [0,1] do
    for c in [0,1] do for d in [0,1] do
        MM := [[a, b], [c, d]] * One(F);
        if Determinant(MM) <> Zero(F) then Add(all, MM); fi;
    od; od; od; od;
    return all;
end;
V4_GL2_ALL_CACHE := V4_GL2_ALL();

V4_SubgroupClosure := function(gens)
    local id, elts, frontier, m, g, x;
    id := IdentityMat(2, GF(2));
    elts := [id];
    if Length(gens) = 0 then return elts; fi;
    frontier := ShallowCopy(gens);
    while Length(frontier) > 0 do
        m := Remove(frontier);
        if m in elts then continue; fi;
        Add(elts, m);
        for g in gens do
            x := m * g;
            if not (x in elts) then Add(frontier, x); fi;
        od;
    od;
    return elts;
end;

V4_InducedH1MatrixFromStabGen := function(A_data, U_basis, pivots, complement, s)
    local ec, h, h_conj, M_e, reduced, i, induced;
    induced := [[Zero(GF(2)), Zero(GF(2))],
                [Zero(GF(2)), Zero(GF(2))]];
    for ec in [1, 2] do
        h := PreImagesRepresentative(A_data.hom,
                                      A_data.pcgs[complement[ec]]);
        h_conj := s^-1 * h * s;
        M_e := ExponentsOfPcElement(A_data.pcgs,
                                     Image(A_data.hom, h_conj)) * One(GF(2));
        reduced := ShallowCopy(M_e);
        for i in [1..Length(U_basis)] do
            if not IsZero(reduced[pivots[i]]) then
                reduced := reduced - U_basis[i];
            fi;
        od;
        induced[1][ec] := reduced[complement[1]];
        induced[2][ec] := reduced[complement[2]];
    od;
    return induced;
end;

V4_BuildAMatricesCanonical := function(orb)
    # Fix 2026-05-21: build A matrices in CANONICAL Q's pcgs basis.
    # Each alpha in orb.A_gens is an aut of canonical_Q.  Express its
    # matrix directly in Pcgs(canonical_Q).  Both A_1 and A_2 use this
    # function so they end up in the SAME basis (= canonical pcgs).
    local pcgs_can, mat_gens, alpha, y1, y2, e1, e2, id;
    pcgs_can := Pcgs(Range(orb.iso_to_can));
    id := IdentityMat(2, GF(2));
    mat_gens := [];
    for alpha in orb.A_gens do
        y1 := Image(alpha, pcgs_can[1]);
        y2 := Image(alpha, pcgs_can[2]);
        e1 := ExponentsOfPcElement(pcgs_can, y1) * One(GF(2));
        e2 := ExponentsOfPcElement(pcgs_can, y2) * One(GF(2));
        Add(mat_gens, [[e1[1], e2[1]], [e1[2], e2[2]]]);
    od;
    mat_gens := Filtered(mat_gens, m -> m <> id);
    return V4_SubgroupClosure(mat_gens);
end;

V4_BuildA1Matrices := function(h1orb, H1data)
    if IsBound(h1orb.v4_A1_matrices) then return h1orb.v4_A1_matrices; fi;
    EnsureAutQ(h1orb);
    h1orb.v4_A1_matrices := V4_BuildAMatricesCanonical(h1orb);
    return h1orb.v4_A1_matrices;
end;

V4_BuildA2Matrices := function(h2orb)
    if IsBound(h2orb.v4_A2_matrices) then return h2orb.v4_A2_matrices; fi;
    EnsureAutQ(h2orb);
    h2orb.v4_A2_matrices := V4_BuildAMatricesCanonical(h2orb);
    return h2orb.v4_A2_matrices;
end;

V4_DoubleCosetReps := function(A1, A2)
    local seen, reps, M_iter, a1, a2, prod;
    seen := [];
    reps := [];
    for M_iter in V4_GL2_ALL_CACHE do
        if M_iter in seen then continue; fi;
        Add(reps, M_iter);
        # M maps the LEFT V_4 quotient to the RIGHT V_4 quotient, so the
        # target normalizer acts on the left and the source normalizer on the
        # right.  This matches the generic A2 \ Aut(Q) / A1 double-coset path.
        for a1 in A1 do
            for a2 in A2 do
                prod := a2 * M_iter * a1;
                if not (prod in seen) then Add(seen, prod); fi;
            od;
        od;
    od;
    return reps;
end;

V4FiberProductGeneratorList_M := function(H1data, h1orb, h2orb, M)
    local M_int, gens, idx, g, exp_vec, a, b, ap, bp,
          table_idx, preimg, gen;
    M_int := [[IntFFE(M[1][1]), IntFFE(M[1][2])],
              [IntFFE(M[2][1]), IntFFE(M[2][2])]];
    gens := [];
    for idx in [1..Length(H1data.H_gens_noid)] do
        g := H1data.H_gens_noid[idx];
        exp_vec := h1orb.v4_gen_exps[idx];
        a := exp_vec[1]; b := exp_vec[2];
        ap := (M_int[1][1] * a + M_int[1][2] * b) mod 2;
        bp := (M_int[2][1] * a + M_int[2][2] * b) mod 2;
        table_idx := 2*ap + bp + 1;
        preimg := h2orb.v4_preimg_table[table_idx];
        gen := g * preimg;
        if gen <> () then Add(gens, gen); fi;
    od;
    Append(gens, h2orb.v4_shifted_kernel_gens_noid);
    return gens;
end;

# ---- V_4 saturated Frattini fast-path (Opt v4f, 2026-05-22) ----
# When h2.full_aut = true (right normalizer induces all of Aut(V_4) = GL(2,2)),
# any choice of basis on each side is W-equivalent.  Skip the canonical-Pcgs
# transport (AutQ + IsomorphismGroups + InducedAutoGens) and use each side's
# own Frattini quotient A_H = H/(H'H^2) (already cached as H1data.linear_A_data
# via EnsureLinearADataV4) as the coordinate system.

# Compute (U_basis, pivots, complement) for orb.K inside Hdata's Frattini
# quotient A.  U_basis is a triangulized basis of K's image in A; pivots are
# its pivot columns; complement is the 2 non-pivot columns giving the F_2^2
# quotient basis.  Cached on orb.v4_frat_kdata.  Returns the kdata rec or
# fail (if A's codim is not exactly 2 in A, i.e. H/K is not V_4 in F_2-basis).
V4_FratKDataForOrb := function(Hdata, orb)
    local A_data, d, U_vecs, U_basis, pivots, vec, j, pivot_set, complement;
    if IsBound(orb.v4_frat_kdata) then return orb.v4_frat_kdata; fi;
    if not EnsureLinearADataV4(Hdata) then
        orb.v4_frat_kdata := fail; return fail;
    fi;
    A_data := Hdata.linear_A_data;
    d := A_data.d;
    U_vecs := List(orb.K_gens_noid, g ->
        ExponentsOfPcElement(A_data.pcgs,
                             Image(A_data.hom, g)) * One(GF(2)));
    U_vecs := Filtered(U_vecs, v -> not IsZero(v));
    if Length(U_vecs) = 0 then
        U_basis := [];
    else
        U_basis := TriangulizedMat(U_vecs);
        U_basis := Filtered(U_basis, v -> not IsZero(v));
    fi;
    if d - Length(U_basis) <> 2 then
        orb.v4_frat_kdata := fail; return fail;
    fi;
    pivots := [];
    for vec in U_basis do
        for j in [1..d] do
            if not IsZero(vec[j]) then Add(pivots, j); break; fi;
        od;
    od;
    pivot_set := Set(pivots);
    complement := Filtered([1..d], j -> not (j in pivot_set));
    orb.v4_frat_kdata := rec(
        A_data := A_data, U_basis := U_basis,
        pivots := pivots, complement := complement, d := d);
    return orb.v4_frat_kdata;
end;

# Reduce a vector v in A_data's pcgs basis mod U_basis and return its 2
# complement coordinates as a pair of IntFFE ints.
V4_FratReduce := function(kdata, v)
    local reduced, i;
    reduced := ShallowCopy(v);
    for i in [1..Length(kdata.U_basis)] do
        if not IsZero(reduced[kdata.pivots[i]]) then
            reduced := reduced - kdata.U_basis[i];
        fi;
    od;
    return [IntFFE(reduced[kdata.complement[1]]),
            IntFFE(reduced[kdata.complement[2]])];
end;

# Induced action matrix of conjugation by s on A_H / U_K = F_2^2.
# M[r][c] = (reduced s^-1 * pre(e_{complement[c]}) * s)[complement[r]].
V4_FratInducedMat := function(kdata, s)
    local mat, ec, h, h_conj, v, reduced, i;
    mat := [[Zero(GF(2)), Zero(GF(2))],
            [Zero(GF(2)), Zero(GF(2))]];
    for ec in [1, 2] do
        h := PreImagesRepresentative(kdata.A_data.hom,
                                      kdata.A_data.pcgs[kdata.complement[ec]]);
        h_conj := s^-1 * h * s;
        v := ExponentsOfPcElement(kdata.A_data.pcgs,
                                   Image(kdata.A_data.hom, h_conj)) * One(GF(2));
        reduced := ShallowCopy(v);
        for i in [1..Length(kdata.U_basis)] do
            if not IsZero(reduced[kdata.pivots[i]]) then
                reduced := reduced - kdata.U_basis[i];
            fi;
        od;
        mat[1][ec] := reduced[kdata.complement[1]];
        mat[2][ec] := reduced[kdata.complement[2]];
    od;
    return mat;
end;

# Detect h2orb.full_aut without calling AutQ / IsomorphismGroups.  Computes
# induced matrices of orb.Stab generators on A_H / U_K and closes under
# multiplication.  Full Aut(V_4) iff the closure has order 6 (= GL(2,2) = S_3).
# Caches result on orb.v4_full_aut_frat (bool).  Returns false if kdata is
# fail (i.e. not a V_4 quotient in F_2-Frattini basis — saturated path doesn't
# apply, caller should fall through to canonical-Pcgs path).
EnsureV4FullAutFrat := function(orb, Hdata)
    local kdata, id, mats, s, mat;
    if IsBound(orb.v4_full_aut_frat) then return orb.v4_full_aut_frat; fi;
    kdata := V4_FratKDataForOrb(Hdata, orb);
    if kdata = fail then orb.v4_full_aut_frat := false; return false; fi;
    id := IdentityMat(2, GF(2));
    mats := [];
    for s in GeneratorsOfGroup(orb.Stab) do
        mat := V4_FratInducedMat(kdata, s);
        if mat <> id then Add(mats, mat); fi;
    od;
    orb.v4_full_aut_frat := (Size(V4_SubgroupClosure(mats)) = 6);
    return orb.v4_full_aut_frat;
end;

# h1 Frattini-coord gen exps (no AutQ, no canonical pcgs).
EnsureV4FastPathH1Frat := function(h1orb, H1data)
    local kdata;
    if IsBound(h1orb.v4_gen_exps_frat) then
        return h1orb.v4_gen_exps_frat <> fail;
    fi;
    kdata := V4_FratKDataForOrb(H1data, h1orb);
    if kdata = fail then h1orb.v4_gen_exps_frat := fail; return false; fi;
    h1orb.v4_gen_exps_frat := List(H1data.linear_gen_exps, v ->
        V4_FratReduce(kdata, v));
    return true;
end;

# h2 Frattini preimg table.  r1, r2 in H2 lift the basis vectors e_{c1}, e_{c2}
# of A_{H2} (where c1, c2 = kdata.complement).  Reducing mod U_{K2} puts each
# into the (1,0) and (0,1) coordinate of H2/K2 ~= F_2^2.  Then table is
# indexed by 2*a + b + 1, matching V4FiberProductGeneratorList convention.
EnsureV4FastPathH2Frat := function(h2orb, H2data)
    local kdata, A_data, c1, c2, r1, r2, r1_sh, r2_sh, table, a, b;
    if IsBound(h2orb.v4_preimg_table_frat) then
        return h2orb.v4_preimg_table_frat <> fail;
    fi;
    kdata := V4_FratKDataForOrb(H2data, h2orb);
    if kdata = fail then h2orb.v4_preimg_table_frat := fail; return false; fi;
    A_data := kdata.A_data;
    c1 := kdata.complement[1]; c2 := kdata.complement[2];
    r1 := PreImagesRepresentative(A_data.hom, A_data.pcgs[c1]);
    r2 := PreImagesRepresentative(A_data.hom, A_data.pcgs[c2]);
    r1_sh := r1^shift_R; r2_sh := r2^shift_R;
    table := EmptyPlist(4);
    for a in [0..1] do
        for b in [0..1] do
            table[2*a + b + 1] := r1_sh^a * r2_sh^b;
        od;
    od;
    h2orb.v4_preimg_table_frat := table;
    EnsureShiftedKGenerators(h2orb);
    return true;
end;

# Saturated V_4 emit: g_i * preimg[2*a + b + 1] where (a, b) = Frattini
# complement coords of g_i.  No AutQ / IsomorphismGroups.
V4FratFiberProductGeneratorList := function(H1data, h1orb, h2orb)
    local gens, idx, g, exp_vec, preimg, gen;
    gens := [];
    for idx in [1..Length(H1data.H_gens_noid)] do
        g := H1data.H_gens_noid[idx];
        exp_vec := h1orb.v4_gen_exps_frat[idx];
        preimg := h2orb.v4_preimg_table_frat[2*exp_vec[1] + exp_vec[2] + 1];
        gen := g * preimg;
        if gen <> () then Add(gens, gen); fi;
    od;
    Append(gens, h2orb.shifted_K_gens_noid);
    return gens;
end;

# Per-process V_4 fast-path emit counter (GAP_DRIVER is single-job).
BENCH_V4FAST := rec(n_emits := 0, n_emits_nonsat := 0, n_emits_frat := 0);

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
          v4_A1, v4_A2, v4_reps, v4_M,
          bench_t0, bench_t1, h2_shifted_hom,
          # Harvest of labelled-subgroup class sums (see HOLT_SPLIT_HARVEST.md).
          # NL = |N_{W_ML}(H1)|, NR = |N_{W_MR}(H2)|, both cached on H[12]data.N_size.
          # cs_combo accumulates Sum over emitted reps of class size in S_M.
          NL, NR, fact_M, cs_combo, cs_rep, autQ_size_or_dc, is_self_swap;

    H1 := H1data.H;
    H2 := fail;
    if GEN_FILE_OPEN then
        EnsureShiftedHData(H2data);
        H2 := H2data.shifted_H;
    fi;

    # ---- HARVEST setup: precompute M!, init class_sum.  NL/NR are PER-ORBIT
    # (|h1orb.Stab| / |h2orb.Stab|), set inside the orbit loop below since
    # different K choices give different stabilisers in N_{W_ML}(H1).
    fact_M := Factorial(ML + MR);
    cs_combo := 0;

    total := 0;
    swap_fixed := 0;

    # Trivial-Q baseline: 1 orbit per (H1, H2) pair (direct product).
    # (encoded via the qsize=1 entry in each orbits list)

    for h1_orb_idx in [1..Length(H1data.orbits)] do
        h1orb := H1data.orbits[h1_orb_idx];
        key := String(h1orb.qid);
        if not IsBound(H2data.byqid.(key)) then continue; fi;
        h2idxs := H2data.byqid.(key);
        # HARVEST: per-orbit Stab_{N(H1)}(K1).  Pre-cached at cache-build
        # via Length(K_orbit); fall back to Size() for legacy cache entries.
        if not IsBound(h1orb.Stab_size) or h1orb.Stab_size = fail then
            h1orb.Stab_size := Size(h1orb.Stab);
        fi;
        NL := h1orb.Stab_size;

        # Trivial-Q (qsize = 1): direct product H1 x H2.
        # Canonical-emission gate: in burnside_m2, only emit when
        # h2idx >= h1_orb_idx (one rep per unordered orbit-pair).
        if h1orb.qsize = 1 then
            for h2idx in h2idxs do
                h2orb := H2data.orbits[h2idx];
                if not IsBound(h2orb.Stab_size) or h2orb.Stab_size = fail then
                    h2orb.Stab_size := Size(h2orb.Stab);
                fi;
                NR := h2orb.Stab_size;
                if h2orb.qsize = 1 then
                    total := total + 1;
                    if BENCH_PHASES = 1 then BENCH_N.n_pairs := BENCH_N.n_pairs + 1; fi;
                    # HARVEST: qsize=1 direct product, |dcs|=1, cs = M! / (NL*NR).
                    # Burnside self-pair (K1=K2): /2 because (H1, H2) and swap
                    # give the same direct product.
                    is_self_swap := (BURNSIDE_M2 = 1 and h1orb.K = h2orb.K);
                    if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                        cs_rep := fact_M / (NL * NR);
                        if is_self_swap then cs_rep := cs_rep / 2; fi;
                        cs_combo := cs_combo + cs_rep;
                    fi;
                    if GEN_FILE_OPEN and (BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx) then
                        if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
                        EmitGenList(Concatenation(H1data.H_gens_noid,
                                                  H2data.shifted_H_gens_noid));
                        if BENCH_PHASES = 1 then
                            BENCH_T.t_emit_qsize1 := BENCH_T.t_emit_qsize1 + (Runtime() - bench_t0);
                            BENCH_N.n_emit := BENCH_N.n_emit + 1;
                        fi;
                    fi;
                    if is_self_swap then
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
            # Opt #3: direct C_2 emit for any MR.  Originally added 2026-05-08
            # (commit 9fd1d208c6) in single-call ProcessPair.  Tentatively
            # reverted 2026-05-23 after smoke n=12 +40 mismatch, but the bug
            # was traced to the peel_c2_pair routing gate (fixed in route.py
            # and auto_mode).  Opt #3 is byte-identical-output verified against
            # the slow Goursat path via smoke3 vs smoke4 comparison.
            if true then   # opt #3: direct construction for any MR (was: MR = 2)
                for h2idx in h2idxs do
                    if H2data.orbits[h2idx].qsize <> 2 then continue; fi;
                    total := total + 1;
                    if BENCH_PHASES = 1 then BENCH_N.n_pairs := BENCH_N.n_pairs + 1; fi;
                    h2orb := H2data.orbits[h2idx];
                    if not IsBound(h2orb.Stab_size) or h2orb.Stab_size = fail then
                    h2orb.Stab_size := Size(h2orb.Stab);
                fi;
                NR := h2orb.Stab_size;
                    # HARVEST: qsize=2, AutQ=Aut(C_2)=trivial, |dcs|=1. cs = M!/(NL*NR).
                    is_self_swap := (BURNSIDE_M2 = 1 and h1orb.K = h2orb.K);
                    if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                        cs_rep := fact_M / (NL * NR);
                        if is_self_swap then cs_rep := cs_rep / 2; fi;
                        cs_combo := cs_combo + cs_rep;
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
                    if is_self_swap then
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
            if not IsBound(h2orb.Stab_size) or h2orb.Stab_size = fail then
                h2orb.Stab_size := Size(h2orb.Stab);
            fi;
            NR := h2orb.Stab_size;
            if h2orb.qsize <> h1orb.qsize then continue; fi;
            # V_4 fast-path (v4opt): gated on GEN_FILE_OPEN since the
            # fast-path requires the emit table.  Count-only mode (no
            # emit) falls through to the general path.
            if GEN_FILE_OPEN
               and h1orb.qid = [4, 0, [4, 2]]
               and h2orb.qid = [4, 0, [4, 2]] then
                # Opt v4f (2026-05-22): try saturated Frattini path first.
                # When h2.full_aut = true (detected via induced-action
                # matrices on A_{H2} / U_{K2}, no AutQ / IsomorphismGroups),
                # use each side's own Frattini quotient as the V_4 basis.
                # All basis choices are W-equivalent under the right's
                # full-Aut(V_4) action, so no canonical alignment needed.
                if EnsureV4FullAutFrat(h2orb, H2data)
                   and EnsureV4FastPathH1Frat(h1orb, H1data)
                   and EnsureV4FastPathH2Frat(h2orb, H2data) then
                    total := total + 1;
                    is_self_swap := (BURNSIDE_M2 = 1 and h1orb.K = h2orb.K);
                    # HARVEST: V_4 Frattini saturated. |Aut(V_4)|=6 covers single orbit.
                    if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                        cs_rep := fact_M * 6 / (NL * NR);
                        if is_self_swap then cs_rep := cs_rep / 2; fi;
                        cs_combo := cs_combo + cs_rep;
                        EmitGenList(V4FratFiberProductGeneratorList(
                            H1data, h1orb, h2orb));
                        BENCH_V4FAST.n_emits_frat :=
                            BENCH_V4FAST.n_emits_frat + 1;
                    fi;
                    if is_self_swap then
                        swap_fixed := swap_fixed + 1;
                    fi;
                    continue;
                fi;
                # Non-saturated: fall back to canonical-Pcgs path
                # (which calls EnsureAutQ for h1 and h2).
                if EnsureV4FastPathH2(h2orb, H2) then
                    EnsureAutQ(h2orb);
                    if h2orb.full_aut = true
                       and EnsureV4FastPathH1(h1orb, H1data) then
                        # h2 saturated but Frattini path tripped earlier
                        # (e.g. USE_LINEAR_ORBITS=0); use the original
                        # canonical-aligned emit.
                        total := total + 1;
                        is_self_swap := (BURNSIDE_M2 = 1 and h1orb.K = h2orb.K);
                        # HARVEST: V_4 saturated, same formula as frat branch.
                        if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                            cs_rep := fact_M * 6 / (NL * NR);
                            if is_self_swap then cs_rep := cs_rep / 2; fi;
                            cs_combo := cs_combo + cs_rep;
                            EmitGenList(V4FiberProductGeneratorList(
                                H1data, h1orb, h2orb));
                            BENCH_V4FAST.n_emits :=
                                BENCH_V4FAST.n_emits + 1;
                        fi;
                        if is_self_swap then
                            swap_fixed := swap_fixed + 1;
                        fi;
                        continue;
                    elif BURNSIDE_M2 = 0
                         and EnsureV4FastPathH1(h1orb, H1data) then
                        # V4_BuildA1Matrices uses h1orb.Stab directly,
                        # bypassing EnsureAutQ's InducedAutomorphism work.
                        v4_A1 := V4_BuildA1Matrices(h1orb, H1data);
                        v4_A2 := V4_BuildA2Matrices(h2orb);
                        v4_reps := V4_DoubleCosetReps(v4_A1, v4_A2);
                        total := total + Length(v4_reps);
                        # HARVEST: V_4 non-saturated.  For each v4_M rep, the dc
                        # size = number of distinct a2 * v4_M * a1 over A1xA2.
                        # |A1|, |A2| <= 6 so the inner loops are O(36) per rep.
                        # No burnside_m2 correction: this branch is BURNSIDE_M2=0 only.
                        for v4_M in v4_reps do
                            seen := [];
                            for alpha in v4_A1 do
                                for beta in v4_A2 do
                                    phi := beta * v4_M * alpha;
                                    if not (phi in seen) then Add(seen, phi); fi;
                                od;
                            od;
                            cs_rep := fact_M * Length(seen) / (NL * NR);
                            cs_combo := cs_combo + cs_rep;
                            EmitGenList(V4FiberProductGeneratorList_M(
                                H1data, h1orb, h2orb, v4_M));
                            BENCH_V4FAST.n_emits_nonsat :=
                                BENCH_V4FAST.n_emits_nonsat + 1;
                        od;
                        continue;
                    fi;
                fi;
            fi;
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
                # A2 in canonical Aut(Q).  h1orb and h2orb are matched by qid
                # (H2data.byqid), so they share the SAME canonical Q and the SAME
                # AutQ object (QCAN_TABLE) -- h2orb.A_gens already live in
                # h1orb.AutQ and ARE the correct A_2.  This MUST use the same
                # (canonical) identification as the emit base
                #   J = h2.iso_to_can o h1.iso_to_can^-1   (see orbit_reps_phi).
                # Do NOT transport via the arbitrary isoTH = IsomorphismGroups(
                # h2.Q, h1.Q): isoTH differs from J by an aut c of Qcan, so
                # isoTH-transport yields c^-1 A2 c.  That is CONJUGATE to A2, so
                # the orbit COUNT is unchanged, but the dcs partition no longer
                # lines up with the canonical emit base -> the emitted reps are
                # NOT a transversal of the true fiber-product classes (duplicate
                # + missing classes).  Brute-force verified in
                # _dc_consistency_probe.g: canonical A2 = valid transversal,
                # isoTH-transport = invalid.  (Reverts the 2026-05-20 isoTH
                # patch, which fixed a count that was never actually wrong here.)
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
            # HARVEST: effective |dc| for cs.  Saturated branch (dcs=[]) uses
            # Size(AutQ) since the single orbit covers all of AutQ.
            if Length(dcs) = 0 then
                autQ_size_or_dc := Size(h2orb.AutQ);
            fi;

            # Compute swap-orbit-id per orbit rep (used for both within-self-pair
            # canonical emission gate and swap_fixed counter).
            if BENCH_PHASES = 1 then bench_t0 := Runtime(); fi;
            swap_orb_id_arr := ListWithIdenticalEntries(n_orb, -1);
            if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                if h1orb.full_aut = true or h2orb.full_aut = true then
                    # Optimization (1) shortcut: 1 orbit, trivially swap-fixed.
                    swap_orb_id_arr[1] := 1;
                else
                    # Self-pair swap.  The emission gate (h2idx = h1_orb_idx)
                    # means h1orb and h2orb are the SAME orbit, so A1 = A2 = A
                    # and Q1 = Q2.  The factor swap is the transpose gluing
                    # psi -> psi^-1, so orbit i is swap-fixed iff psi_i^-1 lies in
                    # its own double coset A psi_i A.  Work in canonical Aut(Qcan)
                    # to match the (now canonical) dcs; no isoTH.  Brute-force
                    # verified vs the inverse-set test in _swap_probe.g.
                    gensQ := GeneratorsOfGroup(Range(h1orb.iso_to_can));
                    for i in [1..n_orb] do
                        # Reify Rep(dcs[i])^-1 as a native GroupHomomorphismByImagesNC
                        # so DoubleCoset `in` recognizes it as an AutQ element.
                        g_swap := Inverse(Representative(dcs[i]));
                        g_swap := GroupHomomorphismByImagesNC(
                            Range(h1orb.iso_to_can), Range(h1orb.iso_to_can),
                            gensQ, List(gensQ, q -> Image(g_swap, q)));
                        SetIsBijective(g_swap, true);
                        swap_orb_id_arr[i] :=
                            PositionProperty(dcs, dc -> g_swap in dc);
                    od;
                fi;
            fi;

            if BENCH_PHASES = 1 then BENCH_T.t_swap := BENCH_T.t_swap + (Runtime() - bench_t0); fi;

            # HARVEST: closed-form pair contribution.  Telescoping Sum_i |dcs[i]|
            # = |AutQ| eliminates the per-rep loop.  Self-pair canonical-gate
            # (Sum_{i<=swap_id[i]} cs_i with /2 for self-fixed) collapses to
            # (1/2) Sum_all cs_i by the inversion symmetry of swap on dcs.
            if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                if Length(dcs) = 0 then
                    cs_rep := fact_M * autQ_size_or_dc / (NL * NR);
                else
                    cs_rep := fact_M * Size(h2orb.AutQ) / (NL * NR);
                fi;
                if BURNSIDE_M2 = 1 and h2idx = h1_orb_idx then
                    cs_rep := cs_rep / 2;
                fi;
                cs_combo := cs_combo + cs_rep;
            fi;
            # Generator emission per orbit rep, canonical-gated (unchanged).
            if GEN_FILE_OPEN then
                if BURNSIDE_M2 = 0 or h2idx > h1_orb_idx then
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
    return rec(orbits := total, swap_fixed := swap_fixed,
               class_sum := cs_combo);
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
TOTAL_CS_SUM := resume_total_cs;   # HARVEST: class_sum, carried across resume (see resume block)
t0 := Runtime();
n_left := Length(H_CACHE_L);
# HOTFIX 2026-06-12: reset the checkpoint timer to EXCLUDE cache/setup load
# (the LEFT H-cache build can be long on heavy standalone combos) so the
# checkpoint interval/floor measure only useful pair-loop work, not setup.
WORKER_START := Runtime();
WORKER_START_WALL := NanosecondsSinceEpoch();
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
        TOTAL_CS_SUM := TOTAL_CS_SUM + res_pair.class_sum;
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
                    ", total_cs_sum := ", TOTAL_CS_SUM,
                    " );\n");
            Exec(Concatenation("mv -f -- '", tmp, "' '", STATE_FILE, "'"));
        fi;
        # Checkpoint: if elapsed exceeds threshold AND there's more to do,
        # quit.  Python wrapper sees state.g and re-invokes us.
        if STATE_FILE <> "" and CHECKPOINT_INTERVAL_MS > 0
           and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CHECKPOINT_INTERVAL_MS
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
      " class_sum=", TOTAL_CS_SUM,
      " elapsed_ms=", Runtime() - t0,
      " v4fast_emits=", BENCH_V4FAST.n_emits,
      " v4fast_nonsat=", BENCH_V4FAST.n_emits_nonsat,
      " v4fast_frat=", BENCH_V4FAST.n_emits_frat, "\n");

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
_PREAMBLE_BATCH = r"""
LogTo("__LOG__");
SizeScreen([100000, 24]);   # disable line wrapping in output

# Linear-orbits flag + Stage A/B/C prototype load (Cut 3 — applies to
# ExtendHCacheEntry / ComputeHCacheEntry / ComputeHDataDirect for the
# C_2/C_3/V_4/S_3/D_8 qids).  Default ON; set PRED_USE_LINEAR_ORBITS=0 to force legacy.
USE_LINEAR_ORBITS := __USE_LINEAR_ORBITS__;
USE_STAGE_D := __USE_STAGE_D__;
if USE_LINEAR_ORBITS = 1 then
    Print("[USE_LINEAR_ORBITS=1] loading Stage A/B/C prototypes...\n");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_a.g");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_b.g");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_c.g");
    if USE_STAGE_D = 1 then
        Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_d.g");
    fi;
fi;

# Lazy LEFT reconstruction toggle (PRED_LAZY_LEFT_RECON; default 0).  See the
# H1DATA_LIST build below and the per-i loop in _LOOP_BATCH.
LAZY_LEFT_RECON := __LAZY_LEFT_RECON__;
FRAMED_CACHE := __FRAMED_CACHE__;   # 1 => write windowable framed cache (+ .idx)
# Streaming H-cache build (PRED_STREAM_HCACHE_BUILD; requires FRAMED_CACHE=1).
# See BuildHCacheStreaming in the shared helpers.
STREAM_HCACHE_BUILD := __STREAM_HCACHE_BUILD__;
BUILD_TOKEN := "__BUILD_TOKEN__";            # process-private .building suffix
HCACHE_BUILD_VER := "__HCACHE_BUILD_VER__";  # entry-content version marker
STREAM_WINDOW_MIN := __STREAM_WINDOW_MIN__;  # BATCH: windowed pair loop at >= this many entries

# Hard checkpoint-restart policy (a restart = GAP relaunch + LEFT setup re-load,
# which is expensive: subs_left reload + LEFT_Q_GROUPS + cache window-open).  A
# restart fires when ANY holds:
#   * N_PAIRS_EPOCH >= MAX_PAIRS_PER_CKPT  -- work cap; lets fast / light-per-pair
#     workers amortize the per-epoch setup over many pairs;
#   * wall >= CHECKPOINT_INTERVAL_MS       -- 2h backstop "no matter what"; catches
#     workers so slow they never reach a CKPT_PAIR_GRAN boundary;
#   * at each CKPT_PAIR_GRAN-pair boundary, wall >= CKPT_TIME_FLOOR_MS -- bounds
#     heap/memory on the SLOW, heavy-per-pair workers (the ones that may balloon).
# N_PAIRS_EPOCH counts pairs since this GAP process started (= since last restart).
# Set a threshold to 0 to disable that clause.
MAX_PAIRS_PER_CKPT := __MAX_PAIRS_PER_CKPT__;
CKPT_TIME_FLOOR_MS := __CKPT_TIME_FLOOR_MS__;
CKPT_PAIR_GRAN     := __CKPT_PAIR_GRAN__;
MAX_WORKSPACE_KB   := __MAX_WORKSPACE_KB__;   # 0 = disabled; else checkpoint-restart the epoch when GAP workspace >= this many KB
N_PAIRS_EPOCH := 0;

# Path to lifting_algorithm.g for _GoursatBuildFiberProduct.
if not IsBound(_GoursatBuildFiberProduct) then Read("__LIFTING_G__"); fi;

# Common helpers (same as GAP_DRIVER).
"""
_HEADER_BATCH = r"""
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
# Per-job streamed-generator output (set per job in the loop below).  Replaces
# the old in-memory fp_lines buffer that drove the S20/S21 30 GB workers.
CUR_GEN_PATH := "";
CUR_GEN_STREAM := fail;
WORKER_START := Runtime();
# Wall-clock baseline for the hard checkpoint-restart trigger.  Runtime() is CPU
# time, which stalls when a bloated worker thrashes on page faults -- so a
# CPU-keyed 2h restart can never fire on the exact heavy jobs it must bound.
# NanosecondsSinceEpoch() is monotonic wall time, immune to iowait starvation.
WORKER_START_WALL := NanosecondsSinceEpoch();

RESUME_JOB_IDX := 1;
RESUME_PAIR_I := 1;
RESUME_PAIR_J := 1;          # 1 = no mid-i resume (start of a fresh i)
RESUME_TOTAL_ORB := 0;
RESUME_TOTAL_FIX := 0;
RESUME_TOTAL_CS := 0;
RESUME_BUILD_NEXT_HI := 0;   # 0 = no build resume

if STATE_FILE <> "" and IsExistingFile(STATE_FILE) then
    Read(STATE_FILE);
    if IsBound(RESUME_STATE) then
        RESUME_JOB_IDX := RESUME_STATE.job_idx;
        # pair coords + totals are absent in a fresh / between-job state.g
        # (rec(job_idx := J) only); they are present when Python reconstructed
        # RESUME_STATE from a gens-file "# cp" marker.  Default to a fresh job.
        if IsBound(RESUME_STATE.pair_i) then
            RESUME_PAIR_I := RESUME_STATE.pair_i;
        fi;
        if IsBound(RESUME_STATE.pair_j) then
            RESUME_PAIR_J := RESUME_STATE.pair_j;
        fi;
        if IsBound(RESUME_STATE.total_orb) then
            RESUME_TOTAL_ORB := RESUME_STATE.total_orb;
        fi;
        if IsBound(RESUME_STATE.total_fix) then
            RESUME_TOTAL_FIX := RESUME_STATE.total_fix;
        fi;
        if IsBound(RESUME_STATE.total_cs_sum) then
            RESUME_TOTAL_CS := RESUME_STATE.total_cs_sum;
        fi;
        Print("CHECKPOINT_RESUME job_idx=", RESUME_JOB_IDX,
              " pair_i=", RESUME_PAIR_I,
              " pair_j=", RESUME_PAIR_J,
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
qstate := NewQTypeState();
# LEFT-order bound (see GAP_DRIVER): |Q| must divide some |H_L|, else Q can't be
# a common Goursat quotient.  Prunes the RIGHT 2-group's order-1024 quotients
# (and the lethal pairwise IsomorphismGroups in QTypeIsNew) when the shared LEFT
# can't reach that order.  SUBGROUPS_LEFT_RAW is the same for every job here.
LEFT_ORDERS := Set(List(SUBGROUPS_LEFT_RAW, Size));
if USE_LEFT_REALIZABLE = 1 then
    LEFT_REALIZABLE := LeftRealizableQTypesIfCheap(SUBGROUPS_LEFT_RAW);
else
    LEFT_REALIZABLE := fail;
fi;
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
                if not ForAny(LEFT_ORDERS, o -> o mod (Size(T_for_qg)/Size(K)) = 0) then continue; fi;
                Q := T_for_qg/K;
                if LEFT_REALIZABLE <> fail and not QTypeInRepList(LEFT_REALIZABLE, Q) then continue; fi;
                if QTypeIsNew(qstate, Q) then
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
            # LEFT-order bound (2026-05-31): a common Goursat quotient Q must be a
            # quotient of SOME LEFT subgroup, so |Q| must divide some |H_L|.  The
            # TG branch already applies this; the subs_right branch did NOT, so a
            # heavy RIGHT cluster (e.g. [6,6] -> |Q| up to |S6|^2=518400) injected
            # impossible Q-types against a tiny LEFT (D8^2, |H|<=64), and the
            # extend/QTypeCovered reconciliation then ran IsomorphismGroups on
            # half-million-order groups that can never match.  Filter them here.
            if not ForAny(LEFT_ORDERS, o -> o mod Size(Q) = 0) then continue; fi;
            if LEFT_REALIZABLE <> fail and not QTypeInRepList(LEFT_REALIZABLE, Q) then continue; fi;
            if QTypeIsNew(qstate, Q) then
                Add(RIGHT_Q_GROUPS, Q);
            fi;
        od;
    fi;
od;

if Length(RIGHT_Q_GROUPS) = 0
   and ForAny(JOBS, j -> j.right_tg_d > 0 or j.subs_right <> "") then
    # COPRIME short-circuit (2026-05-31): RIGHT processed but no Q-type survived
    # the LEFT-order filter -> no nontrivial common quotient -> trivial-Q
    # (direct-product) pairings only.  Skips the ComputeOrLoadLeftQGroups hang
    # on coprime LEFT/RIGHT (e.g. [2,1]_[9,17]_[9,17]).  See GAP_DRIVER note.
    LEFT_Q_GROUPS := [];
    Print("[t+", Runtime() - batch_t0, "ms] COPRIME (no common Q): ",
          "LEFT_Q_GROUPS := [] (trivial-Q pairing only)\n");
elif Length(RIGHT_Q_GROUPS) = 0 then
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
    # LEFT-realizability Q-prune (see QPRUNE_MAXSUBS in _SHARED_HELPERS): keep only
    # the candidate quotient types some LEFT subgroup actually surjects onto (exact,
    # via GQuotients).  Count-neutral; the gate is a perf knob for small LEFT lists.
    if LEFT_REALIZABLE <> fail then
        # RIGHT_Q_GROUPS was already filtered to LEFT-realizable types during
        # discovery, so it IS the prune result (count-identical to GQuotients).
        LEFT_Q_GROUPS := RIGHT_Q_GROUPS;
    elif QPRUNE_MAXSUBS > 0 and Length(SUBGROUPS_LEFT_RAW) <= QPRUNE_MAXSUBS
       and not ForAll(SUBGROUPS_LEFT_RAW, IsSolvableGroup) then
        LEFT_Q_GROUPS := Filtered(RIGHT_Q_GROUPS, Q ->
            ForAny(SUBGROUPS_LEFT_RAW, HL -> Length(GQuotients(HL, Q)) > 0));
    else
        LEFT_Q_GROUPS := RIGHT_Q_GROUPS;
    fi;
    Print("[t+", Runtime() - batch_t0, "ms] RIGHT-bounded Q-groups: ",
          Length(LEFT_Q_GROUPS), " types (from ", Length(RIGHT_Q_GROUPS),
          " RIGHT, LEFT-pruned), max |Q|=",
          Maximum(Concatenation([0], List(LEFT_Q_GROUPS, Size))), "\n");
fi;

H_CACHE := fail;
# Windowed LEFT (framed cache): skip the full read / coverage-scan / extend and
# read each LEFT entry on demand in the pair loop (GetHCacheEntry).  Two cases:
#   (a) a pure pair-loop RESUME -- a prior epoch of THIS invocation already
#       finished build+extend+EnsureHCacheComplete and published a COMPLETE
#       framed cache (in-process invariant), as before; OR
#   (b) the FIRST epoch (no RESUME_STATE) REUSING an already-built complete
#       cache whose entry count >= STREAM_WINDOW_MIN.  Epoch 1 used to full-load
#       the entire cache into RAM (the n=18 C2/D8 monsters are ~3 GB on disk ->
#       tens of GB live) before any pairs ran; windowing avoids that balloon.
# Small caches stay on the cheap full-load path (gated by STREAM_WINDOW_MIN), so
# the overwhelming majority of combos are byte-identical to before.  Case (b) is
# made safe against a crashed-mid-extend HETEROGENEOUS cache by the per-entry
# probe below (the union coverage header can over-claim; see
# WindowedCacheUniformlyCovered).  LEFT_Q_GROUPS + SUBGROUPS_LEFT_RAW above are
# still computed (cheap; needed for RIGHT extend + pairing).
USE_WINDOWED_LEFT := false;
if not IsBound(RESUME_BUILD) and not IsBound(RESUME_EXTEND)
   and (IsBound(RESUME_STATE) or Length(SUBGROUPS_LEFT_RAW) >= STREAM_WINDOW_MIN)
   and CACHE_LEFT_PATH <> "" and IsFramedCacheFile(CACHE_LEFT_PATH)
   and OpenHCacheWindow(CACHE_LEFT_PATH) then
    # (2026-06-09 hardening) The windowed fast path trusts that the on-disk
    # framed cache is the COMPLETE, fully-covered cache a prior epoch of THIS
    # invocation saved.  That invariant holds in-process, but the cache file
    # is shared across workers (LEFT/RIGHT roles; the same cluster in other
    # combos), and a concurrent build's soft-save can clobber it with a
    # PARTIAL (count-short) or foreign-coverage file -- the windowed branch
    # would then run the pair loop N_LEFT-short (SILENT UNDERCOUNT) or with
    # entries missing orbit recs for required qids.  Verify entry count and
    # coverage tag before trusting; on any mismatch fall through to the full
    # load, whose per-entry scan + EnsureHCacheComplete self-heal.
    wleft_ok := HCW_COUNT = Length(SUBGROUPS_LEFT_RAW);
    if wleft_ok then
        wleft_tag := ReadCoverageTagFromFile(CACHE_LEFT_PATH);
        if wleft_tag = fail then
            ;  # full coverage -- fine
        elif wleft_tag = "missing" or wleft_tag = "unknown" then
            wleft_ok := false;
        elif not IsSubset(wleft_tag, QIdsOfGroups(LEFT_Q_GROUPS)) then
            wleft_ok := false;
        fi;
    fi;
    # Per-entry completeness probe.  The coverage-tag check above trusts the
    # file header, which UNIONs per-entry coverage and so over-claims for a
    # crashed-mid-extend cache (extended prefix + short tail).  Probe a
    # sample of real entries (incl. the last) and reject on any shortfall
    # -> full-load self-heal.  Runs on pair-loop RESUME too (2026-07-02):
    # resume epochs are separate processes and the cache file is shared
    # across workers between epochs, so the "in-process invariant" the old
    # resume-skip relied on was never actually process-local.  ~9 seeks.
    if wleft_ok then
        wleft_ok := WindowedCacheUniformlyCovered(LEFT_Q_GROUPS);
    fi;
    if wleft_ok then
        N_LEFT := HCW_COUNT;
        USE_WINDOWED_LEFT := true;
        H1DATA_LIST := fail;
        H_CACHE_L := fail;
        if IsBound(RESUME_STATE) then
            Print("[t+", Runtime() - batch_t0, "ms] WINDOWED LEFT: ", N_LEFT,
                  " entries (framed cache, pair-loop resume; reading on demand)\n");
        else
            Print("[t+", Runtime() - batch_t0, "ms] WINDOWED LEFT: ", N_LEFT,
                  " entries (framed cache, epoch-1 reuse; reading on demand)\n");
        fi;
    else
        CloseHCacheWindow();
        Print("[t+", Runtime() - batch_t0, "ms] WINDOWED LEFT REJECTED: count ",
              HCW_COUNT, " vs ", Length(SUBGROUPS_LEFT_RAW),
              " subgroups, coverage tag short, or non-uniform tail -- full load\n");
    fi;
fi;
# ---- Streaming LEFT-cache EXTEND (memory-bounded) --------------------------
# The epoch-1 gate above windows a COMPLETE framed cache.  If instead the cache
# needs MORE coverage (or a prior extend was checkpointed: RESUME_EXTEND),
# extend it ONE ENTRY AT A TIME via BuildHCacheStreaming(STREAM_EXTEND_FROM=...)
# -- reading the old framed cache on demand and republishing -- instead of
# full-loading the whole multi-GB cache to extend in place (THE 40 GB+ balloon).
# Then window the freshly-published complete cache.  Falls through to the legacy
# full-load extend below when not framed / count-mismatched / streaming off.
if not USE_WINDOWED_LEFT and not IsBound(RESUME_BUILD)
   and STREAM_HCACHE_BUILD = 1 and FRAMED_CACHE = 1
   and CACHE_LEFT_PATH <> "" and IsFramedCacheFile(CACHE_LEFT_PATH)
   and ReadEntryCountFromFile(CACHE_LEFT_PATH) = Length(SUBGROUPS_LEFT_RAW) then
    do_stream_extend := IsBound(RESUME_EXTEND);
    if not do_stream_extend and OpenHCacheWindow(CACHE_LEFT_PATH)
       and HCW_COUNT = Length(SUBGROUPS_LEFT_RAW) then
        se_tag := ReadCoverageTagFromFile(CACHE_LEFT_PATH);
        if se_tag = fail or se_tag = "missing" or se_tag = "unknown" then
            do_stream_extend := false;   # full / unknown coverage -> legacy path
        elif not IsSubset(se_tag, QIdsOfGroups(LEFT_Q_GROUPS)) then
            do_stream_extend := true;    # header coverage short
        elif not WindowedCacheUniformlyCovered(LEFT_Q_GROUPS) then
            do_stream_extend := true;    # header full but a tail entry is short
        else
            do_stream_extend := false;   # complete + uniform -> no extend needed
        fi;
        CloseHCacheWindow();
    fi;
    if do_stream_extend then
        Print("[t+", Runtime() - batch_t0, "ms] STREAMING-EXTEND LEFT cache (",
              Length(SUBGROUPS_LEFT_RAW), " entries, one at a time)...\n");
        STREAM_EXTEND_FROM := CACHE_LEFT_PATH;
        BuildHCacheStreaming(SUBGROUPS_LEFT_RAW, W_ML, LEFT_Q_GROUPS,
            CACHE_LEFT_PATH, "BATCH-LEFT-EXTEND",
            function()
                return STATE_FILE <> "" and CHECKPOINT_INTERVAL_MS > 0
                   and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL,
                              1000000) >= CHECKPOINT_INTERVAL_MS;
            end,
            function(hi_done)
                local tmp;
                tmp := Concatenation(STATE_FILE, ".tmp");
                PrintTo(tmp, "RESUME_EXTEND := rec( streaming := true, done_until := ",
                        hi_done, " );\n");
                Exec(Concatenation("mv -f -- '", tmp, "' '", STATE_FILE, "'"));
                Print("CHECKPOINT_PAUSE_EXTEND streaming done_until=", hi_done,
                      "/", Length(SUBGROUPS_LEFT_RAW),
                      " elapsed_ms=", Runtime() - WORKER_START, "\n");
                LogTo();
                QuitGap();
            end);
        STREAM_EXTEND_FROM := fail;
        # Extend completed (no checkpoint) -> clear the RESUME_EXTEND signal and
        # window the now-complete published cache (skips the full-load below).
        if IsBound(RESUME_EXTEND) and STATE_FILE <> "" and IsExistingFile(STATE_FILE)
           and not IsBound(RESUME_STATE) and not IsBound(RESUME_BUILD) then
            RemoveFile(STATE_FILE);
        fi;
        # Re-verify coverage after the republish (2026-07-02): the publish
        # `mv`s can fail silently (Exec rc unchecked), leaving the OLD,
        # coverage-short cache at the canonical path with the SAME entry
        # count -- a count check alone would window it and the pair loop
        # would silently undercount.  On rejection fall through to the full
        # load below, whose per-entry scan + extend self-heal.
        if OpenHCacheWindow(CACHE_LEFT_PATH) then
            if HCW_COUNT = Length(SUBGROUPS_LEFT_RAW)
               and WindowedCacheUniformlyCovered(LEFT_Q_GROUPS) then
                N_LEFT := HCW_COUNT;
                USE_WINDOWED_LEFT := true;
                H1DATA_LIST := fail;
                H_CACHE_L := fail;
                Print("[t+", Runtime() - batch_t0, "ms] WINDOWED LEFT: ", N_LEFT,
                      " entries (framed cache, post-streaming-extend; reading on demand)\n");
            else
                CloseHCacheWindow();
                Print("[t+", Runtime() - batch_t0, "ms] WINDOWED LEFT REJECTED ",
                      "post-extend: count/coverage short (publish failed?) ",
                      "-- full load\n");
            fi;
        fi;
    fi;
fi;
if not USE_WINDOWED_LEFT then
# Cache-load policy: if RESUME_BUILD is in flight, the on-disk file is a
# *partial* cache that we want to extend, NOT a complete cache to skip-load.
if CACHE_LEFT_PATH <> "" and IsValidCacheFile(CACHE_LEFT_PATH) then
    if RESUME_BUILD_NEXT_HI > 0 then
        Print("[t+", Runtime() - batch_t0,
              "ms] reading PARTIAL H_CACHE from disk (resuming build at ",
              RESUME_BUILD_NEXT_HI, "): ", CACHE_LEFT_PATH, "\n");
        H_CACHE := ReadHCacheAuto(CACHE_LEFT_PATH);
        Print("[t+", Runtime() - batch_t0, "ms] partial H_CACHE: ",
              Length(H_CACHE), " entries already built\n");
    else
        Print("[t+", Runtime() - batch_t0, "ms] reading H_CACHE from disk: ",
              CACHE_LEFT_PATH, "\n");
        H_CACHE := ReadHCacheAuto(CACHE_LEFT_PATH);
        Print("[t+", Runtime() - batch_t0, "ms] H_CACHE read complete: ",
              Length(H_CACHE), " entries\n");
    fi;
fi;
if H_CACHE <> fail and RESUME_BUILD_NEXT_HI = 0 then
    for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
    extend_needed := false;
    for hi in [1..Length(H_CACHE)] do
        missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, _UnsafeRepsOf(H_CACHE[hi]), LEFT_Q_GROUPS);
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
            missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, _UnsafeRepsOf(H_CACHE[hi]), LEFT_Q_GROUPS);
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
               and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CHECKPOINT_INTERVAL_MS
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
    if STREAM_HCACHE_BUILD = 1 and FRAMED_CACHE = 1 and CACHE_LEFT_PATH <> ""
       and Length(SUBGROUPS_LEFT_RAW) > 0 then
        # --- Streaming build (PRED_STREAM_HCACHE_BUILD=1): O(1) memory, no
        # O(N) soft-saves; the canonical path only ever receives COMPLETE
        # caches.  See BuildHCacheStreaming in _SHARED_HELPERS.
        if H_CACHE <> fail and Length(H_CACHE) = Length(SUBGROUPS_LEFT_RAW) then
            # A COMPLETE cache appeared at the canonical path (e.g. a
            # concurrent worker's publish landed while our RESUME_BUILD was
            # pending).  Use it as-is -- appending from next_hi (legacy
            # semantics) would duplicate entries -> over-length Error.
            Print("[t+", Runtime() - batch_t0, "ms] STREAM-BUILD: canonical ",
                  "cache already complete (", Length(H_CACHE),
                  " entries); skipping build\n");
            for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
        else
            # Never resume by appending to a canonical partial: the .building
            # file (matched by BUILD_TOKEN) is the streaming resume state.
            H_CACHE := fail;
            Print("[t+", Runtime() - batch_t0, "ms] computing left H_CACHE for ",
                  Length(SUBGROUPS_LEFT_RAW), " subgroups (in W_ML, streaming)\n");
            BuildHCacheStreaming(SUBGROUPS_LEFT_RAW, W_ML, LEFT_Q_GROUPS,
                CACHE_LEFT_PATH, "BATCH-LEFT",
                function()
                    return STATE_FILE <> "" and CHECKPOINT_INTERVAL_MS > 0
                       and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL,
                                  1000000) >= CHECKPOINT_INTERVAL_MS;
                end,
                function(hi_done)
                    local tmp;
                    tmp := Concatenation(STATE_FILE, ".tmp");
                    PrintTo(tmp, "RESUME_BUILD := rec( next_hi := ",
                            hi_done + 1, " );\n");
                    Exec(Concatenation("mv -f -- '", tmp, "' '", STATE_FILE, "'"));
                    Print("CHECKPOINT_PAUSE_BUILD next_hi=", hi_done + 1,
                          " of=", Length(SUBGROUPS_LEFT_RAW),
                          " elapsed_ms=", Runtime() - WORKER_START,
                          " (streaming)\n");
                    LogTo();
                    QuitGap();
                end);
            # Pair-loop access: windowed for big LEFTs (never materialize the
            # list we just streamed out -- the always-windowed half of the
            # streaming design), full load for small ones (cheap; identical
            # to today's behavior where the current code is fine).
            if Length(SUBGROUPS_LEFT_RAW) >= STREAM_WINDOW_MIN
               and OpenHCacheWindow(CACHE_LEFT_PATH) then
                # Coverage re-probe (2026-07-02): if the publish `mv` failed
                # silently, the canonical path can still hold an OLD
                # same-count cache -- reject and full-load (self-heals).
                if HCW_COUNT = Length(SUBGROUPS_LEFT_RAW)
                   and WindowedCacheUniformlyCovered(LEFT_Q_GROUPS) then
                    N_LEFT := HCW_COUNT;
                    USE_WINDOWED_LEFT := true;
                    H1DATA_LIST := fail;
                    H_CACHE_L := fail;
                    Print("[t+", Runtime() - batch_t0, "ms] WINDOWED LEFT: ",
                          N_LEFT, " entries (streamed build; reading on demand)\n");
                else
                    CloseHCacheWindow();
                fi;
            fi;
            if not USE_WINDOWED_LEFT then
                H_CACHE := ReadHCacheAuto(CACHE_LEFT_PATH);
                for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
            fi;
        fi;
    else
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
           and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CHECKPOINT_INTERVAL_MS
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
    fi;   # end: streaming vs legacy build
    # Build done — clear any RESUME_BUILD state so the pair loop starts
    # cleanly.  (RESUME_STATE if present remains for pair-loop resume.)
    if RESUME_BUILD_NEXT_HI > 0 and STATE_FILE <> "" and IsExistingFile(STATE_FILE) then
        RemoveFile(STATE_FILE);
        RESUME_BUILD_NEXT_HI := 0;
    fi;
fi;
if not USE_WINDOWED_LEFT then
# (re-checked: a streamed fresh build may have switched to windowed access
# above, in which case the cache stays on disk -- no completeness scan or
# reconstruction over an in-memory list to do.  Completeness is guaranteed
# by the publish-time count assertion + the HCW_COUNT check.)
EnsureHCacheComplete(H_CACHE, SUBGROUPS_LEFT_RAW, W_ML, LEFT_Q_GROUPS, CACHE_LEFT_PATH, "BATCH-LEFT");
H_CACHE_L := H_CACHE;
N_LEFT := Length(H_CACHE_L);
if LAZY_LEFT_RECON = 1 then
    # Lazy LEFT reconstruction (PRED_LAZY_LEFT_RECON=1): skip the eager
    # H1DATA_LIST build.  Each H1data is reconstructed per-i inside the pair
    # loop and discarded, bounding the reconstructed-group footprint to O(1)
    # instead of O(N_LEFT) materialized group objects held for the lifetime of
    # all jobs.  Trades J-fold ReconstructHData (once per entry per job sharing
    # this LEFT) for a flat memory profile -- critical for heavy distinguished
    # LEFTs (12K-25K entries) run many workers wide.  Mirrors GAP_DRIVER, which
    # already reconstructs lazily at point of use.
    H1DATA_LIST := fail;
    Print("[t+", Runtime() - batch_t0,
          "ms] LAZY_LEFT_RECON=1: deferring ReconstructHData for ",
          N_LEFT, " LEFT entries\n");
else
    Print("[t+", Runtime() - batch_t0, "ms] starting ReconstructHData on ",
          N_LEFT, " entries...\n");
    last_hb := Runtime();
    H1DATA_LIST := [];
    for hi in [1..N_LEFT] do
        Add(H1DATA_LIST, ReconstructHData(H_CACHE_L[hi], S_ML));
        if Runtime() - last_hb >= 60000 then
            Print("  [t+", Runtime() - batch_t0, "ms] ReconstructHData ",
                  hi, "/", N_LEFT, "\n");
            last_hb := Runtime();
        fi;
    od;
    Print("[t+", Runtime() - batch_t0, "ms] ReconstructHData done; LEFT loaded: ",
          N_LEFT, " entries\n");
fi;
fi;   # end: inner windowed re-check (post-streamed-build windowed case)
fi;   # end: if not USE_WINDOWED_LEFT (full LEFT load/build/extend path)

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
            H_CACHE := ReadHCacheAuto(JOB.cache_right);
            for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
            # RIGHT-side completeness check (2026-06-09): the cache file is
            # LEFT/RIGHT-shared and LEFT builds soft-save PARTIAL caches to it;
            # a partial loaded here silently shortens the pair loop (N_RIGHT
            # short -> SILENT UNDERCOUNT).  Cheap textual count on the hit path.
            n_subs_right_chk := CountSubsGroupLines(JOB.subs_right);
            if n_subs_right_chk <> fail and Length(H_CACHE) <> n_subs_right_chk then
                Read(JOB.subs_right);
                SUBGROUPS_RIGHT_RAW := SUBGROUPS;
                EnsureHCacheComplete(H_CACHE, SUBGROUPS_RIGHT_RAW, S_MR,
                                     LEFT_Q_GROUPS, JOB.cache_right, "BATCH-RIGHT");
            fi;
            extend_needed := false;
            for hi in [1..Length(H_CACHE)] do
                missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, _UnsafeRepsOf(H_CACHE[hi]), LEFT_Q_GROUPS);
                if missing = fail or Length(missing) > 0 then
                    extend_needed := true;
                fi;
            od;
            if extend_needed then
                Print("    [t+", Runtime() - job_t0,
                      "ms] extending RIGHT H_CACHE for new Q-types...\n");
                for hi in [1..Length(H_CACHE)] do
                    missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, _UnsafeRepsOf(H_CACHE[hi]), LEFT_Q_GROUPS);
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

    # ---- Goursat counting + streamed generator emission ----
    # Honor resume state for the resuming job; fresh start for later jobs.
    if job_idx = RESUME_JOB_IDX then
        i_resume_start := RESUME_PAIR_I;
        j_resume_start := RESUME_PAIR_J;
        resume_total_orb := RESUME_TOTAL_ORB;
        resume_total_fix := RESUME_TOTAL_FIX;
        resume_total_cs := RESUME_TOTAL_CS;
    else
        i_resume_start := 1;
        j_resume_start := 1;
        resume_total_orb := 0;
        resume_total_fix := 0;
        resume_total_cs := 0;
    fi;

    # Open this job's generator stream.  Generators are streamed straight to
    # disk (no in-memory fp_lines buffer) -- mirrors GAP_DRIVER and caps the
    # GAP heap at O(1) regardless of class count (the fix for the S20/S21
    # 30 GB workers).  Truncate on a fresh job start; append when resuming
    # mid-job (Python has already truncated CUR_GEN_PATH to right after the
    # last "# cp" checkpoint marker).
    CUR_GEN_PATH := JOB.gens_path;
    if i_resume_start = 1 and j_resume_start = 1 then
        CUR_GEN_STREAM := OutputTextFile(CUR_GEN_PATH, false);
    else
        CUR_GEN_STREAM := OutputTextFile(CUR_GEN_PATH, true);
    fi;
    SetPrintFormattingStatus(CUR_GEN_STREAM, false);

    # In burnside_m2 mode, the ordered-pair iteration visits both (a, b) and
    # (b, a) of each non-diagonal orbit-pair.  These produce S_n-conjugate fp's
    # via swap_perm.  Rather than dedup post-hoc (which requires a fragile
    # GAP `=` test on Group objects without StabChain), we emit only the
    # CANONICAL iteration: h2_orb_idx >= h1_orb_idx.  This gives exactly one
    # rep per unordered orbit-pair {a, b}.  The PREDICTED count
    # (TOTAL_ORB + TOTAL_FIX)/2 from Burnside still uses ALL ordered iterations.

"""
_PAIR_ENGINE_BATCHSUPER = r"""    EmitGen := function(F)
        local gens, s;
        gens := GeneratorsOfGroup(F);
        if Length(gens) > 0 then
            s := JoinStringsWithSeparator(List(gens, String), ",");
        else
            s := "";
        fi;
        WriteAll(CUR_GEN_STREAM, Concatenation("[", s, "]\n"));
    end;

    EmitGenList := function(gens)
        local s;
        if Length(gens) > 0 then
            s := JoinStringsWithSeparator(List(gens, String), ",");
        else
            s := "";
        fi;
        WriteAll(CUR_GEN_STREAM, Concatenation("[", s, "]\n"));
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

    # ---- bench v4: lazy canonical emit tables (DC branch) ----
    EnsureEmitQcanImgs := function(h1orb)
        if not IsBound(h1orb.emit_h_gens) then
            h1orb.emit_h_gens := GeneratorsOfGroup(h1orb.H_ref);
            h1orb.emit_qcan_imgs := List(h1orb.emit_h_gens, g ->
                Image(h1orb.iso_to_can, Image(h1orb.hom, g)));
        fi;
    end;

    EnsureEmitTabs := function(h2orb)
        if not IsBound(h2orb.emit_can_elts) then
            h2orb.emit_can_elts := [];
            h2orb.emit_can_pre := [];
            h2orb.emit_ker_noid := Filtered(
                GeneratorsOfGroup(Kernel(h2orb.shifted_hom)), n -> n <> ());
        fi;
    end;

    EmitTabPreimage := function(h2orb, qc)
        local pos, q2, pre;
        pos := Position(h2orb.emit_can_elts, qc);
        if pos <> fail then return h2orb.emit_can_pre[pos]; fi;
        q2 := PreImagesRepresentative(h2orb.iso_to_can, qc);
        pre := PreImagesRepresentative(h2orb.shifted_hom, q2);
        Add(h2orb.emit_can_elts, qc);
        Add(h2orb.emit_can_pre, pre);
        return pre;
    end;

    # Emit one DC-orbit rep WITHOUT the composed phi: for generator g_k,
    # qc = d^-1(iso_can_h1(hom(g_k))) replicates phi's first two stages, and
    # PreImagesRepresentative(h2.iso_to_can, qc) is the unique preimage —
    # the same element master's Image(phi, ...) produces — so the
    # shifted_hom preimage (and hence the emitted bytes) are identical.
    DCOrbitGenList := function(H1data, h1orb, h2orb, dcs, i)
        local d_inv, gens, k, qc, gen, n;
        EnsureEmitQcanImgs(h1orb);
        EnsureEmitTabs(h2orb);
        d_inv := Inverse(Representative(dcs[i]));
        gens := [];
        for k in [1..Length(h1orb.emit_h_gens)] do
            qc := Image(d_inv, h1orb.emit_qcan_imgs[k]);
            gen := h1orb.emit_h_gens[k] * EmitTabPreimage(h2orb, qc);
            if gen <> () then Add(gens, gen); fi;
        od;
        for n in h2orb.emit_ker_noid do
            Add(gens, n);
        od;
        return gens;
    end;

    # ---- V_4 fast-path (v4opt, 2026-05-18) ----
    # When h1orb.qid = h2orb.qid = [4,0,[4,2]] (V_4) and h2 is Aut-saturated
    # (full_aut=true; the common case for V_4 right factors), replace
    # NaturalHom(H,K) + IsomorphismGroups + Image + PreImagesRepresentative
    # with: ElemAbPQuotient(H,2) once per H1data + GF(2) Gaussian projection
    # per orbit + 4-entry preimage table.  Encoding (a,b) on h1 side uses
    # A/U complement basis; iso to h2.Q=SmallGroup(4,2) uses Pcgs(h2.Q).
    # n_orb=1 (saturated) so any Aut(V_4)-iso choice yields the same orbit:
    # different generator strings than master path, but the same subgroup up
    # to N_G-conjugacy.  Measured: 2.5x on small combo, 4.48x on heavy combo
    # (m_left=15, 4336 H-cache entries) — speedup scales with |H|.
    EnsureLinearADataV4 := function(H1data)
        local A_data;
        if IsBound(H1data.linear_A_data) then
            return H1data.linear_A_data <> fail;
        fi;
        # Guard: ElemAbPQuotient comes from prototype_stage_a.g, loaded only
        # when USE_LINEAR_ORBITS=1.  Fall back to general path otherwise.
        if not IsBound(USE_LINEAR_ORBITS) or USE_LINEAR_ORBITS <> 1 then
            H1data.linear_A_data := fail; return false;
        fi;
        A_data := ElemAbPQuotient(H1data.H, 2);
        if A_data.d < 2 then
            H1data.linear_A_data := fail; return false;
        fi;
        H1data.linear_A_data := A_data;
        H1data.linear_gen_exps := List(H1data.H_gens_noid, g ->
            ExponentsOfPcElement(A_data.pcgs,
                                 Image(A_data.hom, g)) * One(GF(2)));
        return true;
    end;

    EnsureV4FastPathH1 := function(h1orb, H1data)
        local A_data, d, U_vecs, U_basis, pivots, complement, k, v, pcgs_can;
        if IsBound(h1orb.v4_gen_exps) then
            return h1orb.v4_gen_exps <> fail;
        fi;
        if not EnsureLinearADataV4(H1data) then
            h1orb.v4_gen_exps := fail; return false;
        fi;
        A_data := H1data.linear_A_data;
        d := A_data.d;
        U_vecs := List(h1orb.K_gens_noid, g ->
            ExponentsOfPcElement(A_data.pcgs,
                                 Image(A_data.hom, g)) * One(GF(2)));
        U_vecs := Filtered(U_vecs, v -> not IsZero(v));
        if Length(U_vecs) = 0 then
            U_basis := [];
        else
            U_basis := TriangulizedMat(U_vecs);
            U_basis := Filtered(U_basis, v -> not IsZero(v));
        fi;
        if d - Length(U_basis) <> 2 then
            h1orb.v4_gen_exps := fail; return false;
        fi;
        # Fix 2026-05-21: compute v4_gen_exps in CANONICAL Q's pcgs basis via
        # h1orb.iso_to_can.  See GAP_DRIVER EnsureV4FastPathH1 for details.
        EnsureAutQ(h1orb);
        pcgs_can := Pcgs(Range(h1orb.iso_to_can));
        h1orb.v4_gen_exps := List(H1data.H_gens_noid, g ->
            ExponentsOfPcElement(pcgs_can,
                Image(h1orb.iso_to_can,
                      Image(h1orb.hom, g))));
        h1orb.v4_pcgs_can := pcgs_can;
        return true;
    end;

    EnsureV4FastPathH2 := function(h2orb, H2_shifted)
        local pcgs_Q, pcgs_can, can_Q, table, a, b, q_can, q_local;
        if IsBound(h2orb.v4_preimg_table) then
            return h2orb.v4_preimg_table <> fail;
        fi;
        EnsureShiftedHom(h2orb, H2_shifted);
        pcgs_Q := Pcgs(h2orb.Q);
        if pcgs_Q = fail or Length(pcgs_Q) <> 2 then
            h2orb.v4_preimg_table := fail; return false;
        fi;
        # Fix 2026-05-21: index preimg_table by CANONICAL Q's pcgs basis.
        # See GAP_DRIVER EnsureV4FastPathH2 for the basis-mismatch bug.
        EnsureAutQ(h2orb);
        can_Q := Range(h2orb.iso_to_can);
        pcgs_can := Pcgs(can_Q);
        table := EmptyPlist(4);
        for a in [0..1] do
            for b in [0..1] do
                q_can := pcgs_can[1]^a * pcgs_can[2]^b;
                q_local := PreImagesRepresentative(h2orb.iso_to_can, q_can);
                table[2*a + b + 1] :=
                    PreImagesRepresentative(h2orb.shifted_hom, q_local);
            od;
        od;
        h2orb.v4_preimg_table := table;
        h2orb.v4_shifted_kernel_gens_noid := Filtered(
            GeneratorsOfGroup(Kernel(h2orb.shifted_hom)),
            n -> n <> ());
        h2orb.v4_pcgs_can := pcgs_can;
        return true;
    end;

    V4FiberProductGeneratorList := function(H1data, h1orb, h2orb)
        local gens, idx, g, exp_vec, a, b, table_idx, preimg, gen;
        gens := [];
        for idx in [1..Length(H1data.H_gens_noid)] do
            g := H1data.H_gens_noid[idx];
            exp_vec := h1orb.v4_gen_exps[idx];
            a := exp_vec[1]; b := exp_vec[2];
            table_idx := 2*a + b + 1;
            preimg := h2orb.v4_preimg_table[table_idx];
            gen := g * preimg;
            if gen <> () then Add(gens, gen); fi;
        od;
        Append(gens, h2orb.v4_shifted_kernel_gens_noid);
        return gens;
    end;

    # ---- V_4 fast-path generalization (non-saturated h2 case, 2026-05-19) ----
    # When h1.Q = h2.Q = V_4 but h2 is NOT Aut-saturated (e.g. [2,1]_[2,1] right
    # induces only ⟨swap⟩ ⊆ Aut(V_4) = S_3), enumerate Aut(V_4) = GL_2(F_2)
    # double cosets A_1 \ GL_2(F_2) / A_2 directly (≤ 6 reps).  Avoids the
    # general path's IsomorphismGroups + LookupOrComputeDC + per-rep
    # FiberProductGeneratorList through general mappings.
    V4_GL2_ALL := function()
        local F, all, a, b, c, d, MM;
        F := GF(2);
        all := [];
        for a in [0,1] do for b in [0,1] do
        for c in [0,1] do for d in [0,1] do
            MM := [[a, b], [c, d]] * One(F);
            if Determinant(MM) <> Zero(F) then Add(all, MM); fi;
        od; od; od; od;
        return all;
    end;
    V4_GL2_ALL_CACHE := V4_GL2_ALL();

    V4_SubgroupClosure := function(gens)
        local id, elts, frontier, m, g, x;
        id := IdentityMat(2, GF(2));
        elts := [id];
        if Length(gens) = 0 then return elts; fi;
        frontier := ShallowCopy(gens);
        while Length(frontier) > 0 do
            m := Remove(frontier);
            if m in elts then continue; fi;
            Add(elts, m);
            for g in gens do
                x := m * g;
                if not (x in elts) then Add(frontier, x); fi;
            od;
        od;
        return elts;
    end;

    # Induced 2×2 GF(2) matrix of conjugation by s on V_4 = A/U.
    V4_InducedH1MatrixFromStabGen := function(A_data, U_basis, pivots, complement, s)
        local ec, h, h_conj, M_e, reduced, i, induced;
        induced := [[Zero(GF(2)), Zero(GF(2))],
                    [Zero(GF(2)), Zero(GF(2))]];
        for ec in [1, 2] do
            h := PreImagesRepresentative(A_data.hom,
                                          A_data.pcgs[complement[ec]]);
            h_conj := s^-1 * h * s;
            M_e := ExponentsOfPcElement(A_data.pcgs,
                                         Image(A_data.hom, h_conj)) * One(GF(2));
            reduced := ShallowCopy(M_e);
            for i in [1..Length(U_basis)] do
                if not IsZero(reduced[pivots[i]]) then
                    reduced := reduced - U_basis[i];
                fi;
            od;
            induced[1][ec] := reduced[complement[1]];
            induced[2][ec] := reduced[complement[2]];
        od;
        return induced;
    end;

    V4_BuildAMatricesCanonical := function(orb)
        # Fix 2026-05-21: build A matrices in CANONICAL Q's pcgs basis.
        # See GAP_DRIVER V4_BuildAMatricesCanonical for details.
        local pcgs_can, mat_gens, alpha, y1, y2, e1, e2, id;
        pcgs_can := Pcgs(Range(orb.iso_to_can));
        id := IdentityMat(2, GF(2));
        mat_gens := [];
        for alpha in orb.A_gens do
            y1 := Image(alpha, pcgs_can[1]);
            y2 := Image(alpha, pcgs_can[2]);
            e1 := ExponentsOfPcElement(pcgs_can, y1) * One(GF(2));
            e2 := ExponentsOfPcElement(pcgs_can, y2) * One(GF(2));
            Add(mat_gens, [[e1[1], e2[1]], [e1[2], e2[2]]]);
        od;
        mat_gens := Filtered(mat_gens, m -> m <> id);
        return V4_SubgroupClosure(mat_gens);
    end;

    V4_BuildA1Matrices := function(h1orb, H1data)
        if IsBound(h1orb.v4_A1_matrices) then return h1orb.v4_A1_matrices; fi;
        EnsureAutQ(h1orb);
        h1orb.v4_A1_matrices := V4_BuildAMatricesCanonical(h1orb);
        return h1orb.v4_A1_matrices;
    end;

    V4_BuildA2Matrices := function(h2orb)
        if IsBound(h2orb.v4_A2_matrices) then return h2orb.v4_A2_matrices; fi;
        EnsureAutQ(h2orb);
        h2orb.v4_A2_matrices := V4_BuildAMatricesCanonical(h2orb);
        return h2orb.v4_A2_matrices;
    end;

    V4_DoubleCosetReps := function(A1, A2)
        local seen, reps, M_iter, a1, a2, prod;
        seen := [];
        reps := [];
        for M_iter in V4_GL2_ALL_CACHE do
            if M_iter in seen then continue; fi;
            Add(reps, M_iter);
            # M maps the LEFT V_4 quotient to the RIGHT V_4 quotient, so the
            # target normalizer acts on the left and the source normalizer on
            # the right.  This matches the generic A2 \ Aut(Q) / A1 path.
            for a1 in A1 do
                for a2 in A2 do
                    prod := a2 * M_iter * a1;
                    if not (prod in seen) then Add(seen, prod); fi;
                od;
            od;
        od;
        return reps;
    end;

    V4FiberProductGeneratorList_M := function(H1data, h1orb, h2orb, M)
        local M_int, gens, idx, g, exp_vec, a, b, ap, bp,
              table_idx, preimg, gen;
        M_int := [[IntFFE(M[1][1]), IntFFE(M[1][2])],
                  [IntFFE(M[2][1]), IntFFE(M[2][2])]];
        gens := [];
        for idx in [1..Length(H1data.H_gens_noid)] do
            g := H1data.H_gens_noid[idx];
            exp_vec := h1orb.v4_gen_exps[idx];
            a := exp_vec[1]; b := exp_vec[2];
            ap := (M_int[1][1] * a + M_int[1][2] * b) mod 2;
            bp := (M_int[2][1] * a + M_int[2][2] * b) mod 2;
            table_idx := 2*ap + bp + 1;
            preimg := h2orb.v4_preimg_table[table_idx];
            gen := g * preimg;
            if gen <> () then Add(gens, gen); fi;
        od;
        Append(gens, h2orb.v4_shifted_kernel_gens_noid);
        return gens;
    end;

    # ---- V_4 saturated Frattini fast-path (Opt v4f, 2026-05-22) ----
    # See GAP_DRIVER for design notes; identical semantics.
    V4_FratKDataForOrb := function(Hdata, orb)
        local A_data, d, U_vecs, U_basis, pivots, vec, j, pivot_set, complement;
        if IsBound(orb.v4_frat_kdata) then return orb.v4_frat_kdata; fi;
        if not EnsureLinearADataV4(Hdata) then
            orb.v4_frat_kdata := fail; return fail;
        fi;
        A_data := Hdata.linear_A_data;
        d := A_data.d;
        U_vecs := List(orb.K_gens_noid, g ->
            ExponentsOfPcElement(A_data.pcgs,
                                 Image(A_data.hom, g)) * One(GF(2)));
        U_vecs := Filtered(U_vecs, v -> not IsZero(v));
        if Length(U_vecs) = 0 then
            U_basis := [];
        else
            U_basis := TriangulizedMat(U_vecs);
            U_basis := Filtered(U_basis, v -> not IsZero(v));
        fi;
        if d - Length(U_basis) <> 2 then
            orb.v4_frat_kdata := fail; return fail;
        fi;
        pivots := [];
        for vec in U_basis do
            for j in [1..d] do
                if not IsZero(vec[j]) then Add(pivots, j); break; fi;
            od;
        od;
        pivot_set := Set(pivots);
        complement := Filtered([1..d], j -> not (j in pivot_set));
        orb.v4_frat_kdata := rec(
            A_data := A_data, U_basis := U_basis,
            pivots := pivots, complement := complement, d := d);
        return orb.v4_frat_kdata;
    end;

    V4_FratReduce := function(kdata, v)
        local reduced, i;
        reduced := ShallowCopy(v);
        for i in [1..Length(kdata.U_basis)] do
            if not IsZero(reduced[kdata.pivots[i]]) then
                reduced := reduced - kdata.U_basis[i];
            fi;
        od;
        return [IntFFE(reduced[kdata.complement[1]]),
                IntFFE(reduced[kdata.complement[2]])];
    end;

    V4_FratInducedMat := function(kdata, s)
        local mat, ec, h, h_conj, v, reduced, i;
        mat := [[Zero(GF(2)), Zero(GF(2))],
                [Zero(GF(2)), Zero(GF(2))]];
        for ec in [1, 2] do
            h := PreImagesRepresentative(kdata.A_data.hom,
                                          kdata.A_data.pcgs[kdata.complement[ec]]);
            h_conj := s^-1 * h * s;
            v := ExponentsOfPcElement(kdata.A_data.pcgs,
                                       Image(kdata.A_data.hom, h_conj)) * One(GF(2));
            reduced := ShallowCopy(v);
            for i in [1..Length(kdata.U_basis)] do
                if not IsZero(reduced[kdata.pivots[i]]) then
                    reduced := reduced - kdata.U_basis[i];
                fi;
            od;
            mat[1][ec] := reduced[kdata.complement[1]];
            mat[2][ec] := reduced[kdata.complement[2]];
        od;
        return mat;
    end;

    EnsureV4FullAutFrat := function(orb, Hdata)
        local kdata, id, mats, s, mat;
        if IsBound(orb.v4_full_aut_frat) then return orb.v4_full_aut_frat; fi;
        kdata := V4_FratKDataForOrb(Hdata, orb);
        if kdata = fail then orb.v4_full_aut_frat := false; return false; fi;
        id := IdentityMat(2, GF(2));
        mats := [];
        for s in GeneratorsOfGroup(orb.Stab) do
            mat := V4_FratInducedMat(kdata, s);
            if mat <> id then Add(mats, mat); fi;
        od;
        orb.v4_full_aut_frat := (Size(V4_SubgroupClosure(mats)) = 6);
        return orb.v4_full_aut_frat;
    end;

    EnsureV4FastPathH1Frat := function(h1orb, H1data)
        local kdata;
        if IsBound(h1orb.v4_gen_exps_frat) then
            return h1orb.v4_gen_exps_frat <> fail;
        fi;
        kdata := V4_FratKDataForOrb(H1data, h1orb);
        if kdata = fail then h1orb.v4_gen_exps_frat := fail; return false; fi;
        h1orb.v4_gen_exps_frat := List(H1data.linear_gen_exps, v ->
            V4_FratReduce(kdata, v));
        return true;
    end;

    EnsureV4FastPathH2Frat := function(h2orb, H2data)
        local kdata, A_data, c1, c2, r1, r2, r1_sh, r2_sh, table, a, b;
        if IsBound(h2orb.v4_preimg_table_frat) then
            return h2orb.v4_preimg_table_frat <> fail;
        fi;
        kdata := V4_FratKDataForOrb(H2data, h2orb);
        if kdata = fail then h2orb.v4_preimg_table_frat := fail; return false; fi;
        A_data := kdata.A_data;
        c1 := kdata.complement[1]; c2 := kdata.complement[2];
        r1 := PreImagesRepresentative(A_data.hom, A_data.pcgs[c1]);
        r2 := PreImagesRepresentative(A_data.hom, A_data.pcgs[c2]);
        r1_sh := r1^shift_R; r2_sh := r2^shift_R;
        table := EmptyPlist(4);
        for a in [0..1] do
            for b in [0..1] do
                table[2*a + b + 1] := r1_sh^a * r2_sh^b;
            od;
        od;
        h2orb.v4_preimg_table_frat := table;
        EnsureShiftedKGenerators(h2orb);
        return true;
    end;

    V4FratFiberProductGeneratorList := function(H1data, h1orb, h2orb)
        local gens, idx, g, exp_vec, preimg, gen;
        gens := [];
        for idx in [1..Length(H1data.H_gens_noid)] do
            g := H1data.H_gens_noid[idx];
            exp_vec := h1orb.v4_gen_exps_frat[idx];
            preimg := h2orb.v4_preimg_table_frat[2*exp_vec[1] + exp_vec[2] + 1];
            gen := g * preimg;
            if gen <> () then Add(gens, gen); fi;
        od;
        Append(gens, h2orb.shifted_K_gens_noid);
        return gens;
    end;

    # Per-job V_4 fast-path emit counter.
    BENCH_V4FAST := rec(n_emits := 0, n_emits_nonsat := 0, n_emits_frat := 0);

    ProcessPairBatch := function(H1data, H2data, H1, H2)
        local total, swap_fixed, h1orb, h2idxs, h2idx, h2orb, key, isoTH,
              isos, n, gensQ, KeyOf, idx, seen, n_orb, queue, j, phi,
              alpha, beta, neighbor, nkey, k, fp, orbit_id, i, swap_phi,
              swap_key, swap_iso_idx, swap_orbit_id,
              h1_orb_idx, orbit_reps_phi, h_0, t_0, swap_orb_id_arr,
              gens_for_fp,
              dcs, A1, A2_in_h1, A2_in_h1_gens, tinv, g_swap,
              v4_A1, v4_A2, v4_reps, v4_M,
              bench_t0, bench_t1, h2_shifted_hom,
              NL, NR, fact_M, cs_combo, cs_rep, autQ_size_or_dc, is_self_swap;
        total := 0; swap_fixed := 0;
        fact_M := Factorial(ML + MR);
        cs_combo := 0;
        # HARVEST: NL/NR are PER-ORBIT (|h1orb.Stab|, |h2orb.Stab|), set in the
        # loops below.  Using H[12]data.N would give wrong cs when K is not
        # normal in H (e.g. non-normal C_2's in V_4).
        for h1_orb_idx in [1..Length(H1data.orbits)] do
            h1orb := H1data.orbits[h1_orb_idx];
            key := String(h1orb.qid);
            if not IsBound(H2data.byqid.(key)) then continue; fi;
            h2idxs := H2data.byqid.(key);
            if not IsBound(h1orb.Stab_size) or h1orb.Stab_size = fail then
                h1orb.Stab_size := Size(h1orb.Stab);
            fi;
            NL := h1orb.Stab_size;

            # Canonical-emission gate for burnside_m2: only emit when
            # h2idx >= h1_orb_idx so each unordered orbit-pair {a,b} is
            # emitted exactly once.  Counters increment on ALL ordered pairs
            # (so PREDICTED via Burnside formula remains correct).
            if h1orb.qsize = 1 then
                for h2idx in h2idxs do
                    h2orb := H2data.orbits[h2idx];
                    if not IsBound(h2orb.Stab_size) or h2orb.Stab_size = fail then
                    h2orb.Stab_size := Size(h2orb.Stab);
                fi;
                NR := h2orb.Stab_size;
                    if h2orb.qsize = 1 then
                        total := total + 1;
                        is_self_swap := (BURNSIDE_M2 = 1 and h1orb.K = h2orb.K);
                        if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                            cs_rep := fact_M / (NL * NR);
                            if is_self_swap then cs_rep := cs_rep / 2; fi;
                            cs_combo := cs_combo + cs_rep;
                            EmitGenList(Concatenation(H1data.H_gens_noid,
                                                      H2data.shifted_H_gens_noid));
                        fi;
                        if is_self_swap then
                            swap_fixed := swap_fixed + 1;
                        fi;
                    fi;
                od;
                continue;
            fi;

            if h1orb.qsize = 2 then
                # Opt #3: see single-call ProcessPair for derivation.  Bug
                # initially attributed here was actually peel_c2_pair routing
                # gate, fixed in route.py.  Re-restored 2026-05-23.
                if true then   # opt #3: direct construction for any MR (was: MR = 2)
                    for h2idx in h2idxs do
                        h2orb := H2data.orbits[h2idx];
                        if not IsBound(h2orb.Stab_size) or h2orb.Stab_size = fail then
                    h2orb.Stab_size := Size(h2orb.Stab);
                fi;
                NR := h2orb.Stab_size;
                        if h2orb.qsize <> 2 then continue; fi;
                        total := total + 1;
                        is_self_swap := (BURNSIDE_M2 = 1 and h1orb.K = h2orb.K);
                        if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                            cs_rep := fact_M / (NL * NR);
                            if is_self_swap then cs_rep := cs_rep / 2; fi;
                            cs_combo := cs_combo + cs_rep;
                            EnsureC2Representative(h1orb);
                            EnsureShiftedKGenerators(h2orb);
                            EnsureShiftedC2Representative(h2orb);
                            EmitGenList(Concatenation(
                                h1orb.K_gens_noid,
                                h2orb.shifted_K_gens_noid,
                                [h1orb.c2_rep * h2orb.shifted_c2_rep]));
                        fi;
                        if is_self_swap then
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
                if not IsBound(h2orb.Stab_size) or h2orb.Stab_size = fail then
                    h2orb.Stab_size := Size(h2orb.Stab);
                fi;
                NR := h2orb.Stab_size;
                if h2orb.qsize <> h1orb.qsize then continue; fi;
                # V_4 (qid=[4,0,[4,2]]) fast-path: when both sides are V_4 and
                # h2 is Aut-saturated, skip the IsomorphismGroups/Image/
                # PreImagesRepresentative machinery in favor of pcgs+table.
                if h1orb.qid = [4, 0, [4, 2]]
                   and h2orb.qid = [4, 0, [4, 2]] then
                    # Opt v4f (2026-05-22): saturated Frattini path first
                    # (no AutQ).  See GAP_DRIVER for design.
                    if EnsureV4FullAutFrat(h2orb, H2data)
                       and EnsureV4FastPathH1Frat(h1orb, H1data)
                       and EnsureV4FastPathH2Frat(h2orb, H2data) then
                        total := total + 1;
                        is_self_swap := (BURNSIDE_M2 = 1 and h1orb.K = h2orb.K);
                        # HARVEST: V_4 Frattini saturated, |Aut(V_4)|=6.
                        if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                            cs_rep := fact_M * 6 / (NL * NR);
                            if is_self_swap then cs_rep := cs_rep / 2; fi;
                            cs_combo := cs_combo + cs_rep;
                            EmitGenList(V4FratFiberProductGeneratorList(
                                H1data, h1orb, h2orb));
                            BENCH_V4FAST.n_emits_frat :=
                                BENCH_V4FAST.n_emits_frat + 1;
                        fi;
                        if is_self_swap then
                            swap_fixed := swap_fixed + 1;
                        fi;
                        continue;
                    fi;
                    if EnsureV4FastPathH2(h2orb, H2) then
                        EnsureAutQ(h2orb);
                        if h2orb.full_aut = true
                           and EnsureV4FastPathH1(h1orb, H1data) then
                            total := total + 1;
                            is_self_swap := (BURNSIDE_M2 = 1 and h1orb.K = h2orb.K);
                            # HARVEST: V_4 canonical saturated.
                            if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                                cs_rep := fact_M * 6 / (NL * NR);
                                if is_self_swap then cs_rep := cs_rep / 2; fi;
                                cs_combo := cs_combo + cs_rep;
                                EmitGenList(V4FiberProductGeneratorList(
                                    H1data, h1orb, h2orb));
                                BENCH_V4FAST.n_emits :=
                                    BENCH_V4FAST.n_emits + 1;
                            fi;
                            if is_self_swap then
                                swap_fixed := swap_fixed + 1;
                            fi;
                            continue;
                        elif BURNSIDE_M2 = 0
                             and EnsureV4FastPathH1(h1orb, H1data) then
                            # Non-saturated V_4 fast path: enumerate
                            # A_1 \ GL_2(F_2) / A_2 double cosets directly,
                            # one fiber product per rep. Skips the
                            # IsomorphismGroups + LookupOrComputeDC machinery.
                            # V4_BuildA1Matrices uses h1orb.Stab directly,
                            # bypassing EnsureAutQ's InducedAutomorphism work.
                            v4_A1 := V4_BuildA1Matrices(h1orb, H1data);
                            v4_A2 := V4_BuildA2Matrices(h2orb);
                            v4_reps := V4_DoubleCosetReps(v4_A1, v4_A2);
                            total := total + Length(v4_reps);
                            # HARVEST: V_4 non-saturated.  Per v4_M compute dc size
                            # = |A1.M.A2| (BURNSIDE_M2=0 only here).
                            for v4_M in v4_reps do
                                seen := [];
                                for alpha in v4_A1 do
                                    for beta in v4_A2 do
                                        phi := beta * v4_M * alpha;
                                        if not (phi in seen) then Add(seen, phi); fi;
                                    od;
                                od;
                                cs_rep := fact_M * Length(seen) / (NL * NR);
                                cs_combo := cs_combo + cs_rep;
                                EmitGenList(V4FiberProductGeneratorList_M(
                                    H1data, h1orb, h2orb, v4_M));
                                BENCH_V4FAST.n_emits_nonsat :=
                                    BENCH_V4FAST.n_emits_nonsat + 1;
                            od;
                            continue;
                        fi;
                    fi;
                fi;
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
                    # A2 in canonical Aut(Q): h1orb/h2orb share qid => same
                    # canonical Q + AutQ object, so h2orb.A_gens ARE A_2 already.
                    # Must match the canonical emit base J = h2.iso_to_can o
                    # h1.iso_to_can^-1; do NOT transport via the arbitrary isoTH
                    # (that conjugates A2 -> same count but non-transversal reps).
                    # See ProcessPair (GAP_DRIVER) / _dc_consistency_probe.g.
                    A2_in_h1 := SafeSub(h1orb.AutQ, h2orb.A_gens);
                    dcs := LookupOrComputeDC(h1orb, A1, A2_in_h1);
                    n_orb := Length(dcs);
                    # bench v4: skip the per-orbit composed-GeneralMapping
                    # construction; the DC-branch emit goes through
                    # DCOrbitGenList (canonical tables + Representative(dc)).
                    orbit_reps_phi := fail;
                fi;
                total := total + n_orb;
                # HARVEST: saturated branch uses |AutQ| as effective |dcs|.
                if Length(dcs) = 0 then
                    autQ_size_or_dc := Size(h2orb.AutQ);
                fi;

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
                        # Self-pair swap = transpose gluing psi -> psi^-1 in
                        # canonical Aut(Qcan); orbit i swap-fixed iff psi_i^-1 is
                        # in its own coset.  No isoTH.  See ProcessPair (GAP_DRIVER)
                        # / _swap_probe.g.
                        gensQ := GeneratorsOfGroup(Range(h1orb.iso_to_can));
                        for i in [1..n_orb] do
                            g_swap := Inverse(Representative(dcs[i]));
                            g_swap := GroupHomomorphismByImagesNC(
                                Range(h1orb.iso_to_can), Range(h1orb.iso_to_can),
                                gensQ, List(gensQ, q -> Image(g_swap, q)));
                            SetIsBijective(g_swap, true);
                            swap_orb_id_arr[i] :=
                                PositionProperty(dcs, dc -> g_swap in dc);
                        od;
                    fi;
                fi;

                # HARVEST: closed-form pair contribution (see ProcessPair).
                if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                    if Length(dcs) = 0 then
                        cs_rep := fact_M * autQ_size_or_dc / (NL * NR);
                    else
                        cs_rep := fact_M * Size(h2orb.AutQ) / (NL * NR);
                    fi;
                    if BURNSIDE_M2 = 1 and h2idx = h1_orb_idx then
                        cs_rep := cs_rep / 2;
                    fi;
                    cs_combo := cs_combo + cs_rep;
                fi;
                # Emit orbit reps (canonical-gated).
                if BURNSIDE_M2 = 0 or h2idx > h1_orb_idx then
                    for i in [1..n_orb] do
                        if orbit_reps_phi = fail then
                            gens_for_fp := DCOrbitGenList(
                                H1data, h1orb, h2orb, dcs, i);
                        else
                            gens_for_fp := FiberProductGeneratorList(
                                H1data, h1orb, h2orb,
                                InverseGeneralMapping(orbit_reps_phi[i]));
                        fi;
                        EmitGenList(gens_for_fp);
                    od;
                elif BURNSIDE_M2 = 1 and h2idx = h1_orb_idx then
                    for i in [1..n_orb] do
                        if swap_orb_id_arr[i] >= i then
                            if orbit_reps_phi = fail then
                                gens_for_fp := DCOrbitGenList(
                                    H1data, h1orb, h2orb, dcs, i);
                            else
                                gens_for_fp := FiberProductGeneratorList(
                                    H1data, h1orb, h2orb,
                                    InverseGeneralMapping(orbit_reps_phi[i]));
                            fi;
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
        return rec(orbits := total, swap_fixed := swap_fixed,
                   class_sum := cs_combo);
    end;
"""
_LOOP_BATCH = r"""
    TOTAL_ORB := resume_total_orb;
    TOTAL_FIX := resume_total_fix;
    TOTAL_CS_SUM := resume_total_cs;
    last_hb_ms := Runtime() - job_t0;
    n_pairs_done := (i_resume_start - 1) * Length(H2DATA);
    n_pairs_total := N_LEFT * Length(H2DATA);
    if i_resume_start > 1 then
        Print("    [t+", Runtime() - job_t0, "ms] resuming pair loop at i=",
              i_resume_start, "/", N_LEFT,
              " (", n_pairs_done, " pairs already done, orb=", TOTAL_ORB, ")\n");
    else
        Print("    [t+", Runtime() - job_t0, "ms] starting H1xH2 loop: ",
              N_LEFT, " x ", Length(H2DATA),
              " = ", n_pairs_total, " pairs\n");
    fi;
    # HOTFIX 2026-06-12: reset the checkpoint timer to EXCLUDE cache/setup load
    # (the RIGHT H-cache rebuild can take 60-107 min).  The checkpoint interval
    # and floor must measure only useful pair-loop work; otherwise a sub-second
    # pair loop inherits ~100 min of "elapsed" from setup, trips the 2h wall
    # backstop immediately, and restarts -> redoing the whole rebuild.
    WORKER_START := Runtime();
    WORKER_START_WALL := NanosecondsSinceEpoch();
    # Optimization (4) 2026-04-28: precompute shifted RIGHT once per j outside
    # the i loop.  For burnside_m2 mode, H2DATA[1] gets overwritten per-i so
    # we must compute per-pair (only 1 entry, so cheap).
    if BURNSIDE_M2 = 0 then
        for H2data_j in H2DATA do EnsureShiftedHData(H2data_j); od;
        H2_SHIFTED := List(H2DATA, hd -> hd.shifted_H);
    fi;
    for i in [i_resume_start..N_LEFT] do
        # LAZY_LEFT_RECON=1: reconstruct this LEFT entry on demand; it is
        # discarded after the inner j-loop (the Opt-10 cache clear below)
        # rather than retained in H1DATA_LIST.  O(1) vs O(N_LEFT) reconstructed
        # footprint; see the build block above.  USE_WINDOWED_LEFT: the entry is
        # read from the framed cache on demand (seek to its byte offset) -- no
        # full cache in memory; see the windowed-LEFT branch above.
        if USE_WINDOWED_LEFT then
            H1data_j := ReconstructHData(GetHCacheEntry(i), S_ML);
        elif LAZY_LEFT_RECON = 1 then
            H1data_j := ReconstructHData(H_CACHE_L[i], S_ML);
        else
            H1data_j := H1DATA_LIST[i];
        fi;
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
            TOTAL_CS_SUM := TOTAL_CS_SUM + res_pair.class_sum;
            n_pairs_done := n_pairs_done + 1;
            N_PAIRS_EPOCH := N_PAIRS_EPOCH + 1;
            if (Runtime() - job_t0) - last_hb_ms >= 30000 then
                Print("    [t+", Runtime() - job_t0, "ms] pair ",
                      n_pairs_done, "/", n_pairs_total,
                      " (i=", i, "/", N_LEFT,
                      ", j=", j, "/", Length(H2DATA), ") ",
                      "orb_so_far=", TOTAL_ORB, "\n");
                last_hb_ms := Runtime() - job_t0;
            fi;
            # Soft state save (no exit) every STATE_SAVE_INTERVAL_MS.  Caps
            # work loss from unplanned crashes (OOM etc.) to the soft-save
            # interval rather than up to CHECKPOINT_INTERVAL_MS (= the gap
            # between the previous hard checkpoint and now).  Drops a "# cp"
            # marker into the (already on-disk) gens stream + a minimal state.g;
            # the gens file is the durable payload.  Skips on last pair.
            if STATE_FILE <> "" and STATE_SAVE_INTERVAL_MS > 0
               and Runtime() - LAST_STATE_SAVE_MS >= STATE_SAVE_INTERVAL_MS
               and (j < Length(H2DATA) or i < N_LEFT) then
                next_i := i;
                next_j := j + 1;
                if next_j > Length(H2DATA) then
                    next_i := i + 1;
                    next_j := 1;
                fi;
                # Self-describing checkpoint marker: NEXT pair coords + cumulative
                # totals.  Flush the gens stream so everything through this marker
                # is on disk, reopen for continued appends, then drop a minimal
                # state.g (job_idx only).  On resume Python truncates the gens
                # file to this marker and rebuilds RESUME_STATE from it, making
                # the gens file the single crash-consistent source of truth.
                WriteAll(CUR_GEN_STREAM, Concatenation(
                    "# cp ni=", String(next_i), " nj=", String(next_j),
                    " orb=", String(TOTAL_ORB), " fix=", String(TOTAL_FIX),
                    " cs=", String(TOTAL_CS_SUM), "\n"));
                CloseStream(CUR_GEN_STREAM);
                CUR_GEN_STREAM := OutputTextFile(CUR_GEN_PATH, true);
                SetPrintFormattingStatus(CUR_GEN_STREAM, false);
                tmp := Concatenation(STATE_FILE, ".tmp");
                PrintTo(tmp, "RESUME_STATE := rec( job_idx := ", job_idx, " );\n");
                Exec(Concatenation("mv -f -- '", tmp, "' '", STATE_FILE, "'"));
                LAST_STATE_SAVE_MS := Runtime();
                Print("[soft_checkpoint] job_idx=", job_idx,
                      " pair_i=", next_i, "/", N_LEFT,
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
            if STATE_FILE <> ""
               and ( (MAX_PAIRS_PER_CKPT > 0 and N_PAIRS_EPOCH >= MAX_PAIRS_PER_CKPT)
                     or (CHECKPOINT_INTERVAL_MS > 0 and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CHECKPOINT_INTERVAL_MS)
                     or (CKPT_TIME_FLOOR_MS > 0 and CKPT_PAIR_GRAN > 0 and N_PAIRS_EPOCH > 0
                         and N_PAIRS_EPOCH mod CKPT_PAIR_GRAN = 0
                         and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CKPT_TIME_FLOOR_MS)
                     or (MAX_WORKSPACE_KB > 0 and CKPT_PAIR_GRAN > 0 and N_PAIRS_EPOCH > 0
                         and N_PAIRS_EPOCH mod CKPT_PAIR_GRAN = 0
                         and CurrentWorkspaceKB() >= MAX_WORKSPACE_KB) )
               and (j < Length(H2DATA) or i < N_LEFT) then
                next_i := i;
                next_j := j + 1;
                if next_j > Length(H2DATA) then
                    next_i := i + 1;
                    next_j := 1;
                fi;
                # Self-describing checkpoint marker (see soft-save above), then a
                # minimal state.g.  Flush + close the gens stream before QuitGap
                # so the marker is durably on disk.
                WriteAll(CUR_GEN_STREAM, Concatenation(
                    "# cp ni=", String(next_i), " nj=", String(next_j),
                    " orb=", String(TOTAL_ORB), " fix=", String(TOTAL_FIX),
                    " cs=", String(TOTAL_CS_SUM), "\n"));
                CloseStream(CUR_GEN_STREAM);
                tmp := Concatenation(STATE_FILE, ".tmp");
                PrintTo(tmp, "RESUME_STATE := rec( job_idx := ", job_idx, " );\n");
                Exec(Concatenation("mv -f -- '", tmp, "' '", STATE_FILE, "'"));
                Print("CHECKPOINT_PAUSE job_idx=", job_idx,
                      " next_pair_i=", next_i,
                      " next_pair_j=", next_j,
                      " of=", N_LEFT, "x", Length(H2DATA),
                      " orb=", TOTAL_ORB,
                      " elapsed_ms=", Runtime() - WORKER_START, "\n");
                LogTo();
                QuitGap();
            fi;
        od;
        # Opt 10 (2026-05-23): clear per-orbit LAZY caches on processed entry
        # to keep heap small.  Without this, GC time grows with accumulated
        # caches and per-orbit cost climbs from ~5 ms at cycle start to ~30+
        # by minute 60.  Verified correct via smoke3 vs smoke2 byte-identical
        # diff: opt #10 contributes 0 to FPF count when used in isolation.
        # IMPORTANT: also clear v4_frat_kdata (it caches a reference to
        # H1data.linear_A_data) — without this, cross-job calls in multi-job
        # batches would use stale cached kdata.  Do NOT clear H1data.linear_*
        # (H-level not orbit-level, minimal heap impact, breaks downstream).
        for orb in H1data_j.orbits do
            orb.AutQ := fail;
            orb.A_gens := [];
            orb.raw_A_gens := [];
            orb.iso_to_can := fail;
            orb.full_aut := fail;
            orb.hom := fail;
            orb.Q := fail;
            orb.shifted_hom := fail;
            orb.shifted_K_gens_noid := fail;
            orb.c2_rep := fail;
            orb.shifted_c2_rep := fail;
            orb.dc_cache := fail;
            if IsBound(orb.v4_A1_matrices) then Unbind(orb.v4_A1_matrices); fi;
            if IsBound(orb.v4_A2_matrices) then Unbind(orb.v4_A2_matrices); fi;
            if IsBound(orb.v4_gen_exps) then Unbind(orb.v4_gen_exps); fi;
            if IsBound(orb.v4_pcgs_can) then Unbind(orb.v4_pcgs_can); fi;
            if IsBound(orb.v4_full_aut_frat) then Unbind(orb.v4_full_aut_frat); fi;
            if IsBound(orb.v4_gen_exps_frat) then Unbind(orb.v4_gen_exps_frat); fi;
            if IsBound(orb.v4_frat_kdata) then Unbind(orb.v4_frat_kdata); fi;
            if IsBound(orb.v4_preimg_table) then Unbind(orb.v4_preimg_table); fi;
            if IsBound(orb.v4_preimg_table_frat) then Unbind(orb.v4_preimg_table_frat); fi;
            if IsBound(orb.v4_shifted_kernel_gens_noid) then Unbind(orb.v4_shifted_kernel_gens_noid); fi;
            if IsBound(orb.emit_h_gens) then Unbind(orb.emit_h_gens); fi;
            if IsBound(orb.emit_qcan_imgs) then Unbind(orb.emit_qcan_imgs); fi;
            if IsBound(orb.emit_can_elts) then Unbind(orb.emit_can_elts); fi;
            if IsBound(orb.emit_can_pre) then Unbind(orb.emit_can_pre); fi;
            if IsBound(orb.emit_ker_noid) then Unbind(orb.emit_ker_noid); fi;
        od;
        H1data_j.shifted_H := fail;
        H1data_j.shifted_H_gens_noid := fail;
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
    # Flush this job's streamed generators, then assemble the final .g:
    # header (counts are known now) + the streamed gen lines with the "# cp"
    # checkpoint markers stripped, so the body is byte-identical to the old
    # in-memory fp_lines join.  grep streams the body at O(1) memory; "|| true"
    # absorbs grep's exit-1 when a 0-class combo leaves no "[" lines to keep.
    CloseStream(CUR_GEN_STREAM);
    OUT_STREAM := OutputTextFile(TMP_OUT, false);
    SetPrintFormattingStatus(OUT_STREAM, false);
    WriteAll(OUT_STREAM, Concatenation(COMBO_HEADER, "\n"));
    WriteAll(OUT_STREAM, Concatenation("# candidates: ", String(PREDICTED), "\n"));
    WriteAll(OUT_STREAM, Concatenation("# deduped: ", String(PREDICTED), "\n"));
    WriteAll(OUT_STREAM, Concatenation("# elapsed_ms: ", String(elapsed_ms), "\n"));
    WriteAll(OUT_STREAM, Concatenation("# class_sum: ", String(TOTAL_CS_SUM), "\n"));
    CloseStream(OUT_STREAM);
    Exec(Concatenation("grep -v '^#' '", CUR_GEN_PATH, "' >> '", TMP_OUT, "' || true"));
    Exec(Concatenation("mv -f -- '", TMP_OUT, "' '", OUTPUT_PATH, "'"));
    RemoveFile(CUR_GEN_PATH);

    Print("[dc_global] hits=", DC_GLOBAL.n_hit,
          " misses=", DC_GLOBAL.n_miss, "\n");
    Print("RESULT idx=", job_idx, " predicted=", PREDICTED,
          " orbits=", TOTAL_ORB, " swap_fixed=", TOTAL_FIX,
          " class_sum=", TOTAL_CS_SUM,
          " elapsed_ms=", elapsed_ms,
          " v4fast_emits=", BENCH_V4FAST.n_emits,
      " v4fast_nonsat=", BENCH_V4FAST.n_emits_nonsat,
      " v4fast_frat=", BENCH_V4FAST.n_emits_frat, "\n");

    # Between-JOB checkpoint: after RESULT is written, if elapsed exceeds
    # threshold and there are more jobs, save state with the NEXT job_idx
    # (fresh pair state) and quit.  Bounds heap to one JOB's worth.  Pair-loop
    # checkpoint can't fire when n_left = 1 or 2 (its `i < n_left` gate is
    # false at end of last i), so this is the only between-job heap reset.
    if STATE_FILE <> ""
       and ( (MAX_PAIRS_PER_CKPT > 0 and N_PAIRS_EPOCH >= MAX_PAIRS_PER_CKPT)
             or (CHECKPOINT_INTERVAL_MS > 0 and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CHECKPOINT_INTERVAL_MS)
             or (CKPT_TIME_FLOOR_MS > 0 and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CKPT_TIME_FLOOR_MS)
             or (MAX_WORKSPACE_KB > 0 and CurrentWorkspaceKB() >= MAX_WORKSPACE_KB) )
       and job_idx < Length(JOBS) then
        tmp := Concatenation(STATE_FILE, ".tmp");
        PrintTo(tmp, "RESUME_STATE := rec( job_idx := ", job_idx + 1, " );\n");
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
_PREAMBLE_SUPER = r"""
LogTo("__LOG__");
SizeScreen([100000, 24]);

# Linear-orbits flag + Stage A/B/C prototype load.  See BATCH_DRIVER for details.
USE_LINEAR_ORBITS := __USE_LINEAR_ORBITS__;
USE_STAGE_D := __USE_STAGE_D__;
if USE_LINEAR_ORBITS = 1 then
    Print("[USE_LINEAR_ORBITS=1] loading Stage A/B/C prototypes...\n");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_a.g");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_b.g");
    Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_c.g");
    if USE_STAGE_D = 1 then
        Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_d.g");
    fi;
fi;

if not IsBound(_GoursatBuildFiberProduct) then Read("__LIFTING_G__"); fi;

# Lazy LEFT reconstruction toggle (PRED_LAZY_LEFT_RECON; default 0).  Mirrors
# _PREAMBLE_BATCH: when 1, skip the eager per-group H1DATA_LIST build and
# reconstruct each H1data per-i inside the pair loop.  See _HEADER_SUPER /
# _LOOP_SUPER below.
LAZY_LEFT_RECON := __LAZY_LEFT_RECON__;
FRAMED_CACHE := __FRAMED_CACHE__;   # 1 => write windowable framed cache (+ .idx)
# Streaming H-cache build (PRED_STREAM_HCACHE_BUILD; requires FRAMED_CACHE=1).
# See BuildHCacheStreaming in the shared helpers.
STREAM_HCACHE_BUILD := __STREAM_HCACHE_BUILD__;
BUILD_TOKEN := "__BUILD_TOKEN__";            # process-private .building suffix
HCACHE_BUILD_VER := "__HCACHE_BUILD_VER__";  # entry-content version marker
STREAM_WINDOW_MIN := __STREAM_WINDOW_MIN__;  # BATCH: windowed pair loop at >= this many entries

# Hard checkpoint-restart policy (see _PREAMBLE_BATCH): restart on
# MAX_PAIRS_PER_CKPT pairs, OR CHECKPOINT_INTERVAL_MS wall (2h backstop), OR at a
# CKPT_PAIR_GRAN-pair boundary once CKPT_TIME_FLOOR_MS wall has passed.
MAX_PAIRS_PER_CKPT := __MAX_PAIRS_PER_CKPT__;
CKPT_TIME_FLOOR_MS := __CKPT_TIME_FLOOR_MS__;
CKPT_PAIR_GRAN     := __CKPT_PAIR_GRAN__;
MAX_WORKSPACE_KB   := __MAX_WORKSPACE_KB__;   # 0 = disabled; else checkpoint-restart the epoch when GAP workspace >= this many KB
N_PAIRS_EPOCH := 0;

"""
_HEADER_SUPER = r"""
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
# Per-(group,job) streamed-generator output (set per job in the loop below).
# Replaces the old in-memory fp_lines buffer (the S20/S21 30 GB driver).
CUR_GEN_PATH := "";
CUR_GEN_STREAM := fail;
WORKER_START := Runtime();
# Wall-clock baseline for the hard checkpoint-restart trigger.  Runtime() is CPU
# time, which stalls when a bloated worker thrashes on page faults -- so a
# CPU-keyed 2h restart can never fire on the exact heavy jobs it must bound.
# NanosecondsSinceEpoch() is monotonic wall time, immune to iowait starvation.
WORKER_START_WALL := NanosecondsSinceEpoch();

RESUME_GROUP_IDX := 1;
RESUME_SUPER_BUILD_NEXT_HI := 0;   # 0 = no mid-build resume
RESUME_SUPER_JOB_IDX := 1;          # 1 = no between-job resume (fresh group)
RESUME_SUPER_PAIR_I := 1;           # 1 = no mid-pair resume
RESUME_SUPER_PAIR_J := 1;
RESUME_SUPER_TOTAL_ORB := 0;
RESUME_SUPER_TOTAL_FIX := 0;
RESUME_SUPER_TOTAL_CS := 0;
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
            if IsBound(RESUME_SUPER.total_cs_sum) then   # absent in pre-fix state files
                RESUME_SUPER_TOTAL_CS := RESUME_SUPER.total_cs_sum;
            fi;
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
    qstate := NewQTypeState();
    # LEFT-order bound (see GAP_DRIVER): |Q| must divide some |H_L|, else Q can't
    # be a common Goursat quotient.  Prunes the RIGHT 2-group's order-1024
    # quotients (and the lethal pairwise IsomorphismGroups in QTypeIsNew) when the
    # shared LEFT can't reach that order.
    LEFT_ORDERS := Set(List(SUBGROUPS_LEFT_RAW, Size));
    if USE_LEFT_REALIZABLE = 1 then
        LEFT_REALIZABLE := LeftRealizableQTypesIfCheap(SUBGROUPS_LEFT_RAW);
    else
        LEFT_REALIZABLE := fail;
    fi;
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
                    if not ForAny(LEFT_ORDERS, o -> o mod (Size(T_for_qg)/Size(K)) = 0) then continue; fi;
                    Q := T_for_qg/K;
                    if LEFT_REALIZABLE <> fail and not QTypeInRepList(LEFT_REALIZABLE, Q) then continue; fi;
                    if QTypeIsNew(qstate, Q) then
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
                # LEFT-order bound (2026-05-31): see BATCH_DRIVER note.
                if not ForAny(LEFT_ORDERS, o -> o mod Size(Q) = 0) then continue; fi;
                if LEFT_REALIZABLE <> fail and not QTypeInRepList(LEFT_REALIZABLE, Q) then continue; fi;
                if QTypeIsNew(qstate, Q) then
                    Add(RIGHT_Q_GROUPS, Q);
                fi;
            od;
        fi;
    od;

    if Length(RIGHT_Q_GROUPS) = 0
       and ForAny(GROUP.jobs, j -> j.right_tg_d > 0 or j.subs_right <> "") then
        # COPRIME short-circuit (2026-05-31): RIGHT processed, no Q-type survived
        # the LEFT-order filter -> no nontrivial common quotient -> trivial-Q
        # (direct-product) pairings only.  Skips the ComputeOrLoadLeftQGroups hang
        # on coprime LEFT/RIGHT (e.g. [2,1]_[9,17]_[9,17]).  See GAP_DRIVER note.
        LEFT_Q_GROUPS := [];
        Print("  [t+", Runtime() - group_t0, "ms] COPRIME (no common Q): ",
              "LEFT_Q_GROUPS := [] (trivial-Q pairing only)\n");
    elif Length(RIGHT_Q_GROUPS) = 0 then
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
        # LEFT-realizability Q-prune (see QPRUNE_MAXSUBS in _SHARED_HELPERS): keep
        # only the candidate quotient types some LEFT subgroup actually surjects
        # onto (exact, via GQuotients).  Count-neutral; gate is a small-LEFT perf knob.
        if LEFT_REALIZABLE <> fail then
            # RIGHT_Q_GROUPS was already filtered to LEFT-realizable types during
            # discovery, so it IS the prune result (count-identical to GQuotients).
            LEFT_Q_GROUPS := RIGHT_Q_GROUPS;
        elif QPRUNE_MAXSUBS > 0 and Length(SUBGROUPS_LEFT_RAW) <= QPRUNE_MAXSUBS
       and not ForAll(SUBGROUPS_LEFT_RAW, IsSolvableGroup) then
            LEFT_Q_GROUPS := Filtered(RIGHT_Q_GROUPS, Q ->
                ForAny(SUBGROUPS_LEFT_RAW, HL -> Length(GQuotients(HL, Q)) > 0));
        else
            LEFT_Q_GROUPS := RIGHT_Q_GROUPS;
        fi;
        Print("  [t+", Runtime() - group_t0, "ms] RIGHT-bounded Q-groups: ",
              Length(LEFT_Q_GROUPS), " types (from ", Length(RIGHT_Q_GROUPS),
              " RIGHT, LEFT-pruned), max |Q|=",
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
        H_CACHE := ReadHCacheAuto(CACHE_LEFT_PATH);
        Print("  [t+", Runtime() - group_t0, "ms] H_CACHE read complete: ",
              Length(H_CACHE), " entries\n");
    fi;
    if H_CACHE <> fail and not IS_BUILD_RESUME then
        for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
        extend_needed := false;
        for hi in [1..Length(H_CACHE)] do
            missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, _UnsafeRepsOf(H_CACHE[hi]), LEFT_Q_GROUPS);
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
                missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, _UnsafeRepsOf(H_CACHE[hi]), LEFT_Q_GROUPS);
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
                   and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CHECKPOINT_INTERVAL_MS
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
        if STREAM_HCACHE_BUILD = 1 and FRAMED_CACHE = 1 and CACHE_LEFT_PATH <> ""
           and Length(SUBGROUPS_LEFT_RAW) > 0 then
            # --- Streaming build (PRED_STREAM_HCACHE_BUILD=1).  See
            # BuildHCacheStreaming in _SHARED_HELPERS and the BATCH driver's
            # branch for the rationale; SUPER LEFTs are small by routing, so
            # the published cache is simply full-loaded back (the windowed
            # pair loop stays BATCH-only).
            if H_CACHE <> fail and Length(H_CACHE) = Length(SUBGROUPS_LEFT_RAW) then
                Print("  [t+", Runtime() - group_t0, "ms] STREAM-BUILD: ",
                      "canonical cache already complete (", Length(H_CACHE),
                      " entries); skipping build\n");
                for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
            else
                H_CACHE := fail;
                Print("  [t+", Runtime() - group_t0, "ms] computing H_CACHE for ",
                      Length(SUBGROUPS_LEFT_RAW), " subgroups (in W_ML, streaming)\n");
                BuildHCacheStreaming(SUBGROUPS_LEFT_RAW, W_ML, LEFT_Q_GROUPS,
                    CACHE_LEFT_PATH, "SUPER-LEFT",
                    function()
                        return STATE_FILE <> "" and CHECKPOINT_INTERVAL_MS > 0
                           and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL,
                                      1000000) >= CHECKPOINT_INTERVAL_MS;
                    end,
                    function(hi_done)
                        local tmp;
                        tmp := Concatenation(STATE_FILE, ".tmp");
                        PrintTo(tmp, "RESUME_SUPER := rec( next_group_idx := ",
                                group_idx, ", build_next_hi := ", hi_done + 1,
                                " );\n");
                        Exec(Concatenation("mv -f -- '", tmp, "' '",
                                           STATE_FILE, "'"));
                        Print("CHECKPOINT_PAUSE_SUPER_BUILD group=", group_idx,
                              " next_hi=", hi_done + 1, "/",
                              Length(SUBGROUPS_LEFT_RAW),
                              " elapsed_ms=", Runtime() - WORKER_START,
                              " (streaming)\n");
                        LogTo();
                        QuitGap();
                    end);
                H_CACHE := ReadHCacheAuto(CACHE_LEFT_PATH);
                for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
            fi;
        else
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
               and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CHECKPOINT_INTERVAL_MS
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
        fi;   # end: streaming vs legacy build
        # Build done — clear the build-resume flag so subsequent groups
        # (or end-of-group) start cleanly.  Do NOT remove state.g here:
        # end-of-group checkpoint will rewrite it if needed.
        if IS_BUILD_RESUME then
            RESUME_SUPER_BUILD_NEXT_HI := 0;
        fi;
    fi;
    EnsureHCacheComplete(H_CACHE, SUBGROUPS_LEFT_RAW, W_ML, LEFT_Q_GROUPS, CACHE_LEFT_PATH, "SUPER-LEFT");
    H_CACHE_L := H_CACHE;
    N_LEFT := Length(H_CACHE_L);
    if LAZY_LEFT_RECON = 1 then
        # Lazy LEFT reconstruction (PRED_LAZY_LEFT_RECON=1): skip the eager
        # per-group H1DATA_LIST build.  Each H1data is reconstructed per-i inside
        # the pair loop and discarded, bounding the reconstructed footprint to
        # O(1) instead of O(N_LEFT) materialized group objects held for the
        # lifetime of this group's jobs -- critical for heavy super-batch LEFTs
        # run many workers wide.  Trades J-fold ReconstructHData (once per entry
        # per job sharing this LEFT) for a flat memory profile.  Mirrors
        # _HEADER_BATCH; H_CACHE_L is retained for the per-i reconstruction.
        H1DATA_LIST := fail;
        Print("  [t+", Runtime() - group_t0,
              "ms] LAZY_LEFT_RECON=1: deferring ReconstructHData for ",
              N_LEFT, " LEFT entries\n");
    else
        Print("  [t+", Runtime() - group_t0, "ms] starting ReconstructHData on ",
              N_LEFT, " entries...\n");
        last_hb := Runtime();
        H1DATA_LIST := [];
        for hi in [1..N_LEFT] do
            Add(H1DATA_LIST, ReconstructHData(H_CACHE_L[hi], S_ML));
            if Runtime() - last_hb >= 60000 then
                Print("    [t+", Runtime() - group_t0, "ms] ReconstructHData ",
                      hi, "/", N_LEFT, "\n");
                last_hb := Runtime();
            fi;
        od;
        Print("  [t+", Runtime() - group_t0, "ms] ReconstructHData done\n");
    fi;

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
                H_CACHE := ReadHCacheAuto(JOB.cache_right);
                for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
                # RIGHT-side completeness check (2026-06-09): the cache file is
                # LEFT/RIGHT-shared and LEFT builds soft-save PARTIAL caches to
                # it; a partial loaded here silently shortens the pair loop
                # (N_RIGHT short -> SILENT UNDERCOUNT).  Cheap textual count.
                n_subs_right_chk := CountSubsGroupLines(JOB.subs_right);
                if n_subs_right_chk <> fail and Length(H_CACHE) <> n_subs_right_chk then
                    Read(JOB.subs_right);
                    SUBGROUPS_RIGHT_RAW := SUBGROUPS;
                    EnsureHCacheComplete(H_CACHE, SUBGROUPS_RIGHT_RAW, S_MR,
                                         LEFT_Q_GROUPS, JOB.cache_right, "SUPER-RIGHT");
                fi;
                extend_needed := false;
                for hi in [1..Length(H_CACHE)] do
                    missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, _UnsafeRepsOf(H_CACHE[hi]), LEFT_Q_GROUPS);
                    if missing = fail or Length(missing) > 0 then
                        extend_needed := true;
                    fi;
                od;
                if extend_needed then
                    Print("    [t+", Runtime() - job_t0,
                          "ms] extending RIGHT H_CACHE for new Q-types...\n");
                    for hi in [1..Length(H_CACHE)] do
                        missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, _UnsafeRepsOf(H_CACHE[hi]), LEFT_Q_GROUPS);
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
            i_resume_start := RESUME_SUPER_PAIR_I;
            j_resume_start := RESUME_SUPER_PAIR_J;
            resume_total_orb := RESUME_SUPER_TOTAL_ORB;
            resume_total_fix := RESUME_SUPER_TOTAL_FIX;
            resume_total_cs := RESUME_SUPER_TOTAL_CS;
        else
            i_resume_start := 1;
            j_resume_start := 1;
            resume_total_orb := 0;
            resume_total_fix := 0;
            resume_total_cs := 0;
        fi;

        # Open this (group, job)'s generator stream (streamed to disk; no
        # fp_lines buffer).  See _LOOP_BATCH for rationale.  Truncate on a fresh
        # job; append when resuming mid-job (Python truncated CUR_GEN_PATH to
        # right after the last "# cp" marker).
        CUR_GEN_PATH := JOB.gens_path;
        if i_resume_start = 1 and j_resume_start = 1 then
            CUR_GEN_STREAM := OutputTextFile(CUR_GEN_PATH, false);
        else
            CUR_GEN_STREAM := OutputTextFile(CUR_GEN_PATH, true);
        fi;
        SetPrintFormattingStatus(CUR_GEN_STREAM, false);

"""
_LOOP_SUPER = r"""
        TOTAL_ORB := resume_total_orb;
        TOTAL_FIX := resume_total_fix;
        TOTAL_CS_SUM := resume_total_cs;
        last_hb_ms := Runtime() - job_t0;
        n_pairs_done := 0;
        n_pairs_total := N_LEFT * Length(H2DATA);
        Print("    [t+", Runtime() - job_t0, "ms] starting H1xH2 loop: ",
              N_LEFT, " x ", Length(H2DATA),
              " = ", n_pairs_total, " pairs\n");
        # HOTFIX 2026-06-12: reset checkpoint timer to EXCLUDE cache/setup load
        # (RIGHT H-cache rebuild can take 60-107 min) so the interval/floor
        # measure only useful pair-loop work, not the one-time setup.
        WORKER_START := Runtime();
        WORKER_START_WALL := NanosecondsSinceEpoch();
        # Optimization (4) 2026-04-28: precompute shifted RIGHT once per j.
        if BURNSIDE_M2 = 0 then
            for H2data_j in H2DATA do EnsureShiftedHData(H2data_j); od;
            H2_SHIFTED := List(H2DATA, hd -> hd.shifted_H);
        fi;
        for i in [i_resume_start..N_LEFT] do
            # LAZY_LEFT_RECON=1: reconstruct this LEFT entry on demand (per-i,
            # per-job), discarded when overwritten next i.  O(1) vs O(N_LEFT)
            # reconstructed footprint; see the build block above.  Mirrors
            # _LOOP_BATCH.
            if LAZY_LEFT_RECON = 1 then
                H1data_j := ReconstructHData(H_CACHE_L[i], S_ML);
            else
                H1data_j := H1DATA_LIST[i];
            fi;
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
                TOTAL_CS_SUM := TOTAL_CS_SUM + res_pair.class_sum;
                n_pairs_done := n_pairs_done + 1;
                N_PAIRS_EPOCH := N_PAIRS_EPOCH + 1;
                # Heartbeat every 30s of wall time inside this job.
                if (Runtime() - job_t0) - last_hb_ms >= 30000 then
                    Print("    [t+", Runtime() - job_t0, "ms] pair ",
                          n_pairs_done, "/", n_pairs_total,
                          " (i=", i, "/", N_LEFT,
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
                   and (j < Length(H2DATA) or i < N_LEFT) then
                    next_i := i;
                    next_j := j + 1;
                    if next_j > Length(H2DATA) then
                        next_i := i + 1;
                        next_j := 1;
                    fi;
                    # Self-describing checkpoint marker (next pair coords +
                    # totals) into this job's gens stream; flush + reopen so it
                    # is durable; minimal state.g (group + job).  See _LOOP_BATCH.
                    WriteAll(CUR_GEN_STREAM, Concatenation(
                        "# cp ni=", String(next_i), " nj=", String(next_j),
                        " orb=", String(TOTAL_ORB), " fix=", String(TOTAL_FIX),
                        " cs=", String(TOTAL_CS_SUM), "\n"));
                    CloseStream(CUR_GEN_STREAM);
                    CUR_GEN_STREAM := OutputTextFile(CUR_GEN_PATH, true);
                    SetPrintFormattingStatus(CUR_GEN_STREAM, false);
                    tmp := Concatenation(STATE_FILE, ".tmp");
                    PrintTo(tmp, "RESUME_SUPER := rec( next_group_idx := ",
                        group_idx, ", next_job_idx := ", job_idx, " );\n");
                    Exec(Concatenation("mv -f -- '", tmp, "' '",
                                       STATE_FILE, "'"));
                    LAST_STATE_SAVE_MS := Runtime();
                    Print("[soft_checkpoint] SUPER_PAIR group=", group_idx,
                          " job=", job_idx,
                          " pair_i=", next_i, "/", N_LEFT,
                          " pair_j=", next_j,
                          " orb=", TOTAL_ORB,
                          " elapsed_ms=", Runtime() - WORKER_START, "\n");
                fi;
                # Per-pair checkpoint: bound heap to ~30 min of pair work even
                # within a single long JOB (closes the n_left small / pair-spike
                # pathology in SUPER too).
                if STATE_FILE <> ""
                   and ( (MAX_PAIRS_PER_CKPT > 0 and N_PAIRS_EPOCH >= MAX_PAIRS_PER_CKPT)
                         or (CHECKPOINT_INTERVAL_MS > 0 and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CHECKPOINT_INTERVAL_MS)
                         or (CKPT_TIME_FLOOR_MS > 0 and CKPT_PAIR_GRAN > 0 and N_PAIRS_EPOCH > 0
                             and N_PAIRS_EPOCH mod CKPT_PAIR_GRAN = 0
                             and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CKPT_TIME_FLOOR_MS)
                         or (MAX_WORKSPACE_KB > 0 and CKPT_PAIR_GRAN > 0 and N_PAIRS_EPOCH > 0
                             and N_PAIRS_EPOCH mod CKPT_PAIR_GRAN = 0
                             and CurrentWorkspaceKB() >= MAX_WORKSPACE_KB) )
                   and (j < Length(H2DATA) or i < N_LEFT) then
                    next_i := i;
                    next_j := j + 1;
                    if next_j > Length(H2DATA) then
                        next_i := i + 1;
                        next_j := 1;
                    fi;
                    # Self-describing marker + minimal state.g, then flush +
                    # close before QuitGap (see soft-save above / _LOOP_BATCH).
                    WriteAll(CUR_GEN_STREAM, Concatenation(
                        "# cp ni=", String(next_i), " nj=", String(next_j),
                        " orb=", String(TOTAL_ORB), " fix=", String(TOTAL_FIX),
                        " cs=", String(TOTAL_CS_SUM), "\n"));
                    CloseStream(CUR_GEN_STREAM);
                    tmp := Concatenation(STATE_FILE, ".tmp");
                    PrintTo(tmp, "RESUME_SUPER := rec( next_group_idx := ",
                        group_idx, ", next_job_idx := ", job_idx, " );\n");
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
            # Opt 10 (2026-05-23): see BATCH_DRIVER for rationale.  Includes
            # v4_frat_kdata clear to avoid cross-job stale cache reference
            # to H1data.linear_A_data.
            for orb in H1data_j.orbits do
                orb.AutQ := fail;
                orb.A_gens := [];
                orb.raw_A_gens := [];
                orb.iso_to_can := fail;
                orb.full_aut := fail;
                orb.hom := fail;
                orb.Q := fail;
                orb.shifted_hom := fail;
                orb.shifted_K_gens_noid := fail;
                orb.c2_rep := fail;
                orb.shifted_c2_rep := fail;
                orb.dc_cache := fail;
                if IsBound(orb.v4_A1_matrices) then Unbind(orb.v4_A1_matrices); fi;
                if IsBound(orb.v4_A2_matrices) then Unbind(orb.v4_A2_matrices); fi;
                if IsBound(orb.v4_gen_exps) then Unbind(orb.v4_gen_exps); fi;
                if IsBound(orb.v4_pcgs_can) then Unbind(orb.v4_pcgs_can); fi;
                if IsBound(orb.v4_full_aut_frat) then Unbind(orb.v4_full_aut_frat); fi;
                if IsBound(orb.v4_gen_exps_frat) then Unbind(orb.v4_gen_exps_frat); fi;
                if IsBound(orb.v4_frat_kdata) then Unbind(orb.v4_frat_kdata); fi;
                if IsBound(orb.v4_preimg_table) then Unbind(orb.v4_preimg_table); fi;
                if IsBound(orb.v4_preimg_table_frat) then Unbind(orb.v4_preimg_table_frat); fi;
                if IsBound(orb.v4_shifted_kernel_gens_noid) then Unbind(orb.v4_shifted_kernel_gens_noid); fi;
                if IsBound(orb.emit_h_gens) then Unbind(orb.emit_h_gens); fi;
                if IsBound(orb.emit_qcan_imgs) then Unbind(orb.emit_qcan_imgs); fi;
                if IsBound(orb.emit_can_elts) then Unbind(orb.emit_can_elts); fi;
                if IsBound(orb.emit_can_pre) then Unbind(orb.emit_can_pre); fi;
                if IsBound(orb.emit_ker_noid) then Unbind(orb.emit_ker_noid); fi;
            od;
            H1data_j.shifted_H := fail;
            H1data_j.shifted_H_gens_noid := fail;
        od;

        if BURNSIDE_M2 = 1 then PREDICTED := (TOTAL_ORB + TOTAL_FIX) / 2;
        else PREDICTED := TOTAL_ORB; fi;
        elapsed_ms := Runtime() - job_t0;

        # Atomic per-combo write (see notes in BATCH_DRIVER above).  Flush the
        # streamed gens, write the header (counts known now), then append the
        # gen lines with "# cp" markers stripped (byte-identical to the old
        # fp_lines join).  grep streams the body at O(1) memory; "|| true"
        # absorbs grep's exit-1 when a 0-class combo leaves no "[" lines.
        TMP_OUT := Concatenation(OUTPUT_PATH, ".tmp");
        CloseStream(CUR_GEN_STREAM);
        OUT_STREAM := OutputTextFile(TMP_OUT, false);
        SetPrintFormattingStatus(OUT_STREAM, false);
        WriteAll(OUT_STREAM, Concatenation(COMBO_HEADER, "\n"));
        WriteAll(OUT_STREAM, Concatenation("# candidates: ", String(PREDICTED), "\n"));
        WriteAll(OUT_STREAM, Concatenation("# deduped: ", String(PREDICTED), "\n"));
        WriteAll(OUT_STREAM, Concatenation("# elapsed_ms: ", String(elapsed_ms), "\n"));
        WriteAll(OUT_STREAM, Concatenation("# class_sum: ", String(TOTAL_CS_SUM), "\n"));
        CloseStream(OUT_STREAM);
        Exec(Concatenation("grep -v '^#' '", CUR_GEN_PATH, "' >> '", TMP_OUT, "' || true"));
        Exec(Concatenation("mv -f -- '", TMP_OUT, "' '", OUTPUT_PATH, "'"));
        RemoveFile(CUR_GEN_PATH);

        Print("RESULT group=", group_idx, " job=", job_idx,
              " predicted=", PREDICTED, " orbits=", TOTAL_ORB,
              " swap_fixed=", TOTAL_FIX, " class_sum=", TOTAL_CS_SUM,
              " elapsed_ms=", elapsed_ms,
              " v4fast_emits=", BENCH_V4FAST.n_emits,
      " v4fast_nonsat=", BENCH_V4FAST.n_emits_nonsat,
      " v4fast_frat=", BENCH_V4FAST.n_emits_frat, "\n");

        # Between-JOB checkpoint: bound heap to one JOB's worth.  Pair-loop
        # checkpoint can't fire when n_left = 1 or 2, so this is the only
        # in-group heap reset for those cases.
        if STATE_FILE <> ""
           and ( (MAX_PAIRS_PER_CKPT > 0 and N_PAIRS_EPOCH >= MAX_PAIRS_PER_CKPT)
                 or (CHECKPOINT_INTERVAL_MS > 0 and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CHECKPOINT_INTERVAL_MS)
                 or (CKPT_TIME_FLOOR_MS > 0 and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CKPT_TIME_FLOOR_MS) )
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
    if STATE_FILE <> ""
       and ( (MAX_PAIRS_PER_CKPT > 0 and N_PAIRS_EPOCH >= MAX_PAIRS_PER_CKPT)
             or (CHECKPOINT_INTERVAL_MS > 0 and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CHECKPOINT_INTERVAL_MS)
             or (CKPT_TIME_FLOOR_MS > 0 and QuoInt(NanosecondsSinceEpoch() - WORKER_START_WALL, 1000000) >= CKPT_TIME_FLOOR_MS) )
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

GAP_DRIVER = _PREAMBLE_GAP + _SHARED_HELPERS + _TAIL_GAP


# Self-describing checkpoint marker the BATCH/SUPER drivers append to a job's
# gens file: "# cp ni=.. nj=.. orb=.. fix=.. cs=..\n" (next pair coords +
# cumulative totals).  Requires the trailing newline, so a half-written marker
# from a crash is ignored.
_CP_MARKER_RE = re.compile(
    rb"# cp ni=(\d+) nj=(\d+) orb=(\d+) fix=(\d+) cs=(\d+)\n")


def _gens_tail_with(gens_path, has_needle, init_window=1 << 22):
    """Read a growing tail window of `gens_path` from EOF (x4 each step) until
    `has_needle(buf)` is True or the whole file has been read.  Returns
    (buf, base) where buf == file bytes from offset `base` to EOF.

    The checkpoint marker a resume needs is the LAST one, which sits near the end
    of the gens file (it is followed only by the generators of pairs computed
    since that checkpoint).  Reading just the tail bounds memory to
    O(distance-from-EOF-to-last-marker) instead of O(filesize): a mega-combo's
    multi-GB gens file is no longer slurped whole.  This was a hard OOM -- a
    6.6 GB job1_gens.g (the n=22 [4,3]^4 D8^4 monster, 32.8M classes) killed
    _prepare_gens_resume with MemoryError on `read_bytes()`, wedging the combo so
    it could never resume.  Correctness: when the window first grows to include
    the last marker, base <= marker_start, so the marker line is fully present;
    while the window is smaller, the buffer is pure post-checkpoint generators
    (no marker) and we expand.  Identical (marker, truncation) to a full read."""
    size = gens_path.stat().st_size
    if size == 0:
        return b"", 0
    window = min(size, init_window)
    with gens_path.open("rb") as f:
        while True:
            base = size - window
            f.seek(base)
            buf = f.read(window)
            if base == 0 or has_needle(buf):
                return buf, base
            window = min(size, window * 4)


# --- Streaming H-cache build (PRED_STREAM_HCACHE_BUILD) ---------------------
# DEFAULT ON since 2026-06-09 (gates 1-2 + BATCH e2e green; flipped together
# with the PRED_FRAMED_CACHE / PRED_LAZY_LEFT_RECON defaults per the
# HCACHE_STREAMING_PROPOSAL.md rollout).  Opt out of any of the three with
# =0.  The GAP drivers build fresh LEFT caches by appending entries to a
# process-private <cache>.building.<token> file and publish atomically on
# completion, so the canonical cache path only ever carries COMPLETE caches
# and build memory is O(1) in the entry count.  See BuildHCacheStreaming in
# _SHARED_HELPERS.
#
# Bump _HCACHE_BUILD_VER whenever ComputeHCacheEntry / the Stage A-D kernel
# enumeration changes what an entry CONTAINS (the
# hcache_reuse_across_code_changes lesson: never mix entries computed by
# different enumeration code in one cache file).  Orphaned .building files
# whose ver does not match are never adopted.
_HCACHE_BUILD_VER = "1"


def _stream_hcache_enabled():
    return (os.environ.get("PRED_STREAM_HCACHE_BUILD") != "0"
            and os.environ.get("PRED_FRAMED_CACHE") != "0")


def _claim_stale_building(cache_path, token, expected_n):
    """Adopt the most complete STALE orphaned .building file for cache_path.

    A worker killed mid-(streaming)-build leaves <cache>.building.<tok> + its
    .idx behind; the dead worker's UUID work_root (and state.g) are never
    reused, so only this claim can resume that partial.  Claim = rename both
    files to OUR token, so the GAP driver adopts them as its own.

    Liveness gate: a live builder touches its files at least every ~60 s
    (flush cadence), so anything untouched for PRED_BUILDING_STALE_S (default
    30 min) is presumed dead.  A single ComputeHCacheEntry can occasionally
    stall longer; if a LIVE builder is ever falsely claimed, it detects the
    rename at its next flush (_StreamBuildingHeaderOk) and aborts loudly
    BEFORE publishing anything -- the claimer owns the entries, no corruption
    is possible, only that builder's duplicate work is lost.

    Ver + expected count come from the .idx header; a mismatch (enumeration
    code changed, or the source subgroup list was regenerated) makes the
    orphan unadoptable -- skip it (GAP would discard it anyway)."""
    stale_s = int(os.environ.get("PRED_BUILDING_STALE_S", "1800"))
    mine = cache_path.parent / f"{cache_path.name}.building.{token}"
    if mine.exists():
        return
    best = None
    now = time.time()
    for cand in cache_path.parent.glob(cache_path.name + ".building.*"):
        if cand.name.endswith(".idx") or cand == mine:
            continue
        idx = cand.parent / (cand.name + ".idx")
        if not idx.exists():
            continue
        try:
            mtime = max(cand.stat().st_mtime, idx.stat().st_mtime)
            if now - mtime < stale_s:
                continue
            with idx.open("r", encoding="ascii", errors="replace") as f:
                hdr = f.readline()
            m = re.match(r"# hcache_building: ver=(\S+) count=(\d+)", hdr)
            if (not m or m.group(1) != _HCACHE_BUILD_VER
                    or int(m.group(2)) != expected_n):
                continue
            size = cand.stat().st_size
        except OSError:
            continue
        if best is None or size > best[1]:
            best = (cand, size)
    if best is None:
        return
    cand = best[0]
    idx = cand.parent / (cand.name + ".idx")
    try:
        # idx first: a crash between the renames leaves an idx-less foreign
        # .g (never adopted, harmless garbage) rather than a ver-less
        # claimed pair.
        idx.rename(cache_path.parent / f"{mine.name}.idx")
        cand.rename(mine)
        print(f"  [stream-build] claimed stale .building "
              f"({best[1]} bytes) for {cache_path.name}",
              file=sys.stderr, flush=True)
    except OSError:
        pass


def _prepare_gens_resume(state_g, work_root, n_jobs, state_var="RESUME_STATE"):
    """Reconcile state.g with the resuming job's gens file before relaunching GAP.

    The BATCH/SUPER drivers stream generators to ``job<K>_gens.g`` and, at each
    checkpoint, append a self-describing "# cp" marker then drop a minimal
    ``state.g`` (job_idx only).  The gens file is the single source of truth: we
    read job_idx, find the last complete marker in that job's gens file, truncate
    the file to right after it (discarding any half-written tail from a crash),
    and rewrite state.g with the pair coords + totals from that marker so GAP
    resumes exactly where the on-disk generators end.  If the gens file has no
    marker yet (job not started, or crashed before its first checkpoint), restart
    that job from scratch (truncate gens to empty; coords/totals default to a
    fresh start in the GAP resume-read)."""
    if not state_g.exists():
        return
    txt = state_g.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"job_idx\s*:=\s*(\d+)", txt)
    if not m:
        return
    job_idx = int(m.group(1))
    if not (1 <= job_idx <= n_jobs):
        return
    gens = work_root / f"job{job_idx}_gens.g"
    if not gens.exists():
        state_g.write_text(f"{state_var} := rec( job_idx := {job_idx} );\n",
                           encoding="utf-8")
        return
    buf, toff = _gens_tail_with(gens, lambda b: _CP_MARKER_RE.search(b) is not None)
    matches = list(_CP_MARKER_RE.finditer(buf))
    if not matches:
        with gens.open("r+b") as f:
            f.truncate(0)
        state_g.write_text(f"{state_var} := rec( job_idx := {job_idx} );\n",
                           encoding="utf-8")
        return
    last = matches[-1]
    with gens.open("r+b") as f:
        f.truncate(toff + last.end())
    ni, nj, orb, fix, cs = (int(last.group(k)) for k in range(1, 6))
    state_g.write_text(
        f"{state_var} := rec( job_idx := {job_idx}, pair_i := {ni}, "
        f"pair_j := {nj}, total_orb := {orb}, total_fix := {fix}, "
        f"total_cs_sum := {cs} );\n",
        encoding="utf-8")


def _prepare_super_gens_resume(state_g, work_root):
    """SUPER-driver analogue of _prepare_gens_resume.

    The SUPER state.g is a RESUME_SUPER record with next_group_idx, plus
    next_job_idx for a mid-jobs / mid-pair pause (or build_next_hi for a
    LEFT-cache-build pause).  Only the mid-pair case needs gens reconciliation:
    locate that (group, job)'s gens file, truncate to its last "# cp" marker, and
    rewrite RESUME_SUPER with the pair coords + totals from the marker.  Build
    and end-of-group states are left untouched (no streamed gens involved)."""
    if not state_g.exists():
        return
    txt = state_g.read_text(encoding="utf-8", errors="ignore")
    if "build_next_hi" in txt:
        return  # LEFT-cache-build resume: no gens to reconcile.
    mg = re.search(r"next_group_idx\s*:=\s*(\d+)", txt)
    mj = re.search(r"next_job_idx\s*:=\s*(\d+)", txt)
    if not mg or not mj:
        return  # end-of-group (group only): fresh group, no gens to reconcile.
    g, j = int(mg.group(1)), int(mj.group(1))
    gens = work_root / f"g{g}_job{j}_gens.g"
    base = f"RESUME_SUPER := rec( next_group_idx := {g}, next_job_idx := {j}"
    if not gens.exists():
        state_g.write_text(base + " );\n", encoding="utf-8")
        return
    buf, toff = _gens_tail_with(gens, lambda b: _CP_MARKER_RE.search(b) is not None)
    matches = list(_CP_MARKER_RE.finditer(buf))
    if not matches:
        with gens.open("r+b") as f:
            f.truncate(0)
        state_g.write_text(base + " );\n", encoding="utf-8")
        return
    last = matches[-1]
    with gens.open("r+b") as f:
        f.truncate(toff + last.end())
    ni, nj, orb, fix, cs = (int(last.group(k)) for k in range(1, 6))
    state_g.write_text(
        base + f", pair_i := {ni}, pair_j := {nj}, total_orb := {orb}, "
        f"total_fix := {fix}, total_cs_sum := {cs} );\n",
        encoding="utf-8")


# ---------------------------------------------------------------------------
# Batched GAP driver: load LEFT once, iterate jobs all sharing that LEFT.
# Each job has its own RIGHT side (TG or source file) and writes its own
# legacy-format output file (composed by GAP via SizeScreen wide enough to
# avoid line wraps).
# ---------------------------------------------------------------------------
BATCH_DRIVER = _PREAMBLE_BATCH + _SHARED_HELPERS + _HEADER_BATCH + _PAIR_ENGINE_BATCHSUPER + _LOOP_BATCH


# ---------------------------------------------------------------------------
# Super-batch driver: process multiple LEFT-source GROUPS in ONE GAP session,
# amortizing the GAP startup + lifting_algorithm.g load across all of them.
# Useful when many groups have only 1-2 jobs each (e.g., n=14 had 1248 groups
# averaging ~1.2 jobs each).
# ---------------------------------------------------------------------------
SUPER_BATCH_DRIVER = _PREAMBLE_SUPER + _SHARED_HELPERS + _HEADER_SUPER + _PAIR_ENGINE_BATCHSUPER + _LOOP_SUPER


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

    # Streaming-build token (one per invocation; .building paths are
    # per-cache, so groups cannot collide).  See _claim_stale_building.
    build_token = uuid.uuid4().hex[:12]

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
        drop_cache_if_corrupt(cache_l)
        subs_l_list = parse_combo_file(sl)
        if _stream_hcache_enabled():
            _claim_stale_building(cache_l, build_token, len(subs_l_list))
        subs_l_g = work_root / f"subs_left_g{g_i}.g"
        subs_l_g.write_text(_subs_g_text(subs_l_list), encoding="utf-8")

        job_records = []
        for j_i, job in enumerate(jobs, start=1):
            inputs = resolve_inputs(job["combo"], job["mode"])
            rec = {
                "m_right": inputs["m_right"],
                "burnside_m2": 1 if inputs["burnside_m2"] else 0,
                "output_path": to_gap(Path(job["output_path"])),
                # Per-(group,job) streamed gens file (GAP indices are 1-based:
                # group_idx == g_i+1, job_idx == j_i).
                "gens_path": to_gap(work_root / f"g{g_i + 1}_job{j_i}_gens.g"),
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
                drop_cache_if_corrupt(cr)
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
        .replace("__USE_STAGE_D__",
                 "0" if os.environ.get("PRED_STAGE_D") == "0" else "1")
        .replace("__LAZY_LEFT_RECON__",
                 "0" if os.environ.get("PRED_LAZY_LEFT_RECON") == "0" else "1")
        .replace("__MAX_PAIRS_PER_CKPT__",
                 str(int(os.environ.get("PRED_MAX_PAIRS_PER_CKPT", "100000"))))
        .replace("__CKPT_TIME_FLOOR_MS__",
                 str(int(os.environ.get("PRED_CKPT_TIME_FLOOR_MS", "1800000"))))
        .replace("__CKPT_PAIR_GRAN__",
                 str(int(os.environ.get("PRED_CKPT_PAIR_GRAN", "5000"))))
        .replace("__MAX_WORKSPACE_KB__",
                 str(int(round(float(os.environ.get("PRED_MAX_WORKSPACE_GB", "30")) * 1048576))))
        .replace("__FRAMED_CACHE__",
                 "0" if os.environ.get("PRED_FRAMED_CACHE") == "0" else "1")
        .replace("__STREAM_HCACHE_BUILD__", "1" if _stream_hcache_enabled() else "0")
        .replace("__BUILD_TOKEN__", build_token)
        .replace("__HCACHE_BUILD_VER__", _HCACHE_BUILD_VER)
        .replace("__STREAM_WINDOW_MIN__",
                 str(int(os.environ.get("PRED_STREAM_WINDOW_MIN", "20000"))))
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
    # A state.g left from a prior killed run means "resume": reconcile it with
    # the per-(group,job) gens files before the first launch.
    if state_g.exists():
        _prepare_super_gens_resume(state_g, work_root)
    try:
        while True:
            epoch += 1
            _gap_run(cmd, env, timeout, diag_dir=work_root)
            if log.exists():
                with preserved_log.open("ab") as p, log.open("rb") as l:
                    p.write(l.read())
            if not state_g.exists():
                break
            # GAP checkpointed: reconcile state.g with the resuming (group,job)'s
            # gens file (truncate to last "# cp" marker, rebuild RESUME_SUPER)
            # before relaunch — keeps the gens file the crash-consistent source.
            _prepare_super_gens_resume(state_g, work_root)
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
        r"orbits=\s*(\d+)\s+swap_fixed=\s*(\d+)"
        r"(?:\s+class_sum=\s*(\d+))?\s+elapsed_ms=\s*(\d+)")
    # Map (group_idx, job_idx) -> result
    parsed = {}
    for m in result_re.finditer(log_text):
        g = int(m.group(1))
        j = int(m.group(2))
        parsed[(g, j)] = {
            "predicted": int(m.group(3)),
            "orbits": int(m.group(4)),
            "swap_fixed": int(m.group(5)),
            "class_sum": int(m.group(6)) if m.group(6) else None,
            "elapsed_s": int(m.group(7)) / 1000.0,
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
    drop_cache_if_corrupt(cache_l)

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
    subs_l_list = parse_combo_file(sl)
    subs_l_g = work_root / "subs_left.g"
    subs_l_g.write_text(_subs_g_text(subs_l_list), encoding="utf-8")
    # Streaming-build token: stable across this invocation's GAP epochs (the
    # .building resume path), unique across concurrent workers.  Claim any
    # stale orphan from a dead worker before the first GAP launch.
    build_token = uuid.uuid4().hex[:12]
    if _stream_hcache_enabled():
        _claim_stale_building(cache_l, build_token, len(subs_l_list))

    for idx, job in enumerate(jobs):
        inputs = resolve_inputs(job["combo"], job["mode"])
        out_path = Path(job["output_path"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "m_right": inputs["m_right"],
            "burnside_m2": 1 if inputs["burnside_m2"] else 0,
            "output_path": to_gap(out_path),
            # Per-job streamed-generator file (GAP's 1-based job_idx == idx+1).
            "gens_path": to_gap(work_root / f"job{idx + 1}_gens.g"),
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
            drop_cache_if_corrupt(cr)
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
        .replace("__USE_STAGE_D__",
                 "0" if os.environ.get("PRED_STAGE_D") == "0" else "1")
        .replace("__LAZY_LEFT_RECON__",
                 "0" if os.environ.get("PRED_LAZY_LEFT_RECON") == "0" else "1")
        .replace("__MAX_PAIRS_PER_CKPT__",
                 str(int(os.environ.get("PRED_MAX_PAIRS_PER_CKPT", "100000"))))
        .replace("__CKPT_TIME_FLOOR_MS__",
                 str(int(os.environ.get("PRED_CKPT_TIME_FLOOR_MS", "1800000"))))
        .replace("__CKPT_PAIR_GRAN__",
                 str(int(os.environ.get("PRED_CKPT_PAIR_GRAN", "5000"))))
        .replace("__MAX_WORKSPACE_KB__",
                 str(int(round(float(os.environ.get("PRED_MAX_WORKSPACE_GB", "30")) * 1048576))))
        .replace("__FRAMED_CACHE__",
                 "0" if os.environ.get("PRED_FRAMED_CACHE") == "0" else "1")
        .replace("__STREAM_HCACHE_BUILD__", "1" if _stream_hcache_enabled() else "0")
        .replace("__BUILD_TOKEN__", build_token)
        .replace("__HCACHE_BUILD_VER__", _HCACHE_BUILD_VER)
        .replace("__STREAM_WINDOW_MIN__",
                 str(int(os.environ.get("PRED_STREAM_WINDOW_MIN", "20000"))))
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
    # A state.g left from a prior killed run means "resume": reconcile it with
    # the per-job gens files before the first launch (see _prepare_gens_resume).
    if state_g.exists():
        _prepare_gens_resume(state_g, work_root, len(jobs))
    try:
        while True:
            epoch += 1
            _gap_run(cmd, env, timeout, diag_dir=work_root)
            if log.exists():
                with preserved_log.open("ab") as p, log.open("rb") as l:
                    p.write(l.read())
            if not state_g.exists():
                break
            # GAP checkpointed: reconcile state.g with the resuming job's gens
            # file (truncate to last "# cp" marker, rebuild RESUME_STATE) before
            # relaunch, so the gens file stays the crash-consistent source of truth.
            _prepare_gens_resume(state_g, work_root, len(jobs))
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
        r"RESULT idx=\s*(\d+)\s+predicted=\s*(\d+)\s+orbits=\s*(\d+)\s+swap_fixed=\s*(\d+)"
        r"(?:\s+class_sum=\s*(\d+))?\s+elapsed_ms=\s*(\d+)")
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
                "class_sum": int(m.group(5)) if m.group(5) else None,
                "elapsed_s": int(m.group(6)) / 1000.0,
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


def _write_legacy_format(output_path, combo, raw_gens_lines, deduped_count,
                         elapsed_ms, class_sum=None):
    """Write combo file with legacy header followed by generator lines.
    Joins GAP line-continuations so each generator is one physical line
    (matching legacy parallel_sn/.../<combo>.g format).
    If class_sum is provided, emits a `# class_sum: N` header (labelled-
    subgroup harvest, see HOLT_SPLIT_HARVEST.md)."""
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
        if class_sum is not None:
            f.write(f"# class_sum: {class_sum}\n")
        for line in joined_lines:
            f.write(line + "\n")
    return len(joined_lines)


def _predict_gap_driver(combo, mode="auto", emit_generators=False,
                        output_path=None, force=False, timeout=3600,
                        extend_only=False):
    """LEGACY single-combo GAP driver.  Retained ONLY for --extend-only
    (cache preflight; never enters the pair loop) and the PRED_COMBO_LEGACY=1
    escape hatch.  Its pair-loop crash-resume has a known window (state.g is
    durably updated every pair while gens+markers sit in a buffered stream,
    so a hard kill silently drops -- or, in the reverse window, duplicates --
    generator lines on resume).  predict() routes everything else through
    the BATCH driver, whose gens-file-as-source-of-truth resume is
    crash-consistent."""
    if isinstance(combo, str):
        combo = parse_combo_str(combo)
    target_n = sum(d for d, _ in combo)

    # Normalize --mode (auto / clean mode name / legacy alias) to a concrete
    # strategy.  `mode` is thereafter the fine-grained strategy and is emitted
    # as the result's "mode" field, so output records stay stable.
    mode = resolve_strategy(combo, mode)
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
    drop_cache_if_corrupt(cache_l)

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
        drop_cache_if_corrupt(cache_r)

    # Parse source files (raw generator lists) into proper SUBGROUPS := [...] form.
    def write_subs_g(out_path, subs_list):
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("SUBGROUPS := [\n")
            for i, s in enumerate(subs_list):
                sep = "," if i < len(subs_list) - 1 else ""
                f.write(f"  Group({s}){sep}\n")
            f.write("];\n")
    subs_l_g = work / "subs_left.g"
    subs_l_list = parse_combo_file(sl)
    write_subs_g(subs_l_g, subs_l_list)
    # Streaming-build token + stale-orphan claim (see _claim_stale_building).
    build_token = uuid.uuid4().hex[:12]
    if _stream_hcache_enabled():
        _claim_stale_building(cache_l, build_token, len(subs_l_list))
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
            buf, toff = _gens_tail_with(gen_path,
                                        lambda b: b.rfind(b"# checkpoint ") >= 0)
            last_marker = buf.rfind(b"# checkpoint ")
            if last_marker >= 0:
                # Find end of that line (the \n after the marker).
                end_of_marker_line = buf.find(b"\n", last_marker)
                if end_of_marker_line >= 0:
                    truncate_to = toff + end_of_marker_line + 1
                    if truncate_to < gen_path.stat().st_size:
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
    # BENCH_STARTUP=1: emit [PHASE t=...] timing prints at session-startup
    # checkpoints (gap_startup_done, after_prototype_loads, subs_left_loaded,
    # left_q_groups_computed, left_hcache_built, right_hcache_built).
    # Off by default; only affects single-combo predict() invocations.
    bench_startup = int(os.environ.get("BENCH_STARTUP", "0"))
    if H_TO_QS_MASTER_PATH.parent.exists():
        H_TO_QS_FRAGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    run_g = work / "run.g"
    run_g.write_text(
        GAP_DRIVER
        .replace("__LOG__", to_gap(log))
        .replace("__BENCH_STARTUP__", str(bench_startup))
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
        .replace("__FRAMED_CACHE__",
                 "0" if os.environ.get("PRED_FRAMED_CACHE") == "0" else "1")
        .replace("__STREAM_HCACHE_BUILD__", "1" if _stream_hcache_enabled() else "0")
        .replace("__BUILD_TOKEN__", build_token)
        .replace("__HCACHE_BUILD_VER__", _HCACHE_BUILD_VER)
        .replace("__STREAM_WINDOW_MIN__",
                 str(int(os.environ.get("PRED_STREAM_WINDOW_MIN", "20000"))))
        .replace("__STATE_FILE__", to_gap(state_g))
        .replace("__CHECKPOINT_INTERVAL_MS__", str(chkpt_ms))
        .replace("__STATE_SAVE_INTERVAL_MS__", str(state_save_ms))
        .replace("__EXTEND_ONLY__", "1" if extend_only else "0")
        .replace("__USE_LINEAR_ORBITS__",
                 "0" if os.environ.get("PRED_USE_LINEAR_ORBITS") == "0" else "1")
        .replace("__USE_STAGE_D__",
                 "0" if os.environ.get("PRED_STAGE_D") == "0" else "1")
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
    m = re.search(
        r"RESULT predicted=\s*(\d+)\s+orbits=\s*(\d+)\s+swap_fixed=\s*(\d+)"
        r"(?:\s+class_sum=\s*(\d+))?", log_text)
    if not m:
        return {"error": "no RESULT", "log_tail": log_text[-2000:], "elapsed_s": elapsed}
    out = {
        "combo": combo_filename(combo),
        "mode": mode,
        "predicted": int(m.group(1)),
        "orbits": int(m.group(2)),
        "swap_fixed": int(m.group(3)),
        "class_sum": int(m.group(4)) if m.group(4) else None,
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
                                          out["predicted"], elapsed_ms,
                                          class_sum=out["class_sum"])
        if n_written != out["predicted"]:
            out["warning_count_mismatch"] = (
                f"wrote {n_written} generator lines but predicted={out['predicted']}")
        out["output_path"] = str(output_path)
    result_path.write_text(json.dumps(out, indent=2))
    return out


def _count_generator_lines(path):
    """Count logical generator lines ('['-starters, backslash-continuation
    aware) in a composed combo .g file.  Mirrors runner/combos.py's
    completeness counting without importing the runner package."""
    n = 0
    prev_continued = False
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n").rstrip("\r")
            if not prev_continued and line.startswith("["):
                n += 1
            prev_continued = line.endswith("\\")
    return n


def predict(combo, mode="auto", emit_generators=False, output_path=None,
            force=False, timeout=3600, extend_only=False):
    """Single-combo entry point.  Since 2026-07-02 this is a thin wrapper
    over predict_batch (a 1-job batch): the single-combo GAP driver's
    checkpoint design had a crash-resume window that silently dropped or
    duplicated emitted generator lines (see _predict_gap_driver), and the
    driver also lacked the BATCH path's streamed gens / windowed LEFT /
    lazy-recon / memory-cap machinery (the entry-point divergence that made
    the same pair loop cost 0.37GB via batch vs 9.5GB via --combo).  One
    driver fewer to keep in sync.

    --extend-only still uses the legacy driver (it exits before the pair
    loop, where the crash window lives).  PRED_COMBO_LEGACY=1 forces the
    old driver for A/B comparison."""
    if isinstance(combo, str):
        combo = parse_combo_str(combo)
    if extend_only or os.environ.get("PRED_COMBO_LEGACY") == "1":
        return _predict_gap_driver(combo, mode=mode,
                                   emit_generators=emit_generators,
                                   output_path=output_path, force=force,
                                   timeout=timeout, extend_only=extend_only)
    try:
        mode = resolve_strategy(combo, mode)
    except ValueError as e:
        return {"error": str(e)}
    if mode == "unsupported":
        return {"error": "no 2-factor mode applicable to this combo"}

    target_str = combo_filename(combo)
    work = TMP / target_str
    work.mkdir(parents=True, exist_ok=True)
    result_path = work / "result.json"
    if (result_path.exists() and not force and not emit_generators
            and output_path is None):
        return json.loads(result_path.read_text())

    # The batch driver always composes the legacy combo file itself; give it
    # a work-local path when the caller didn't ask for one.  Comment lines
    # in the composed file are skipped by every generator-list consumer
    # (the wreath two-step's --candidates-from, parse_combo_file, ...), so
    # the composed file doubles as the "generators_file".
    out_path = Path(output_path) if output_path is not None else (work / "out.g")
    try:
        results = predict_batch(
            [{"combo": combo, "mode": mode, "output_path": str(out_path)}],
            force=force, timeout=timeout)
    except ValueError as e:
        return {"error": str(e)}
    if not results:
        return {"error": "empty batch result"}
    r = dict(results[0])
    if "error" in r:
        return r
    try:
        inputs = resolve_inputs(combo, mode)
        r["left_combo"] = combo_filename(inputs["left_combo"])
        r["right"] = (f"TG({inputs['right_tg'][0]},{inputs['right_tg'][1]})"
                      if inputs["right_tg"]
                      else combo_filename(inputs["right_combo"]))
        r["m_left"] = inputs["m_left"]
        r["m_right"] = inputs["m_right"]
    except (ValueError, KeyError):
        pass
    # Composed-output integrity check: the body must carry exactly the
    # predicted number of generator lines.  This is the loud replacement for
    # the old warning_count_mismatch, which no caller consumed.
    if not out_path.exists():
        return {"error": f"batch job reported success but no output at {out_path}",
                **{k: v for k, v in r.items() if k != "output_path"}}
    n_body = _count_generator_lines(out_path)
    if r.get("predicted") is not None and n_body != r["predicted"]:
        try:
            out_path.unlink()
        except OSError:
            pass
        return {"error": (f"composed output has {n_body} generator lines but "
                          f"predicted={r['predicted']} (truncated emit; "
                          f"output removed)"),
                "combo": r.get("combo"), "mode": r.get("mode")}
    if emit_generators or output_path is not None:
        r["generators_file"] = str(out_path)
    result_path.write_text(json.dumps(r, indent=2))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", help="JSON file with list of jobs sharing LEFT source")
    ap.add_argument("--super-batch",
                    help="JSON file with list of GROUPS, each group has its own LEFT")
    ap.add_argument("--combo")
    # Clean modes: distinguished / split / burnside_m2.  Legacy fine-grained
    # strategy names (holt_split, peel_c2_pair) are accepted as aliases for
    # backward compatibility with runner/route.py and existing callers.
    ap.add_argument("--mode", default="auto",
                    choices=["auto", "distinguished", "split", "burnside_m2",
                             "holt_split", "peel_c2_pair"])
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
