#!/usr/bin/env python3
"""
predict_full_general_wreath.py — single-cluster [d,t]^m predictor.

Same approach as predict_full_general.py (materialize per Aut(Q)-orbit,
then pairwise RA-dedup with fingerprint bucketing) but uses the smaller
ambient group N_T wr S_m instead of full S_(m*d).  For the FPF subdirect
products we materialize, every S_n-conjugacy must be by an element of
N_T wr S_m (since both subgroups have the same m-block FPF structure of
species (d,t), and the conjugating element must preserve that structure).

This makes RA pairwise tests much cheaper -- |N_T wr S_m| << |S_n| for
larger m -- without any change to correctness vs. predict_full_general.py.

Usage:
    python predict_full_general_wreath.py --combo "[3,1]_[3,1]_[3,1]_[3,1]_[3,1]_[3,1]" --target-n 18
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

ROOT = Path(__file__).resolve().parent
SN_DIR = Path(os.environ.get("PREDICT_SN_DIR", str(ROOT / "parallel_sn")))
TMP = Path(os.environ.get("PREDICT_TMP_DIR",
                          str(ROOT / "predict_species_tmp" / "_full_general_wreath")))
TMP.mkdir(parents=True, exist_ok=True)

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def to_gap(p) -> str:
    """Windows-style path syntax for paths embedded inside GAP source."""
    return str(p).replace("\\", "/")


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


GAP_WREATH = r"""
LogTo("__LOG__");

Read("__LIFTING_G__");

# inputs
M     := __M__;       # source degree (= (m_blocks - 1) * d)
DD    := __D__;
TID   := __T_ID__;
M_BLOCKS := __M_BLOCKS__;   # total # of (d,t) blocks (m_blocks)
TARGET_N := M + DD;
SUBS_PATH := "__SUBS_CYG__";

Print("wreath: m_src=", M, " d=", DD, " t=", TID,
      " m_blocks=", M_BLOCKS, " target_n=", TARGET_N, "\n");

S_M := SymmetricGroup(M);
T_orig := TransitiveGroup(DD, TID);
S_D := SymmetricGroup(DD);

# T-side acts on [M+1..M+D] (last block).
shift := MappingPermListList([1..DD], [M+1..M+DD]);
T := T_orig^shift;
N_T_block := Normalizer(SymmetricGroup([M+1..M+DD]), T);

# Build the wreath ambient W = N_T_canonical wr S_{M_BLOCKS} on [1..TARGET_N].
# WreathProduct(N_T_canonical, S_{m}) acts naturally on M_BLOCKS blocks of
# DD points each via the imprimitive action.  We use the canonical-block
# version (on [1..DD]) and let WreathProduct distribute.
N_T_canonical := Normalizer(S_D, T_orig);
W := WreathProduct(N_T_canonical, SymmetricGroup(M_BLOCKS));
Print("|W|=|N_T wr S_m| = ", Size(W), "\n");

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

# T-side data
T_data := List(Orbits(N_T_block, NormalSubgroups(T), ConjAction),
               orbit -> rec(K := orbit[1]));
for r in T_data do
    r.hom := NaturalHomomorphismByNormalSubgroup(T, r.K);
    r.Q := Range(r.hom);
    r.qsize := Size(r.Q);
    r.qid := SafeId(r.Q);
    r.stab := Stabilizer(N_T_block, r.K, ConjAction);
    if r.qsize > 1 then
        r.AutQ := AutomorphismGroup(r.Q);
        r.A_gens := InducedAutoGens(r.stab, T, r.hom);
    else
        r.AutQ := fail;
        r.A_gens := [];
    fi;
od;
AllowedSizes := Set(List(T_data, x -> x.qsize));

Read(SUBS_PATH);   # SUBGROUPS

ALL_FP := [];

