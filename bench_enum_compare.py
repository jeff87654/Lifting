"""bench_enum_compare.py — benchmark OLD (GQuotients) vs NEW (NS+filter) for
non-abelian Q enumeration in _EnumerateNormalsForQGroups.

Two modes:
  --case mr3    LEFT=[4,3]_[4,3]_[4,3]_[4,3]   (n=16, 12525 H's)  q_groups=[C_2,C_3,S_3]
  --case mr4    LEFT=[2,1]_[4,3]_[4,3]_[4,3]   (n=14, 2777  H's)  q_groups=[C_2,C_3,C_4,V_4,D_4,A_4,S_3,S_4]

For each mode, samples the first N H's (default 8) of varying sizes,
times both methods on each H, and verifies the K-sets are equal.
"""
import argparse, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).parent
LIFTING_WS = ROOT / "lifting.ws"
LIFTING_WS_CYG = "/cygdrive/c/Users/jeffr/Downloads/Lifting/lifting.ws"

CASES = {
    "mr3": {
        "src":  "parallel_sn_topt/16/[4,4,4,4]/[4,3]_[4,3]_[4,3]_[4,3].g",
        "m_r":  3,
        "label": "[4,3]^4 with M_R=3 (C_2,C_3,S_3)",
    },
    "mr4": {
        "src":  "parallel_sn_topt/14/[4,4,4,2]/[2,1]_[4,3]_[4,3]_[4,3].g",
        "m_r":  4,
        "label": "[2,1]_[4,3]^3 with M_R=4 (8 Q-types incl. D_4,A_4,S_3,S_4)",
    },
}

