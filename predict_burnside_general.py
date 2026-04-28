#!/usr/bin/env python3
"""
predict_burnside_general.py — Burnside over S_m for single-cluster combos
[d,t]^m with m >= 2.  Works for any T = TG(d,t).

Strategy: brute-force enumerate subgroups F <= T^m (acting block-wise on
m*d points) via ConjugacyClassesSubgroups, filter for "surjective on each
block-projection", then for each cycle type lambda apply Burnside:
  |X / S_m| = (1/m!) Sum_lambda  (m!/z_lambda) * |Fix(sigma_lambda)|
where |Fix(sigma_lambda)| = # F's with sigma_lambda-conjugation fixing F.

We compute |Fix(sigma_lambda)| by counting filtered F's whose permutation
action by sigma_lambda preserves F (i.e., F^sigma = F as a set).  Modulo
(N_T)^m action, using RA in (N_T)^m or similar.
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

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
TMP = ROOT / "predict_species_tmp" / "_burnside_general"
TMP.mkdir(parents=True, exist_ok=True)

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


GAP_BURNSIDE = r"""
LogTo("__LOG__");

DD       := __D__;
TID      := __T_ID__;
M_BLOCKS := __M_BLOCKS__;
N_TARGET := DD * M_BLOCKS;

Print("burnside-bf m=", M_BLOCKS, " d=", DD, " t=", TID, " n=", N_TARGET, "\n");

T_orig    := TransitiveGroup(DD, TID);
N_T_orig  := Normalizer(SymmetricGroup(DD), T_orig);

# Build T^m on m*d points (m disjoint blocks of d, each acting as T).
block_shift := function(i) return MappingPermListList([1..DD], [(i-1)*DD+1..i*DD]); end;
T_blocks    := List([1..M_BLOCKS], i -> T_orig^block_shift(i));
N_T_blocks  := List([1..M_BLOCKS], i -> N_T_orig^block_shift(i));
T_m         := Group(Concatenation(List(T_blocks, GeneratorsOfGroup)));
N_T_m       := Group(Concatenation(List(N_T_blocks, GeneratorsOfGroup)));
S_n         := SymmetricGroup(N_TARGET);

Print("|T_m|=", Size(T_m), "  |N_T_m|=", Size(N_T_m), "\n");

t0 := Runtime();
Print("Computing CCS(T_m)...\n");
ccs := ConjugacyClassesSubgroups(T_m);
ccs_elapsed := Runtime() - t0;
Print("|CCS(T_m)|=", Length(ccs), " (", ccs_elapsed, "ms)\n");

# Filter: F has each block-projection = T_blocks[i].
block_pts_list := List([1..M_BLOCKS], i -> Set([(i-1)*DD+1..i*DD]));
valid_F_list := [];
for cl in ccs do
    F := Representative(cl);
    ok := true;
    for i in [1..M_BLOCKS] do
        # Compute block-projection of F to block i.
        # F's restriction-to-block-i = F's image in S_d via "act on block i's points".
        # Since T_m's elements all preserve blocks, this is just RestrictedPerm.
        gens_block := List(GeneratorsOfGroup(F),
            g -> RestrictedPerm(g, [(i-1)*DD+1..i*DD]));
        block_proj := Group(gens_block, ());
        if Size(block_proj) <> Size(T_orig)
           or not IsTransitive(block_proj, [(i-1)*DD+1..i*DD]) then
            ok := false; break;
        fi;
    od;
    if ok then Add(valid_F_list, F); fi;
od;
Print("valid F's after filter: ", Length(valid_F_list), "\n");

# Re-bucket up to N_T wr S_m action.  Build the ambient permutation group on
# n points: N_T on each block + S_m permuting blocks.
GenBlockPerm := function(sigma)
    # sigma is a permutation in S_M_BLOCKS.  Build the corresponding
    # permutation in S_n that permutes blocks accordingly.
    local images, k, bi, bj, bnew;
    images := [];
    for k in [1..N_TARGET] do
        bi := QuoInt(k-1, DD);
        bj := (k-1) mod DD;
        bnew := (bi+1)^sigma - 1;
        Add(images, bnew*DD + bj + 1);
    od;
    return PermList(images);
end;

block_perm_gens := List(GeneratorsOfGroup(SymmetricGroup(M_BLOCKS)), GenBlockPerm);
W_full := Group(Concatenation(GeneratorsOfGroup(N_T_m), block_perm_gens));
Print("|W_full|=", Size(W_full), "\n");

# RA-dedup in W_full to get the "S_m-orbit count".
fp_fingerprint := function(G)
    local sz, abi, ds;
    sz := Size(G);
    abi := AbelianInvariants(G);
    ds := List(DerivedSeries(G), Size);
    if IdGroupsAvailable(sz) then
        return [sz, IdGroup(G), abi, ds];
    fi;
    return [sz, abi, ds];
end;

n := Length(valid_F_list);
fps := List(valid_F_list, fp_fingerprint);
parent := [1..n];
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

bucket_keys := [];
bucket_lists := [];
for i in [1..n] do
    pos := Position(bucket_keys, fps[i]);
    if pos = fail then
        Add(bucket_keys, fps[i]);
        Add(bucket_lists, [i]);
    else
        Add(bucket_lists[pos], i);
    fi;
od;
Print("buckets=", Length(bucket_lists),
      " (max=", Maximum(List(bucket_lists, Length)), ")\n");

ra_calls := 0;
ra_succ := 0;
for b in [1..Length(bucket_lists)] do
    bk := bucket_lists[b];
    for i in [1..Length(bk)-1] do
        for j in [i+1..Length(bk)] do
            if UF_Find(bk[i]) = UF_Find(bk[j]) then continue; fi;
            ra_calls := ra_calls + 1;
            if RepresentativeAction(W_full, valid_F_list[bk[i]], valid_F_list[bk[j]]) <> fail then
                UF_Union(bk[i], bk[j]);
                ra_succ := ra_succ + 1;
            fi;
        od;
    od;
od;
classes := Set([1..n], i -> UF_Find(i));
Print("RA dedup: ra_calls=", ra_calls, " succ=", ra_succ,
      "  distinct classes=", Length(classes), "\n");

Print("BURNSIDE_TOTAL: ", Length(classes), "\n");
LogTo();
QUIT;
"""


def predict_burnside(combo_str: str, target_n=18, timeout=3600):
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

    target_str = "_".join(f"[{dd},{tt}]" for dd, tt in target_combo)
    work = TMP / target_str
    work.mkdir(parents=True, exist_ok=True)
    log = work / "burnside.log"
    if log.exists(): log.unlink()
    run_g = work / "run.g"
    run_g.write_text(
        GAP_BURNSIDE
        .replace("__LOG__", to_cyg(log))
        .replace("__D__", str(d))
        .replace("__T_ID__", str(t))
        .replace("__M_BLOCKS__", str(m_blocks)),
        encoding="utf-8"
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
    m = re.search(r"BURNSIDE_TOTAL:\s*(\d+)", log_text)
    if not m:
        return {"error": "no BURNSIDE_TOTAL", "log_tail": log_text[-2000:],
                "elapsed_s": elapsed}
    out = {
        "combo": target_str,
        "d": d, "t": t, "m_blocks": m_blocks,
        "predicted": int(m.group(1)),
        "elapsed_s": elapsed,
    }
    (work / "result.json").write_text(json.dumps(out, indent=2))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", required=True)
    ap.add_argument("--target-n", type=int, default=18)
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()
    print(json.dumps(predict_burnside(args.combo, args.target_n, args.timeout), indent=2))


if __name__ == "__main__":
    main()