ProcessH := function(H)
    local N_H, h_normals, eligible, K_H_data, kh_data,
          a_idx, b_idx, isoTH, isos, n_isos, gens_QT, key_of, idx,
          seen, i, j, k, queue, phi, alpha, beta, neighbor, nkey,
          fp, phi_inv, orec;

    N_H := Normalizer(S_M, H);
    h_normals := NormalSubgroups(H);

    # Trivial-quotient direct product
    fp := Group(Concatenation(GeneratorsOfGroup(H), GeneratorsOfGroup(T)));
    Add(ALL_FP, fp);

    eligible := Filtered(h_normals, K -> K <> H and (Index(H, K) in AllowedSizes));
    K_H_data := [];
    for orec in Orbits(N_H, eligible, ConjAction) do
        kh_data := rec(K := orec[1]);
        kh_data.hom := NaturalHomomorphismByNormalSubgroup(H, kh_data.K);
        kh_data.Q := Range(kh_data.hom);
        kh_data.qsize := Size(kh_data.Q);
        kh_data.qid := SafeId(kh_data.Q);
        kh_data.stab := Stabilizer(N_H, kh_data.K, ConjAction);
        if kh_data.qsize > 1 then
            kh_data.A_gens := InducedAutoGens(kh_data.stab, H, kh_data.hom);
        else
            kh_data.A_gens := [];
        fi;
        Add(K_H_data, kh_data);
    od;

    for a_idx in [1..Length(K_H_data)] do
        if K_H_data[a_idx].qsize <= 1 then continue; fi;
        for b_idx in [1..Length(T_data)] do
            if T_data[b_idx].qsize <= 1 then continue; fi;
            if K_H_data[a_idx].qid <> T_data[b_idx].qid then continue; fi;

            isoTH := IsomorphismGroups(T_data[b_idx].Q, K_H_data[a_idx].Q);
            if isoTH = fail then continue; fi;

            isos := List(AsList(T_data[b_idx].AutQ), aT -> aT * isoTH);
            n_isos := Length(isos);
            gens_QT := GeneratorsOfGroup(T_data[b_idx].Q);
            key_of := function(phi)
                return List(gens_QT, q -> Image(phi, q));
            end;
            idx := rec();
            for i in [1..n_isos] do
                idx.(String(key_of(isos[i]))) := i;
            od;

            seen := ListWithIdenticalEntries(n_isos, false);
            for i in [1..n_isos] do
                if seen[i] then continue; fi;
                queue := [i];
                seen[i] := true;
                while Length(queue) > 0 do
                    j := Remove(queue);
                    phi := isos[j];
                    for alpha in K_H_data[a_idx].A_gens do
                        neighbor := phi * alpha;
                        nkey := String(key_of(neighbor));
                        if IsBound(idx.(nkey)) then
                            k := idx.(nkey);
                            if not seen[k] then seen[k] := true; Add(queue, k); fi;
                        fi;
                    od;
                    for beta in T_data[b_idx].A_gens do
                        neighbor := InverseGeneralMapping(beta) * phi;
                        nkey := String(key_of(neighbor));
                        if IsBound(idx.(nkey)) then
                            k := idx.(nkey);
                            if not seen[k] then seen[k] := true; Add(queue, k); fi;
                        fi;
                    od;
                od;
                phi_inv := InverseGeneralMapping(isos[i]);
                fp := _GoursatBuildFiberProduct(
                    H, T,
                    K_H_data[a_idx].hom, T_data[b_idx].hom,
                    phi_inv,
                    [1..M], [M+1..M+DD]);
                if fp <> fail then
                    Add(ALL_FP, fp);
                fi;
            od;
        od;
    od;
end;

t0 := Runtime();
for H_idx in [1..Length(SUBGROUPS)] do
    ProcessH(SUBGROUPS[H_idx]);
od;
mat_elapsed := Runtime() - t0;
n_materialized := Length(ALL_FP);
Print("materialized: ", n_materialized, " fp's in ", mat_elapsed, "ms\n");

# RA-dedup in W (the species normalizer N_T wr S_m) with block-aware
# fingerprints.  RA in W uses GAP's partition-backtrack methods and is fast
# *given* small bucket sizes; the key is to bucket by strong block-aware
# invariants before pairwise RA.
t1 := Runtime();

# T_BLOCKS_N_TARGET: per-block T placement on TARGET_N points.
T_blocks_full := List([1..M_BLOCKS],
    bi -> T_orig^MappingPermListList([1..DD], [(bi-1)*DD+1..bi*DD]));
