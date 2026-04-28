"""debug_holt_split_3322.py — directly compare TIERED-OPT vs trad on
[3,3,2,2]/[2,1]_[2,1]_[3,2]_[3,2] holt_split combo.

Run two enumerations:
  variant A: q_groups = RequiredQGroups(6) for LEFT
  variant B: q_groups = fail for LEFT

Compare per-(L_idx, R_idx) Goursat fp counts.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "debug_holt_split_3322.log"
if LOG.exists():
    LOG.unlink()

GAP_SCRIPT = f'''
LogTo("{str(LOG).replace(chr(92), "/")}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");

# LEFT subgroups (from parallel_sn_v2/4/[2,2]/[2,1]_[2,1].g)
LEFT_SUBS := [
    Group([(1,2)(3,4)]),
    Group([(1,2),(3,4)])
];

# RIGHT subgroups (from parallel_sn_v2/6/[3,3]/[3,2]_[3,2].g)
RIGHT_SUBS := [
    Group([(1,2,3),(1,2),(4,5,6),(4,5)]),
    Group([(1,2,3),(1,2)(4,5),(4,6,5)]),
    Group([(1,2,3)(4,5,6),(1,2)(4,5)])
];

ML := 4;
MR := 6;

# Block-wreath ambients
W_ML := WreathProduct(SymmetricGroup(2), SymmetricGroup(2));   # S_2 wr S_2
W_MR := WreathProduct(SymmetricGroup(3), SymmetricGroup(2));   # S_3 wr S_2
S_ML := SymmetricGroup(ML);
S_MR := SymmetricGroup(MR);

SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

ConjAction := function(K, g) return K^g; end;

# Build q_groups filter (RequiredQGroups(6))
RequiredQGroups := function(M_R)
    local result, seen, t, T, K, Q, qid;
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

QG := RequiredQGroups(6);
Print("RequiredQGroups(6): ", Length(QG), " types\\n");
for Q in QG do Print("  |Q|=", Size(Q), " IdGroup=", IdGroup(Q), "\\n"); od;

# Two enumeration variants
EnumNormals_topt := function(H, q_groups)
    local q_size_H, DH, abel_hom, A, result, Q, sz, p, max_subs, epi;
    if q_groups = fail then
        return Filtered(NormalSubgroups(H), K -> K <> H);
    fi;
    if Length(q_groups) = 0 then return []; fi;
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

# Compare K-sets for each LEFT subgroup
for li in [1..Length(LEFT_SUBS)] do
    L := LEFT_SUBS[li];
    Print("\\n=== LEFT[", li, "] |L|=", Size(L), " ===\\n");
    K_trad := Filtered(NormalSubgroups(L), K -> K <> L);
    K_topt := EnumNormals_topt(L, QG);
    Print("Trad K-count=", Length(K_trad),
          " quots=", SortedList(List(K_trad, K -> IdGroup(L/K))), "\\n");
    Print("Topt K-count=", Length(K_topt),
          " quots=", SortedList(List(K_topt, K -> IdGroup(L/K))), "\\n");

    N_L := Normalizer(W_ML, L);
    Print("|N_W(L)|=", Size(N_L), "\\n");
    orbs_trad := Orbits(N_L, K_trad, ConjAction);
    orbs_topt := Orbits(N_L, K_topt, ConjAction);
    Print("Trad orbits: ", Length(orbs_trad),
          " quot-sizes: ", List(orbs_trad, o -> Size(L)/Size(o[1])), "\\n");
    Print("Topt orbits: ", Length(orbs_topt),
          " quot-sizes: ", List(orbs_topt, o -> Size(L)/Size(o[1])), "\\n");
od;

# Compare K-sets for each RIGHT subgroup (always uses fail in topt)
for ri in [1..Length(RIGHT_SUBS)] do
    R := RIGHT_SUBS[ri];
    Print("\\n=== RIGHT[", ri, "] |R|=", Size(R), " ===\\n");
    K_trad := Filtered(NormalSubgroups(R), K -> K <> R);
    Print("Trad K-count=", Length(K_trad), "\\n");
    Print("Quot iso-classes: ", SortedList(List(K_trad, K -> IdGroup(R/K))), "\\n");

    N_R := Normalizer(W_MR, R);
    Print("|N_W(R)|=", Size(N_R), "\\n");
    orbs := Orbits(N_R, K_trad, ConjAction);
    Print("Orbits: ", Length(orbs),
          " quot-sizes: ", List(orbs, o -> Size(R)/Size(o[1])), "\\n");
od;

LogTo();
QUIT;
'''

(ROOT / "debug_holt_split_3322.g").write_text(GAP_SCRIPT, encoding="utf-8")
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_holt_split_3322.g"
env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cyg}"'],
    env=env, capture_output=True)
print(LOG.read_text(encoding="utf-8") if LOG.exists() else "(no log)")
