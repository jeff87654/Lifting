#!/usr/bin/env python3
"""
run_identity_path.py — identity-route emitter (pure Python, no GAP).

Three counting identities, each verified exact (class counts AND labelled
sums, 0 failures) against every applicable row of
s2_to_s22_combo_class_counts.csv (2026-07-02; see memory
`coprime_product_transfer_identities`), let whole families of combos be
materialized textually from already-built lower-n output files:

  id_product — the combo's blocks split into >=2 clusters whose species
      orders have pairwise-disjoint prime supports.  Goursat glue across
      clusters divides both cluster orders, hence is trivial (a subdirect
      product cannot acquire new primes), and conjugacy fusion factorizes
      (blocks of equal degree always share prime factors, so no orbit can
      cross clusters):
          classes  = prod_c classes(cluster_c)
          labelled = n!/prod(n_c!) * prod_c labelled(cluster_c)
      Emission: interleaved outer product of the cluster files on disjoint
      point ranges.

  id_absorb — exactly one block of degree d in DSET whose species T is A_d
      or one of the simple groups in SIMPLE_EXTRA, against a rest coprime
      to rad(d).  T's only quotients are 1 and T-sized ones killed by
      coprimality, so the glue is trivial and H = T x K:
          classes  = classes(rest)
          labelled = labelled(rest) * n! * L_T / (m! * d!)
      (L_T = the standalone [d,t].g's # class_sum: = d!/|N_{S_d}(T)|.)
      Emission: product of the rest file with the [d,t] bootstrap file
      (same emitter as id_product).

  id_transfer — exactly one block of degree d in DSET whose species T has
      order 2d or d! (unique C2 quotient; all other quotients killed by
      rad(d)-coprimality of the rest), rest (2,1)-free.  The glue data
      (unique C2-kernel, Aut(C2)=1, trivial N-side fusion) is identical to
      a (2,1) block's, so the classes biject with the [2,1] u rest combo:
          classes  = classes([2,1] u rest at m+2)
          labelled = labelled(target) * 2 * n! * L_T / ((m+2)! * d!)
      Emission: stream the target file; in each line replace the 2-block
      2-cycle by a fixed reflection rho of T on d fresh points and append
      generators of T's unique index-2 subgroup M — for glue=1 lines this
      generates T x K, for glue=C2 lines {(x,k) : phi_T(x) = phi(k)}, i.e.
      exactly the image of the class bijection.

Usage (mirrors run_c2_glue_path.py):
    python run_identity_path.py --combo "[3,1]_[4,3]_[4,3]" \
        --output-path out.g --source-dir parallel_sn_opt0610
    python run_identity_path.py --batch-json jobs.json --source-dir ...
        # jobs.json: [{"combo": "...", "output_path": "..."}, ...]

Self-checks (line counts vs source headers, FPF point coverage, exact
divisibility of the labelled formulas) are on by default; the sampled
coverage checks can be disabled with PRED_IDENTITY_CHECK=0.
"""
from __future__ import annotations
import argparse
import itertools
import json
import math
import os
import re
import time
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
TG_ORDERS_PATH = ROOT / "database" / "tg_orders.json"

# Degrees eligible for the single-block identities.  All odd: the |T|=2d
# transfer classification relies on |T| having 2-part exactly 2, and the
# S_d/A_d generator constructions rely on the d-cycle being even.
# Degree 3 added 2026-07-02 (second pass): a (3,1) block with 3-coprime rest
# is a 3-group vs 3'-rest, i.e. always multi-component -> id_product, so the
# only d=3 capture here is the (3,2) S3-block TRANSFER (= the user's
# identity B, verified 27,455/27,455): [3,2] u rest = [2,1] u rest at n-1.
# This moves the c3_glue-[3,2] monsters (e.g. n=23 [3,2]_[4,3]^3_[8,22]
# ~72M classes) from a GAP stream to pure-Python textual emission.
DSET = (3, 5, 7, 9, 11, 13, 15, 17, 19)