T_m_full := Group(Concatenation(List(T_blocks_full, GeneratorsOfGroup)));
block_pts_list := List([1..M_BLOCKS], bi -> Set([(bi-1)*DD+1..bi*DD]));

fp_fingerprint := function(G)
    local sz, abi, ds, idg, block_perm, pure_F, pure_size, pure_abi,
          per_block_kernel_sizes, subset_dim_signature, k, S, subset_pts,
          gens_S, projG_S;
    sz := Size(G);
    abi := AbelianInvariants(G);
    ds := List(DerivedSeries(G), Size);
    if IdGroupsAvailable(sz) then idg := IdGroup(G); else idg := 0; fi;

    block_perm := Action(G, block_pts_list, OnSets);
    pure_F := Intersection(G, T_m_full);
    pure_size := Size(pure_F);
    pure_abi := AbelianInvariants(pure_F);

    per_block_kernel_sizes := SortedList(List([1..M_BLOCKS], bi ->
        Size(Group(List(GeneratorsOfGroup(pure_F),
            g -> RestrictedPerm(g, [(bi-1)*DD+1..bi*DD])), ()))));

    # Subset-projection signature: for each subset size k=2..M_BLOCKS-1,
    # multiset of |proj_S(pure_F)| over k-subsets S.  S_m-invariant via
    # SortedList.  Cheap (~0.1s for m=6).  Strongly discriminative for
    # subspace structures.
    subset_dim_signature := [];
    for k in [2..M_BLOCKS - 1] do
        Add(subset_dim_signature, SortedList(List(Combinations([1..M_BLOCKS], k),
            function(S)
                local subset_pts, gens_S;
                subset_pts := Concatenation(List(S, bi -> [(bi-1)*DD+1..bi*DD]));
                gens_S := List(GeneratorsOfGroup(pure_F),
                    g -> RestrictedPerm(g, subset_pts));
                return Size(Group(gens_S, ()));
            end)));
    od;

    return [sz, idg, abi, ds,
            Size(block_perm), IdGroup(block_perm),
            pure_size, pure_abi,
            per_block_kernel_sizes,
            subset_dim_signature];
end;

# Rich invariants borrowed from lifting_method_fast_v2.g:CheapSubgroupInvariantFull
# + ExpensiveSubgroupInvariant.  Triggered only when the cheap fingerprint leaves
# a bucket with > 1000 predicted RA-call pairs (i.e. size > 45).
fp_fingerprint_rich := function(G)
    local base, sz, moved, derived, derivedSizes, D, nc,
          orderHist, g, o, classes, cl, classHist, cycleType,
          pairs, pairOrbLens, perBlockImg, bi, blockPts;
    base := fp_fingerprint(G);
    sz := Size(G);
    moved := MovedPoints(G);

    Add(base, DerivedLength(G));
    Add(base, Size(Center(G)));
    derived := DerivedSubgroup(G);
    Add(base, Size(derived));
    Add(base, Exponent(G));

    # Derived-series sizes up to depth 6.
    derivedSizes := [sz, Size(derived)];
    D := derived;
    while Size(D) > 1 and Length(derivedSizes) < 6 do
        D := DerivedSubgroup(D);
        Add(derivedSizes, Size(D));
    od;
    Add(base, derivedSizes);

    if IsNilpotentGroup(G) then nc := NilpotencyClassOfGroup(G);
    else nc := -1; fi;
    Add(base, nc);

    # Element-order histogram (gated |G| <= 1e5).
    if sz <= 100000 then
        orderHist := [];
        for g in G do
            o := Order(g);
            if IsBound(orderHist[o]) then
                orderHist[o] := orderHist[o] + 1;
            else
                orderHist[o] := 1;
            fi;
        od;
        Add(base, orderHist);
    else
        Add(base, -1);
    fi;

    # Per-block action-image order.
    perBlockImg := [];
    for bi in [1..M_BLOCKS] do
        blockPts := [(bi-1)*DD+1..bi*DD];
        Add(perBlockImg,
            Size(G) / Size(Stabilizer(G, blockPts, OnTuples)));
    od;
    Sort(perBlockImg);
    Add(base, perBlockImg);

    # CC cycle-type histogram (gated |G| <= 1e4).
    if sz <= 10000 then
        classes := ConjugacyClasses(G);
        classHist := rec();
        for cl in classes do
            cycleType := String(SortedList(CycleLengths(Representative(cl), moved)));
            if IsBound(classHist.(cycleType)) then
                classHist.(cycleType) := classHist.(cycleType) + Size(cl);
            else
                classHist.(cycleType) := Size(cl);
            fi;
        od;
        Add(base, classHist);
    else
        Add(base, -1);
    fi;

    # 2-subset orbit lengths (gated |moved| <= 20).
    if Length(moved) > 0 and Length(moved) <= 20 then
        pairs := Combinations(moved, 2);
        pairOrbLens := SortedList(List(Orbits(G, pairs, OnSets), Length));
        Add(base, pairOrbLens);
    else
        Add(base, -1);
    fi;

    return base;
