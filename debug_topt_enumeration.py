"""debug_topt_enumeration.py — compare _EnumerateNormalsForQGroups (TIERED-OPT)
vs trad NormalSubgroups for LEFT subgroups in [4,2]/[2,1]_[4,2].g paired with
RIGHT TG(4,3) = D_8.

Goal: find why topt produces +20 over v2 in [4,4,2]/[2,1]_[4,2]_[4,3].
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "debug_topt_enumeration.log"
if LOG.exists():
    LOG.unlink()

GAP_SCRIPT = f'''
LogTo("{str(LOG).replace(chr(92), "/")}");

# LEFT subgroups from [4,2]/[2,1]_[4,2].g
L1 := Group([(1,4)(2,3),(1,2)(3,4),(5,6)]);
L2 := Group([(1,4)(2,3),(1,2)(3,4)(5,6)]);

# RIGHT = TG(4,3) = D_8 on 1-4
R := TransitiveGroup(4, 3);

Print("\\n=== LEFT_1 = V_4 x C_2 in S_6 ===\\n");
Print("|L1| = ", Size(L1), "\\n");

# Trad: all normal subgroups
N_L1 := Filtered(NormalSubgroups(L1), K -> K <> L1);
Print("Trad: ", Length(N_L1), " normal subgroups (K<>H)\\n");
for K in N_L1 do
    Print("  |K|=", Size(K), " quot=", Size(L1)/Size(K), " IdGroup=",
          IdGroup(L1/K), "\\n");
od;

# Topt: enumerate by Q-iso class
SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

# RequiredQGroups(MR=4) — quotients of TG(4,*)
result := [];
seen := Set([]);
for t in [1..NrTransitiveGroups(4)] do
    T := TransitiveGroup(4, t);
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
Q_GROUPS := result;
Print("\\nRequiredQGroups(4): ", Length(Q_GROUPS), " types\\n");
for Q in Q_GROUPS do
    Print("  |Q|=", Size(Q), " IdGroup=", IdGroup(Q), "\\n");
od;

# Topt enumeration
_EnumerateNormalsForQGroups := function(H, q_groups)
    local q_size_H, DH, abel_hom, A, result_K, Q, sz, p, max_subs, epi;
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
    result_K := [];
    for Q in q_groups do
        sz := Size(Q);
        if q_size_H mod sz <> 0 then continue; fi;
        if IsPrimeInt(sz) then
            if abel_hom = fail then continue; fi;
            if Size(A) mod sz <> 0 then continue; fi;
            p := sz;
            max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = p);
            Append(result_K, List(max_subs, K -> PreImage(abel_hom, K)));
        elif IsAbelian(Q) then
            if abel_hom = fail then continue; fi;
            for epi in GQuotients(A, Q) do
                Add(result_K, PreImage(abel_hom, Kernel(epi)));
            od;
        else
            Append(result_K, Set(List(GQuotients(H, Q), Kernel)));
        fi;
    od;
    return Set(result_K);
end;

N_L1_topt := _EnumerateNormalsForQGroups(L1, Q_GROUPS);
Print("\\nTopt _EnumerateNormalsForQGroups: ", Length(N_L1_topt), " K's\\n");
for K in N_L1_topt do
    Print("  |K|=", Size(K), " quot=", Size(L1)/Size(K), " IdGroup=",
          IdGroup(L1/K), "\\n");
od;

# Set comparison
Print("\\nTrad K-set as sorted IdGroup of quotient:\\n  ",
      SortedList(List(N_L1, K -> IdGroup(L1/K))), "\\n");
Print("Topt K-set as sorted IdGroup of quotient:\\n  ",
      SortedList(List(N_L1_topt, K -> IdGroup(L1/K))), "\\n");

# Same for L2
Print("\\n=== LEFT_2 = twisted V_4 in S_6 ===\\n");
Print("|L2| = ", Size(L2), " IdGroup=", IdGroup(L2), "\\n");
N_L2 := Filtered(NormalSubgroups(L2), K -> K <> L2);
Print("Trad: ", Length(N_L2), " normal subgroups\\n");
N_L2_topt := _EnumerateNormalsForQGroups(L2, Q_GROUPS);
Print("Topt: ", Length(N_L2_topt), " K's\\n");
Print("Trad K-set as sorted IdGroup of quotient: ",
      SortedList(List(N_L2, K -> IdGroup(L2/K))), "\\n");
Print("Topt K-set as sorted IdGroup of quotient: ",
      SortedList(List(N_L2_topt, K -> IdGroup(L2/K))), "\\n");

# Now compute orbit decomposition via Normalizer in W_ML = S_4 x S_2
W := DirectProduct(SymmetricGroup(4), SymmetricGroup(2));
N_L1_W := Normalizer(W, L1);
N_L2_W := Normalizer(W, L2);
Print("\\n|N_W(L1)|=", Size(N_L1_W), "\\n");
Print("|N_W(L2)|=", Size(N_L2_W), "\\n");

# Orbits
Print("\\n--- L1 orbit decomposition (trad K's) ---\\n");
ConjAction := function(K, g) return K^g; end;
orbs := Orbits(N_L1_W, N_L1, ConjAction);
Print("Trad: ", Length(orbs), " orbits\\n");
for orb in orbs do
    Print("  size=", Length(orb), " quot=", IdGroup(L1/orb[1]), "\\n");
od;
orbs_topt := Orbits(N_L1_W, N_L1_topt, ConjAction);
Print("Topt: ", Length(orbs_topt), " orbits\\n");
for orb in orbs_topt do
    Print("  size=", Length(orb), " quot=", IdGroup(L1/orb[1]), "\\n");
od;

Print("\\n--- L2 orbit decomposition ---\\n");
orbs := Orbits(N_L2_W, N_L2, ConjAction);
Print("Trad: ", Length(orbs), " orbits\\n");
for orb in orbs do
    Print("  size=", Length(orb), " quot=", IdGroup(L2/orb[1]), "\\n");
od;
orbs_topt := Orbits(N_L2_W, N_L2_topt, ConjAction);
Print("Topt: ", Length(orbs_topt), " orbits\\n");
for orb in orbs_topt do
    Print("  size=", Length(orb), " quot=", IdGroup(L2/orb[1]), "\\n");
od;

LogTo();
QUIT;
'''

(ROOT / "debug_topt_enumeration.g").write_text(GAP_SCRIPT, encoding="utf-8")
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_topt_enumeration.g"
env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cyg}"'],
    env=env, capture_output=True)
print(LOG.read_text(encoding="utf-8") if LOG.exists() else "(no log)")