# Simple groups among DSET-degree transitive groups that are neither C_p
# (p-group -> id_product territory) nor A_d (caught by the d!/2 order test):
# PSL(3,2)@7, PSL(2,11)@11, M11@11, PSL(3,3)@13, PSL(2,16)@17.  Within DSET
# degrees these orders are unambiguous (any other group of the same order
# would need an element order its S_d cannot supply).  A GAP-built quotient
# table would supersede this list (and upgrade more species).
SIMPLE_EXTRA = frozenset({168, 660, 7920, 5616, 4080})

PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23)

_TG_ORDERS = None
_PSET_CACHE = {}


def _tg_orders():
    global _TG_ORDERS
    if _TG_ORDERS is None:
        _TG_ORDERS = json.loads(TG_ORDERS_PATH.read_text(encoding="utf-8"))
    return _TG_ORDERS


def tg_order(d, t):
    """Size(TransitiveGroup(d,t)), or None when the table doesn't cover it
    (callers must treat None as 'not identity-eligible')."""
    lst = _tg_orders().get(str(d))
    if lst is None or not (1 <= t <= len(lst)):
        return None
    return lst[t - 1]


def primeset(d, t):
    """Frozenset of primes dividing |TransitiveGroup(d,t)| (all <= 23 for
    the degrees the build reaches), or None if the order is unknown."""
    key = (d, t)
    if key not in _PSET_CACHE:
        o = tg_order(d, t)
        if o is None:
            _PSET_CACHE[key] = None
        else:
            s = set()
            for p in PRIMES:
                while o % p == 0:
                    s.add(p)
                    o //= p
            if o != 1:   # prime factor > 23: cannot happen for degree <= 23
                _PSET_CACHE[key] = None
            else:
                _PSET_CACHE[key] = frozenset(s)
    return _PSET_CACHE[key]


def rad_primes(d):
    return frozenset(p for p in PRIMES if d % p == 0)