end;

fps := List(ALL_FP, fp_fingerprint);
parent := [1..n_materialized];
UF_Find := function(x)
    while parent[x] <> x do
        parent[x] := parent[parent[x]]; x := parent[x];
    od;
    return x;
end;
UF_Union := function(x, y)
    local rx, ry;
    rx := UF_Find(x); ry := UF_Find(y);
    if rx <> ry then parent[ry] := rx; fi;
end;

# List-of-buckets to avoid GAP record-name 1023-char cap on long fingerprints.
bucket_keys := [];
bucket_lists := [];
for i in [1..n_materialized] do
    pos := Position(bucket_keys, fps[i]);
    if pos = fail then
        Add(bucket_keys, fps[i]);
        Add(bucket_lists, [i]);
    else
        Add(bucket_lists[pos], i);
    fi;
od;
Print("buckets: ", Length(bucket_lists),
      " (max bucket size: ", Maximum(List(bucket_lists, Length)), ")\n");

# Trigger rich-invariant upgrade for the WHOLE combo when any bucket has
# > 1000 predicted RA-call pairs (size > 45) OR total predicted pairs > 5000.
# Mirrors legacy RICH_DEDUP_THRESHOLD = 1000 from lifting_method_fast_v2.g.
max_bucket_size := Maximum(List(bucket_lists, Length));
total_pred_ra := Sum(bucket_lists, b -> Length(b) * (Length(b) - 1) / 2);
if max_bucket_size > 45 or total_pred_ra > 5000 then
    Print("UPGRADE: max bucket=", max_bucket_size,
          " total_pred_ra=", total_pred_ra,
          " -> recomputing with rich invariants\n");
    t_rich := Runtime();
    fps := List(ALL_FP, fp_fingerprint_rich);
    Print("UPGRADE: rich fingerprints in ", Runtime() - t_rich, "ms\n");
    bucket_keys := [];
    bucket_lists := [];
    for i in [1..n_materialized] do
        pos := Position(bucket_keys, fps[i]);
        if pos = fail then
            Add(bucket_keys, fps[i]);
            Add(bucket_lists, [i]);
        else
            Add(bucket_lists[pos], i);
        fi;
    od;
    Print("UPGRADE: re-bucketed -> ", Length(bucket_lists), " buckets",
          " (max size: ", Maximum(List(bucket_lists, Length)), ",",
          " new total_pred_ra: ",
          Sum(bucket_lists, b -> Length(b) * (Length(b) - 1) / 2), ")\n");
fi;

# Debug: print bucket sizes only (skip key dump for legibility on large buckets)
for b_dbg in [1..Length(bucket_lists)] do
    Print("  bucket ", b_dbg, " size=", Length(bucket_lists[b_dbg]), "\n");
od;

n_conj_pairs := 0;
n_ra_calls := 0;
ra_total_ms := 0;
ra_max_ms := 0;
for b_idx in [1..Length(bucket_lists)] do
    bk := bucket_lists[b_idx];
    bucket_t0 := Runtime();
    bucket_calls := 0;
    for i in [1..Length(bk)-1] do
        for j in [i+1..Length(bk)] do
            if UF_Find(bk[i]) = UF_Find(bk[j]) then continue; fi;
            n_ra_calls := n_ra_calls + 1;
            bucket_calls := bucket_calls + 1;
            ra_t0 := Runtime();
            ra_result := RepresentativeAction(W, ALL_FP[bk[i]], ALL_FP[bk[j]]);
            ra_elapsed := Runtime() - ra_t0;
            ra_total_ms := ra_total_ms + ra_elapsed;
            if ra_elapsed > ra_max_ms then ra_max_ms := ra_elapsed; fi;
            if ra_result <> fail then
                UF_Union(bk[i], bk[j]);
                n_conj_pairs := n_conj_pairs + 1;
            fi;
        od;
    od;
    Print("  bucket ", b_idx, " size=", Length(bk),
          " calls=", bucket_calls,
          " elapsed=", Runtime() - bucket_t0, "ms\n");
