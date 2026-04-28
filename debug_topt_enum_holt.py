"""debug_topt_enum_holt.py — for the [2,1]_[2,1]_[3,2]_[3,2] holt_split combo,
compare TIERED-OPT _EnumerateNormalsForQGroups vs trad NormalSubgroups
on each LEFT and RIGHT subgroup.

LEFT source: parallel_sn_topt/4/[2,2]/[2,1]_[2,1].g — 2 subgroups
RIGHT source: parallel_sn_topt/6/[3,3]/[3,2]_[3,2].g — 3 subgroups

For each L_i × R_j, list normal-subgroup K's enumerated by each method.
Look for K's missing in topt but present in trad.
"""
import os, subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "debug_topt_enum_holt.log"
if LOG.exists(): LOG.unlink()

GAP_SCRIPT = f'''
LogTo("{str(LOG).replace(chr(92), "/")}");

# LEFT subgroups (from parallel_sn_topt/4/[2,2]/[2,1]_[2,1].g)
LEFT_SUBS := [
    Group([(1,2)(3,4)]),
    Group([(1,2),(3,4)])
];
# RIGHT subgroups (from parallel_sn_topt/6/[3,3]/[3,2]_[3,2].g)
RIGHT_SUBS := [
    Group([(1,2,3),(1,2),(4,5,6),(4,5)]),
    Group([(1,2,3),(1,2)(4,5),(4,6,5)]),
    Group([(1,2,3)(4,5,6),(1,2)(4,5)])
];

ML := 4; MR := 6;

SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

# RequiredQGroups (clone of topt's logic)
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

# Topt enumeration (from predict_2factor_topt.py)
EnumNormalsTopt := function(H, q_groups)
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

# Q_GROUPS for LEFT (depends on M_R=6) and RIGHT (depends on M_L=4)
LEFT_Q_GROUPS := RequiredQGroups(6);
RIGHT_Q_GROUPS := RequiredQGroups(4);

Print("LEFT_Q_GROUPS: ", Length(LEFT_Q_GROUPS), " types\\n");
for Q in LEFT_Q_GROUPS do Print("  |Q|=", Size(Q), " ", IdGroup(Q), "\\n"); od;
Print("\\nRIGHT_Q_GROUPS: ", Length(RIGHT_Q_GROUPS), " types\\n");
for Q in RIGHT_Q_GROUPS do Print("  |Q|=", Size(Q), " ", IdGroup(Q), "\\n"); od;

ReportFor := function(label, H, q_groups)
    local trad, topt, trad_quots, topt_quots, missing;
    Print("\\n=== ", label, " |H|=", Size(H), " ===\\n");
    trad := Filtered(NormalSubgroups(H), K -> K <> H);
    topt := EnumNormalsTopt(H, q_groups);
    trad_quots := SortedList(List(trad, K -> [Size(H)/Size(K), IdGroup(H/K)]));
    topt_quots := SortedList(List(topt, K -> [Size(H)/Size(K), IdGroup(H/K)]));
    Print("Trad: ", Length(trad), " K's, quots=", trad_quots, "\\n");
    Print("Topt: ", Length(topt), " K's, quots=", topt_quots, "\\n");
    # Are there any K's in trad not in topt?  (Not just iso-class, actual equality)
    missing := Filtered(trad, K -> not (K in topt));
    if Length(missing) > 0 then
        Print(">> ", Length(missing), " K's in trad missing from topt!\\n");
        for K in missing do
            Print("   missing K: |K|=", Size(K), " quot=", IdGroup(H/K),
                  " gens=", GeneratorsOfGroup(K), "\\n");
        od;
    fi;
    return rec(trad := trad, topt := topt);
end;

for li in [1..Length(LEFT_SUBS)] do
    ReportFor(Concatenation("LEFT[", String(li), "]"), LEFT_SUBS[li], LEFT_Q_GROUPS);
od;

for ri in [1..Length(RIGHT_SUBS)] do
    ReportFor(Concatenation("RIGHT[", String(ri), "]"), RIGHT_SUBS[ri], RIGHT_Q_GROUPS);
od;

LogTo();
QUIT;
'''

(ROOT / "debug_topt_enum_holt.g").write_text(GAP_SCRIPT, encoding="utf-8")
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_topt_enum_holt.g"
env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cyg}"'],
    env=env, capture_output=True)
print(LOG.read_text(encoding="utf-8") if LOG.exists() else "(no log)")
print("---STDERR---")
print(proc.stderr.decode(errors="ignore")[:2000])