def components(combo):
    """Partition the blocks into clusters with pairwise-disjoint species
    prime supports (union-find).  Returns a list of sorted combo tuples, or
    None if any species order is unknown."""
    blocks = list(combo)
    psets = []
    for b in blocks:
        ps = primeset(*b)
        if ps is None:
            return None
        psets.append(ps)
    parent = list(range(len(blocks)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            if psets[i] & psets[j]:
                pi, pj = find(i), find(j)
                if pi != pj:
                    parent[pi] = pj
    groups = {}
    for i, b in enumerate(blocks):
        groups.setdefault(find(i), []).append(b)
    return [tuple(sorted(g)) for g in groups.values()]


def classify_identity(combo):
    """None, or a dict describing the identity that owns this combo:
      {"kind": "id_product",  "factors": [combo, ...]}
      {"kind": "id_absorb",   "factors": [rest, (block,)], "block": (d,t)}
      {"kind": "id_transfer", "block": (d,t), "rest": rest,
       "target": combo of [2,1] u rest}
    Pure function of the combo + tg_orders.json; runner.route imports this
    so router and engine can never skew."""
    combo = tuple(sorted(combo))
    if len(combo) < 2:
        return None
    comps = components(combo)
    if comps is None:
        return None
    if len(comps) >= 2:
        return {"kind": "id_product", "factors": comps}
    for d in DSET:
        blocks_d = [b for b in combo if b[0] == d]
        if len(blocks_d) != 1:
            continue
        block = blocks_d[0]
        rest = tuple(sorted(b for b in combo if b != block))
        if not rest:
            continue
        rp = rad_primes(d)
        if any(primeset(*b) & rp for b in rest):
            continue
        o = tg_order(*block)
        if o is None:
            continue
        if o == math.factorial(d) // 2 or o in SIMPLE_EXTRA:
            return {"kind": "id_absorb", "factors": [rest, (block,)],
                    "block": block}
        if (o == 2 * d or o == math.factorial(d)) and (2, 1) not in rest:
            return {"kind": "id_transfer", "block": block, "rest": rest,
                    "target": tuple(sorted(rest + ((2, 1),)))}
    return None


# --- combo/file helpers (format mirrors run_c2_glue_path.py) --------------

def parse_combo(combo_str):
    pairs = re.findall(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]", combo_str)
    return tuple(sorted((int(d), int(t)) for d, t in pairs))


def combo_to_str(combo) -> str:
    return "_".join(f"[{d},{t}]" for d, t in combo)


def combo_header(combo) -> str:
    return "[ " + ", ".join(f"[ {d}, {t} ]" for d, t in combo) + " ]"


def source_path(source_dir, combo) -> Path:
    degs = sorted((d for d, _ in combo), reverse=True)
    part = "[" + ",".join(str(d) for d in degs) + "]"
    return (Path(source_dir).resolve() / str(sum(degs)) / part
            / (combo_to_str(combo) + ".g"))


def read_two_headers(path):
    """(deduped, class_sum) from the leading '#' headers; (None, None)-ish
    entries when absent."""
    deduped = class_sum = None
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.startswith("#"):
                    break
                m = re.match(r"#\s*deduped:\s*(\d+)", line)
                if m:
                    deduped = int(m.group(1))
                m = re.match(r"#\s*class_sum:\s*(\d+)", line)
                if m:
                    class_sum = int(m.group(1))
    except OSError:
        pass
    return deduped, class_sum


def iter_gen_lines(path):
    """Yield logical generator lines (one per class): '['-prefixed, joining
    trailing-backslash continuations and unbalanced-bracket wraps."""
    buf = ""
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not buf:
                if not line or line[0] != "[":
                    continue
            cont = line.endswith("\\")
            if cont:
                line = line[:-1]
            buf += line
            if not cont and buf.count("[") == buf.count("]"):
                yield buf
                buf = ""
    if buf:
        raise ValueError(f"unterminated generator line in {path}")


NUM_RE = re.compile(r"\d+")


def relabel_inner(line, offset):
    """Strip the outer [ ] and shift every point by offset.  Returns
    (inner_string, points_seen_before_shift)."""
    pts = set()

    def sub(m):
        v = int(m.group())
        pts.add(v)
        return str(v + offset)

    inner = NUM_RE.sub(sub, line[1:-1]) if offset else line[1:-1]
    if not offset:
        for m in NUM_RE.finditer(inner):
            pts.add(int(m.group()))
    return inner, pts


# --- permutation utilities (transfer block groups; |T| <= 2*19) ------------

def parse_gen_list(line):
    """'[g1,g2,...]' -> [[(cycle),(cycle)], ...]; '()' -> []."""
    inner = line.strip()[1:-1]
    gens, depth, start = [], 0, 0
    for i, ch in enumerate(inner):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            gens.append(inner[start:i])
            start = i + 1
    gens.append(inner[start:])
    out = []
    for g in gens:
        cycles = []
        for grp in re.findall(r"\(([^()]*)\)", g):
            grp = grp.strip()
            if grp:
                cycles.append(tuple(int(x) for x in grp.split(",")))
        out.append(cycles)
    return out


def perm_from_cycles(cycles, deg):
    img = list(range(deg + 1))
    for c in cycles:
        for i in range(len(c)):
            img[c[i]] = c[(i + 1) % len(c)]
    return tuple(img[1:])


def pmul(p, q):
    """x -> q(p(x))."""
    return tuple(q[x - 1] for x in p)


def pinv(p):
    inv = [0] * len(p)
    for i, x in enumerate(p):
        inv[x - 1] = i + 1
    return tuple(inv)


def cycles_of(p):
    seen, out = set(), []
    for s in range(1, len(p) + 1):
        if s in seen or p[s - 1] == s:
            continue
        c, x = [], s
        while x not in seen:
            seen.add(x)
            c.append(x)
            x = p[x - 1]
        out.append(tuple(c))
    return out


def closure(gens, deg):
    idp = tuple(range(1, deg + 1))
    elems = {idp}
    frontier = [idp]
    gens = [g for g in gens if g != idp]
    while frontier:
        nxt = []
        for e in frontier:
            for g in gens:
                x = pmul(e, g)
                if x not in elems:
                    elems.add(x)
                    nxt.append(x)
        frontier = nxt
    return elems


def cycles_str(cycles, offset=0):
    if not cycles:
        return "()"
    return "".join(
        "(" + ",".join(str(x + offset) for x in c) + ")" for c in cycles)


def transfer_block_data(block, source_dir):
    """(kernel_gens_cycles, rho_cycles) on points 1..d: generators of T's
    unique index-2 subgroup M plus a fixed element rho of T \\ M."""
    d, t = block
    o = tg_order(d, t)
    if o == math.factorial(d):
        # T = S_d natural; M = A_d = <(1,2,3),(1,2,...,d)> (d odd), rho=(1,2).
        if d % 2 == 0:
            raise ValueError(f"transfer S_{d}: even degree unsupported")
        return [[(1, 2, 3)], [tuple(range(1, d + 1))]], [(1, 2)]
    if o != 2 * d:
        raise ValueError(f"transfer block {block}: unexpected order {o}")
    boot = source_path(source_dir, (block,))
    lines = list(iter_gen_lines(boot))
    if len(lines) != 1:
        raise ValueError(f"bootstrap {boot} has {len(lines)} lines, want 1")
    gens = [perm_from_cycles(cyc, d) for cyc in parse_gen_list(lines[0])]
    T = closure(gens, d)
    if len(T) != o:
        raise ValueError(f"bootstrap {boot}: |<gens>|={len(T)} != order {o}")
    # M = <squares, commutators> = the unique index-2 subgroup.
    seed = {pmul(g, g) for g in T}
    seed |= {pmul(pmul(pinv(g), pinv(h)), pmul(g, h)) for g in T for h in T}
    M = closure(list(seed), d)
    if len(T) != 2 * len(M):
        raise ValueError(
            f"block {block}: |T|/|M| = {len(T)}/{len(M)} != 2 "
            "(no unique C2 quotient — misclassified)")

    def perm_order(p):
        o1 = 1
        for c in cycles_of(p):
            o1 = o1 * len(c) // math.gcd(o1, len(c))
        return o1

    ker_gens, span = [], closure([], d)
    for e in sorted(M, key=lambda p: (-perm_order(p), p)):
        if e not in span:
            ker_gens.append(e)
            span = closure(ker_gens, d)
            if len(span) == len(M):
                break
    rho = min(e for e in T if e not in M)
    # <M, rho> = T is transitive, so every block point appears in the
    # emitted cycles (a point fixed by all of them would be fixed by T).
    return [cycles_of(g) for g in ker_gens], cycles_of(rho)


# --- emitters ---------------------------------------------------------------

def _atomic_write(output_path, headers, body_iter):
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + f".tmp.{os.getpid()}")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as f:
            for h in headers:
                f.write(h + "\n")
            for chunk in body_iter:
                f.write(chunk)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(out)


def _factor_info(source_dir, factor):
    path = source_path(source_dir, factor)
    deduped, class_sum = read_two_headers(path)
    if deduped is None or deduped < 1:
        raise ValueError(f"factor source missing/broken # deduped: {path}")
    if class_sum is None:
        raise ValueError(f"factor source missing # class_sum: {path}")
    return {"combo": factor, "path": path, "n": sum(d for d, _ in factor),
            "deduped": deduped, "class_sum": class_sum}


def emit_product(combo, ident, output_path, source_dir, check):
    """id_product / id_absorb: interleaved outer product of factor files."""
    t0 = time.time()
    infos = [_factor_info(source_dir, f) for f in ident["factors"]]
    # Largest factor first: it gets offset 0 and streams unrelabeled.
    infos.sort(key=lambda r: -r["deduped"])
    off = 0
    for info in infos:
        info["offset"] = off
        off += info["n"]
    n = off

    expected = 1
    for info in infos:
        expected *= info["deduped"]
    denom = 1
    for info in infos:
        denom *= math.factorial(info["n"])
    if math.factorial(n) % denom:
        raise AssertionError("multinomial not integral (impossible)")
    class_sum = math.factorial(n) // denom
    for info in infos:
        class_sum *= info["class_sum"]

    # Pre-merge the non-streamed factors' relabeled inner strings.  Their
    # cartesian size is expected/big_count, bounded by the guard below.
    small_inners = [""]
    for info in infos[1:]:
        lines = []
        cnt = 0
        full = frozenset(range(1, info["n"] + 1))
        for ln in iter_gen_lines(info["path"]):
            cnt += 1
            inner, pts = relabel_inner(ln, info["offset"])
            if pts != full:
                raise ValueError(
                    f"{info['path']} line {cnt}: point support {sorted(pts)}"
                    f" != 1..{info['n']} (not an FPF line)")
            lines.append(inner)
        if cnt != info["deduped"]:
            raise ValueError(
                f"{info['path']}: streamed {cnt} lines but header says "
                f"# deduped: {info['deduped']} (truncated/corrupt source)")
        merged = [(s + "," + l) if s else l
                  for s in small_inners for l in lines]
        if len(merged) > 10_000_000:
            raise ValueError("product cofactor cartesian too large")
        small_inners = merged

    big = infos[0]
    big_full = frozenset(range(1, big["n"] + 1))
    state = {"cnt": 0}

    def body():
        for ln in iter_gen_lines(big["path"]):
            state["cnt"] += 1
            inner = ln[1:-1]
            if check and (state["cnt"] <= 200 or state["cnt"] % 10000 == 0):
                pts = {int(m.group()) for m in NUM_RE.finditer(inner)}
                if pts != big_full:
                    raise ValueError(
                        f"{big['path']} line {state['cnt']}: support != "
                        f"1..{big['n']}")
            yield "".join(f"[{inner},{s}]\n" for s in small_inners)

    headers = [
        f"# combo: {combo_header(combo)}",
        f"# candidates: {expected}",
        f"# deduped: {expected}",
        f"# class_sum: {class_sum}",
        "# elapsed_ms: __ELAPSED__",
        f"# engine: identity_{ident['kind'][3:]}",
        "# identity: " + " x ".join(combo_to_str(i["combo"]) for i in infos),
    ]
    _emit_with_elapsed(output_path, headers, body, t0)
    if state["cnt"] != big["deduped"]:
        Path(output_path).unlink(missing_ok=True)
        raise ValueError(
            f"{big['path']}: streamed {state['cnt']} lines but header says "
            f"# deduped: {big['deduped']} (truncated/corrupt source)")
    return expected, class_sum, t0


def emit_transfer(combo, ident, output_path, source_dir, check):
    """id_transfer: stream [2,1] u rest, substituting the 2-block."""
    t0 = time.time()
    d, t = ident["block"]
    target = ident["target"]
    src = source_path(source_dir, target)
    src_deduped, src_cs = read_two_headers(src)
    if src_deduped is None or src_deduped < 1:
        raise ValueError(f"transfer source missing/broken # deduped: {src}")
    if src_cs is None:
        raise ValueError(f"transfer source missing # class_sum: {src}")
    boot_deduped, l_t = read_two_headers(source_path(source_dir,
                                                     (ident["block"],)))
    if boot_deduped != 1 or not l_t:
        raise ValueError(
            f"bootstrap [{d},{t}].g missing/odd headers under {source_dir}")

    m = sum(dd for dd, _ in ident["rest"])
    n = m + d
    num = src_cs * 2 * math.factorial(n) * l_t
    den = math.factorial(m + 2) * math.factorial(d)
    if num % den:
        raise AssertionError("transfer labelled formula not integral")
    class_sum = num // den

    ker_cycles, rho_cycles = transfer_block_data(ident["block"], source_dir)
    ker_strs = [cycles_str(c, m) for c in ker_cycles]
    rho_str = cycles_str(rho_cycles, m)

    state = {"cnt": 0}

    def body():
        for ln in iter_gen_lines(src):
            state["cnt"] += 1
            gens = parse_gen_list(ln)
            # Union-find the source points into orbits to locate the 2-block.
            parent = {}

            def find(x):
                r = x
                while parent.get(r, r) != r:
                    r = parent[r]
                while parent.get(x, x) != x:
                    parent[x], x = r, parent[x]
                return r

            pts = set()
            for g in gens:
                for c in g:
                    pts.update(c)
                    r0 = find(c[0])
                    for x in c[1:]:
                        parent[find(x)] = r0
            orbits = {}
            for p in pts:
                orbits.setdefault(find(p), []).append(p)
            two = [o for o in orbits.values() if len(o) == 2]
            if len(two) != 1 or len(pts) != m + 2:
                raise ValueError(
                    f"{src} line {state['cnt']}: expected a unique 2-orbit "
                    f"on {m + 2} moved points, got orbit sizes "
                    f"{sorted(len(o) for o in orbits.values())}")
            a, b = sorted(two[0])
            pmap = {}
            for i, p in enumerate(sorted(pts - {a, b})):
                pmap[p] = i + 1
            out_gens = []
            for g in gens:
                parts = []
                swap = False
                for c in g:
                    cs_ = set(c)
                    if cs_ == {a, b}:
                        swap = True
                        continue
                    if cs_ & {a, b}:
                        raise ValueError(
                            f"{src} line {state['cnt']}: 2-block point in a "
                            f"larger cycle {c}")
                    parts.append(
                        "(" + ",".join(str(pmap[x]) for x in c) + ")")
                if swap:
                    parts.append(rho_str)
                out_gens.append("".join(parts) or "()")
            yield "[" + ",".join(out_gens + ker_strs) + "]\n"

    headers = [
        f"# combo: {combo_header(combo)}",
        f"# candidates: {src_deduped}",
        f"# deduped: {src_deduped}",
        f"# class_sum: {class_sum}",
        "# elapsed_ms: __ELAPSED__",
        "# engine: identity_transfer",
        f"# identity: [{d},{t}] <- [2,1] via {combo_to_str(target)}",
    ]
    _emit_with_elapsed(output_path, headers, body, t0)
    if state["cnt"] != src_deduped:
        Path(output_path).unlink(missing_ok=True)
        raise ValueError(
            f"{src}: streamed {state['cnt']} lines but header says "
            f"# deduped: {src_deduped} (truncated/corrupt source)")
    return src_deduped, class_sum, t0


def _emit_with_elapsed(output_path, headers, body, t0):
    """Write atomically with a fixed-width elapsed placeholder, then patch
    the real value in place (same byte width, so size/format are stable)."""
    headers = [h.replace("__ELAPSED__", "%10d" % 0) for h in headers]
    _atomic_write(output_path, headers, body())
    elapsed_ms = min(int((time.time() - t0) * 1000), 9_999_999_999)
    with open(output_path, "r+b") as f:
        head = f.read(4096)
        tag = b"# elapsed_ms: "
        idx = head.find(tag)
        if idx >= 0:
            f.seek(idx + len(tag))
            f.write(b"%10d" % elapsed_ms)


# --- driver -----------------------------------------------------------------

def run_one(combo_str, output_path, source_dir, check):
    combo = parse_combo(combo_str)
    ident = classify_identity(combo)
    if ident is None:
        return {"combo": combo_str, "error": "not identity-eligible"}
    try:
        if ident["kind"] in ("id_product", "id_absorb"):
            deduped, class_sum, t0 = emit_product(
                combo, ident, output_path, source_dir, check)
        else:
            deduped, class_sum, t0 = emit_transfer(
                combo, ident, output_path, source_dir, check)
    except (ValueError, AssertionError, OSError) as e:
        return {"combo": combo_str, "mode": ident["kind"], "error": str(e)}
    elapsed = round(time.time() - t0, 3)
    return {"combo": combo_str,
            "mode": "identity_" + ident["kind"][3:],
            "predicted": deduped,
            "candidates": deduped,
            "class_sum": class_sum,
            "elapsed_ms": int(elapsed * 1000),
            "elapsed_s": elapsed,
            "output_path": str(output_path)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo")
    ap.add_argument("--output-path")
    ap.add_argument("--batch-json",
                    help="JSON list of {combo, output_path} processed "
                         "sequentially in this process (no GAP involved)")
    ap.add_argument("--source-dir",
                    default=os.environ.get("PREDICT_SN_DIR",
                                           str(ROOT / "parallel_sn_opt0610")))
    ap.add_argument("--timeout", type=int, default=0)   # accepted, unused
    args = ap.parse_args()

    check = os.environ.get("PRED_IDENTITY_CHECK") != "0"

    if args.batch_json:
        specs = [(j["combo"], j["output_path"])
                 for j in json.loads(Path(args.batch_json).read_text())]
        results = [run_one(c, o, args.source_dir, check) for c, o in specs]
        print(json.dumps(results, indent=2))
    else:
        if not (args.combo and args.output_path):
            ap.error("--combo and --output-path required "
                     "(or use --batch-json)")
        print(json.dumps(run_one(args.combo, args.output_path,
                                 args.source_dir, check), indent=2))


if __name__ == "__main__":
    main()