od;
Print("RA TIMING: total_calls=", n_ra_calls,
      "  total_time=", ra_total_ms, "ms",
      "  avg=", Int(ra_total_ms / Maximum(n_ra_calls, 1)), "ms",
      "  max=", ra_max_ms, "ms\n");
classes := Set([1..n_materialized], i -> UF_Find(i));
n_distinct := Length(classes);
ra_elapsed := Runtime() - t1;
Print("RA-in-W dedup: ", n_distinct, " distinct from ", n_materialized,
      " (", n_ra_calls, " RA calls, ", n_conj_pairs, " conj pairs, ",
      ra_elapsed, "ms)\n");

# Emit one fp generator-list per distinct class (one rep per UF class).
# Output written as raw bracketed lines; Python wrapper composes legacy header.
EMIT_GENS_PATH := "__GEN_PATH__";
if EMIT_GENS_PATH <> "" then
    PrintTo(EMIT_GENS_PATH, "");
    seen_class := rec();
    for i in [1..n_materialized] do
        cls := UF_Find(i);
        cls_key := String(cls);
        if not IsBound(seen_class.(cls_key)) then
            seen_class.(cls_key) := true;
            gens := GeneratorsOfGroup(ALL_FP[i]);
            if Length(gens) > 0 then
                gens_s := JoinStringsWithSeparator(List(gens, String), ",");
            else
                gens_s := "";
            fi;
            AppendTo(EMIT_GENS_PATH, "[", gens_s, "]\n");
        fi;
    od;
fi;

Print("RESULT n_materialized=", n_materialized,
      " n_distinct=", n_distinct,
      " predicted=", n_distinct, "\n");