GAP_DRIVER = r"""
# bench script
LogTo("__LOG__");
Print("=== bench __LABEL__ ===\n");
m_R := __MR__;

SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

# Build q_groups for M_R
build_q_groups := function(M_R)
    local result, seen, t, T, K, Q, qid;
    result := []; seen := Set([]);
    if M_R = 0 then return result; fi;
    for t in [1..NrTransitiveGroups(M_R)] do
        T := TransitiveGroup(M_R, t);
        for K in NormalSubgroups(T) do
            if Size(K) = Size(T) then continue; fi;
            Q := T / K;
            qid := SafeId(Q);
            if not (qid in seen) then AddSet(seen, qid); Add(result, Q); fi;
        od;
    od;
    return result;
end;

Q_GROUPS := build_q_groups(m_R);
Print("Q_GROUPS: ", Length(Q_GROUPS), " types: ");
for q in Q_GROUPS do Print(StructureDescription(q), "(", Size(q), ") "); od;
Print("\n\n");

# OLD path: per-Q smart routing (current code in predict_2factor_topt.py)
EnumOLD := function(H, q_groups)
    local q_size_H, DH, abel_hom, A, result, Q, sz, p, max_subs, epi;
    if q_groups = fail then return Filtered(NormalSubgroups(H), K -> K <> H); fi;
    if Length(q_groups) = 0 then return []; fi;
    q_size_H := Size(H);
    DH := DerivedSubgroup(H);
    if Size(DH) = q_size_H then abel_hom := fail; A := fail;
    else abel_hom := NaturalHomomorphismByNormalSubgroup(H, DH); A := Range(abel_hom); fi;
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

# NEW path: prime/abelian via routing, non-abelian via NS + index filter
EnumNEW := function(H, q_groups)
    local q_size_H, DH, abel_hom, A, result, Q, sz, p, max_subs, epi,
          prime_qs, abelian_qs, nonabelian_qs, target_indices, target_qids,
          normals, K, i_K;
    if q_groups = fail then return Filtered(NormalSubgroups(H), K -> K <> H); fi;
    if Length(q_groups) = 0 then return []; fi;
    q_size_H := Size(H);
    prime_qs := Filtered(q_groups, q -> IsPrimeInt(Size(q)));
    abelian_qs := Filtered(q_groups, q -> IsAbelian(q) and not IsPrimeInt(Size(q)));
    nonabelian_qs := Filtered(q_groups, q -> not IsAbelian(q));
    DH := DerivedSubgroup(H);
    if Size(DH) = q_size_H then abel_hom := fail; A := fail;
    else abel_hom := NaturalHomomorphismByNormalSubgroup(H, DH); A := Range(abel_hom); fi;
    result := [];
    for Q in prime_qs do
        sz := Size(Q);
        if q_size_H mod sz <> 0 then continue; fi;
        if abel_hom = fail then continue; fi;
        if Size(A) mod sz <> 0 then continue; fi;
        p := sz;
        max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = p);
        Append(result, List(max_subs, K -> PreImage(abel_hom, K)));
    od;
    for Q in abelian_qs do
        sz := Size(Q);
        if q_size_H mod sz <> 0 then continue; fi;
        if abel_hom = fail then continue; fi;
        for epi in GQuotients(A, Q) do
            Add(result, PreImage(abel_hom, Kernel(epi)));
        od;
    od;
    nonabelian_qs := Filtered(nonabelian_qs, q -> q_size_H mod Size(q) = 0);
    if Length(nonabelian_qs) > 0 then
        target_indices := Set(List(nonabelian_qs, Size));
        target_qids := Set(List(nonabelian_qs, SafeId));
        normals := Filtered(NormalSubgroups(H),
                            K -> K <> H and (Size(H)/Size(K)) in target_indices);
        for K in normals do
            if SafeId(H/K) in target_qids then Add(result, K); fi;
        od;
    fi;
    return Set(result);
end;

# Read source: each line after headers is a generator list
src_path := "__SRC__";
all_lines := SplitString(StringFile(src_path), "\n");
gen_lines := Filtered(all_lines, l -> Length(l) > 0 and l[1] <> '#');
Print("Source has ", Length(gen_lines), " H subgroups; sampling __NSAMPLE__\n\n");

# Sample H's: largest first, then a few smaller ones
n_total := Length(gen_lines);
sample_idx := [1, 2, 3];
if n_total > 50  then Add(sample_idx, 50);  fi;
if n_total > 100 then Add(sample_idx, 100); fi;
if n_total > 500 then Add(sample_idx, 500); fi;
if n_total > 1500 then Add(sample_idx, 1500); fi;
if n_total > 5000 then Add(sample_idx, 5000); fi;

pad := function(x, w) local s; s := String(x); while Length(s) < w do s := Concatenation(" ", s); od; return s; end;
Print(pad("idx",6), pad("|H|",8), pad("OLD_ms",10), pad("NEW_ms",10), pad("K_n",6), pad("match",7), "\n");

m_str := "";
for idx in sample_idx do
    H_gens := EvalString(gen_lines[idx]);
    H := Group(H_gens);

    t0 := Runtime();
    K_old := EnumOLD(H, Q_GROUPS);
    t_old := Runtime() - t0;

    t0 := Runtime();
    K_new := EnumNEW(H, Q_GROUPS);
    t_new := Runtime() - t0;

    match := Length(K_old) = Length(K_new) and Set(K_old) = Set(K_new);
    if match then m_str := "OK"; else m_str := "DIFF"; fi;
    Print(pad(idx,6), pad(Size(H),8), pad(t_old,10), pad(t_new,10),
          pad(Length(K_old),6), pad(m_str,7), "\n");
od;

Print("\n=== done ===\n");
LogTo();
QUIT;
"""

def run_case(case):
    cfg = CASES[case]
    sandbox = ROOT / f"bench_enum_{case}"
    sandbox.mkdir(exist_ok=True)
    log_path = sandbox / "bench.log"
    if log_path.exists(): log_path.unlink()
    g_path = sandbox / "bench.g"

    g = (GAP_DRIVER
         .replace("__LOG__", str(log_path).replace("\\", "/"))
         .replace("__LABEL__", cfg["label"])
         .replace("__SRC__", str(ROOT / cfg["src"]).replace("\\", "/"))
         .replace("__MR__", str(cfg["m_r"]))
         .replace("__NSAMPLE__", "9 H's of varying sizes"))
    g_path.write_text(g, encoding="utf-8")

    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    g_cyg = "/cygdrive/c/" + str(g_path)[3:].replace("\\", "/")
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"

    cmd = (f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
           f'./gap.exe -q -o 0 -L "{LIFTING_WS_CYG}" "{g_cyg}"')
    print(f"[{case}] starting...")
    t0 = time.time()
    proc = subprocess.run([bash_exe, "--login", "-c", cmd],
                          env=env, capture_output=True, text=True,
                          timeout=12*3600)
    elapsed = time.time() - t0
    print(f"[{case}] done in {elapsed:.0f}s")
    if log_path.exists():
        print(f"--- {case} log ---")
        print(log_path.read_text())
    if proc.stderr:
        print(f"--- {case} stderr ---")
        print(proc.stderr[-800:])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=list(CASES.keys()), required=True)
    args = ap.parse_args()
    run_case(args.case)