LogTo();
QUIT;
"""


def _format_combo_header(combo):
    """Legacy '# combo:' line.  combo is a list of (d, t) tuples."""
    pairs = ", ".join(f"[ {d}, {t} ]" for d, t in sorted(combo))
    return f"# combo: [ {pairs} ]"


def _join_gap_continuations(raw_lines):
    joined, buf = [], []
    for ln in raw_lines:
        if ln.endswith("\\"):
            buf.append(ln[:-1])
        else:
            buf.append(ln)
            joined.append("".join(buf))
            buf = []
    if buf:
        joined.append("".join(buf))
    return [ln for ln in joined if ln.strip()]


def _write_legacy_format(output_path, combo, raw_gens_lines, deduped_count, elapsed_ms):
    """Atomic write: write to output_path.tmp, then os.replace() to final path.
    Crashes mid-write leave only the .tmp; the final file only appears once
    all gens are flushed."""
    joined_lines = _join_gap_continuations(raw_gens_lines)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(_format_combo_header(combo) + "\n")
        f.write(f"# candidates: {deduped_count}\n")
        f.write(f"# deduped: {deduped_count}\n")
        f.write(f"# elapsed_ms: {elapsed_ms}\n")
        for line in joined_lines:
            f.write(line + "\n")
    os.replace(tmp_path, output_path)   # atomic on POSIX; also atomic on Windows for same volume
    return len(joined_lines)


def predict_wreath(combo_str: str, target_n=18, timeout=3600,
                   emit_generators=False, output_path=None):
    pat = re.compile(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]")
    pairs = pat.findall(combo_str)
    target_combo = tuple(sorted((int(d), int(t)) for d, t in pairs))
    species = set(target_combo)
    if len(species) != 1:
        return {"error": f"not single-cluster: species={species}"}
    d, t = next(iter(species))
    m_blocks = len(target_combo)
    if m_blocks < 2:
        return {"error": "m_blocks must be >= 2"}

    # Source = (m-1) blocks of (d, t)
    src_n = (m_blocks - 1) * d
    src_part = "[" + ",".join([str(d)] * (m_blocks - 1)) + "]"
    src_combo = "_".join([f"[{d},{t}]"] * (m_blocks - 1))
    src_file = SN_DIR / str(src_n) / src_part / f"{src_combo}.g"
    if not src_file.exists():
        return {"error": f"source not found: {src_file}"}

    target_str = "_".join(f"[{dd},{tt}]" for dd, tt in target_combo)
    work = TMP / target_str
    work.mkdir(parents=True, exist_ok=True)

    subs = parse_combo_file(src_file)
    if not subs:
        return {"error": "empty source"}
    subs_g = work / "subs.g"
    with open(subs_g, "w") as f:
        f.write("SUBGROUPS := [\n")
        for i, s in enumerate(subs):
            sep = "," if i < len(subs) - 1 else ""
            f.write(f"  Group({s}){sep}\n")
        f.write("];\n")
    log = work / "wreath.log"
    if log.exists(): log.unlink()
    if output_path is not None:
        emit_generators = True
    gen_path = (work / "fps.g") if emit_generators else None
    if gen_path is not None and gen_path.exists(): gen_path.unlink()
    run_g = work / "run.g"
    run_g.write_text(
        GAP_WREATH
        .replace("__LOG__", to_gap(log))
        .replace("__LIFTING_G__", to_gap(ROOT / "lifting_algorithm.g"))
        .replace("__M__", str(src_n))
        .replace("__D__", str(d))
        .replace("__T_ID__", str(t))
        .replace("__M_BLOCKS__", str(m_blocks))
        .replace("__SUBS_CYG__", to_gap(subs_g))
        .replace("__GEN_PATH__", to_gap(gen_path) if gen_path else ""),
        encoding="utf-8",
    )

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    t0 = time.time()
    # timeout >= 30 days OR <= 0 means "no timeout" (avoid threading.Lock overflow on Windows).
    sub_timeout = None if (timeout is None or timeout <= 0 or timeout >= 86400 * 30) else timeout
    try:
        if sub_timeout is None:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        else:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=sub_timeout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "elapsed_s": time.time() - t0}
    elapsed = round(time.time() - t0, 1)
    log_text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    m = re.search(r"RESULT n_materialized=\s*(\d+)\s+n_distinct=\s*(\d+)\s+predicted=\s*(\d+)", log_text)
    if not m:
        return {"error": "no RESULT",
                "log_tail": log_text[-2000:],
                "gap_rc": proc.returncode,
                "gap_stderr_tail": proc.stderr[-1500:] if proc.stderr else "",
                "gap_stdout_tail": proc.stdout[-1500:] if proc.stdout else "",
                "elapsed_s": elapsed}
    out = {
        "combo": target_str,
        "d": d, "t": t, "m_blocks": m_blocks,
        "src_n": src_n,
        "n_materialized": int(m.group(1)),
        "n_distinct": int(m.group(2)),
        "predicted": int(m.group(3)),
        "elapsed_s": elapsed,
    }
    if emit_generators and gen_path:
        out["generators_file"] = str(gen_path)
    if output_path is not None and gen_path is not None and gen_path.exists():
        raw_lines = gen_path.read_text(encoding="utf-8").splitlines()
        elapsed_ms = int(elapsed * 1000)
        n_written = _write_legacy_format(Path(output_path), target_combo, raw_lines,
                                          out["predicted"], elapsed_ms)
        if n_written != out["predicted"]:
            out["warning_count_mismatch"] = (
                f"wrote {n_written} generator lines but predicted={out['predicted']}")
        out["output_path"] = str(output_path)
    (work / "result.json").write_text(json.dumps(out, indent=2))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", required=True)
    ap.add_argument("--target-n", type=int, default=18)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--emit-generators", action="store_true")
    ap.add_argument("--output-path",
                    help="write legacy-format combo file here (implies --emit-generators)")
    args = ap.parse_args()
    print(json.dumps(predict_wreath(args.combo, args.target_n, args.timeout,
                                     emit_generators=args.emit_generators,
                                     output_path=args.output_path), indent=2))


if __name__ == "__main__":
    main()
