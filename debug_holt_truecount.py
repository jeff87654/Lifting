"""debug_holt_truecount.py — materialize all v2+topt candidates for
[3,3,2,2]/[2,1]_[2,1]_[3,2]_[3,2] and compute the true N-orbit count.

v2: 20 deduped (embedding [3,3,2,2] with 3-blocks first, 2-blocks last)
topt: 18 deduped (embedding [2,2,3,3] with 2-blocks first, 3-blocks last)

To compare apples-to-apples, conjugate topt subgroups by the relabeling perm
that maps [2,2,3,3] -> [3,3,2,2] (i.e., points 1-4 <-> 5-10 swap).
Then compute orbits under N = Normalizer(S_10, partition stabilizer for [3,3,2,2]).
"""
import os, subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "debug_holt_truecount.log"
if LOG.exists(): LOG.unlink()

# v2 generators (DESCENDING [3,3,2,2] embedding)
V2_LINES = [
    "[(2,3)(5,6)(7,8)(9,10),(1,2,3)(4,5,6)]",
    "[(2,3)(5,6)(9,10),(1,2,3)(4,5,6),(7,8)]",
    "[(2,3)(5,6),(1,2,3)(4,5,6),(7,8)(9,10)]",
    "[(2,3)(5,6)(9,10),(1,2,3)(4,5,6),(7,8)(9,10)]",
    "[(2,3)(5,6),(1,2,3)(4,5,6),(7,8),(9,10)]",
    "[(4,5,6),(1,2,3),(2,3)(5,6)(7,8)(9,10)]",
    "[(4,5,6),(1,2,3),(2,3)(5,6)(9,10),(7,8)]",
    "[(4,5,6),(1,2,3),(2,3)(5,6),(7,8)(9,10)]",
    "[(4,5,6),(1,2,3),(2,3)(5,6)(9,10),(7,8)(9,10)]",
    "[(4,5,6),(1,2,3),(2,3)(5,6),(7,8),(9,10)]",
    "[(4,5,6),(1,2,3),(5,6)(7,8)(9,10),(2,3)]",
    "[(4,5,6),(1,2,3),(5,6)(9,10),(2,3)(7,8)]",
    "[(4,5,6),(1,2,3),(5,6)(7,8)(9,10),(2,3)(7,8)]",
    "[(4,5,6),(1,2,3),(5,6)(7,8)(9,10),(2,3)(7,8)(9,10)]",
    "[(4,5,6),(1,2,3),(5,6),(2,3),(7,8)(9,10)]",
    "[(4,5,6),(1,2,3),(5,6)(9,10),(2,3),(7,8)]",
    "[(4,5,6),(1,2,3),(5,6)(9,10),(2,3)(9,10),(7,8)]",
    "[(4,5,6),(1,2,3),(5,6)(9,10),(2,3),(7,8)(9,10)]",
    "[(4,5,6),(1,2,3),(5,6)(9,10),(2,3)(9,10),(7,8)(9,10)]",
    "[(4,5,6),(1,2,3),(5,6),(2,3),(7,8),(9,10)]",
]

# topt generators (ASCENDING [2,2,3,3] embedding) - pts 1-4 are C_2's, 5-10 are S_3's
TOPT_LINES = [
    "[(1,2)(3,4),(5,6,7),(5,6),(8,9,10),(8,9)]",
    "[(1,2)(3,4)(5,6),(5,7,6),(8,10,9),(8,9)]",
    "[(1,2)(3,4)(8,9),(5,7,6),(5,6)(8,9),(8,10,9)]",
    "[(1,2)(3,4),(5,6,7),(5,6)(8,9),(8,10,9)]",
    "[(1,2)(3,4)(5,6)(8,9),(5,7,6),(8,9,10)]",
    "[(1,2)(3,4),(5,6,7)(8,9,10),(5,6)(8,9)]",
    "[(1,2)(3,4)(5,6)(8,9),(5,7,6)(8,10,9)]",
    "[(1,2),(3,4),(5,6,7),(5,6),(8,9,10),(8,9)]",
    "[(1,2)(5,6),(3,4),(5,7,6),(8,10,9),(8,9)]",
    "[(1,2)(8,9),(3,4),(5,7,6),(5,6)(8,9),(8,10,9)]",
    "[(1,2)(5,6),(3,4)(5,6),(5,7,6),(8,10,9),(8,9)]",
    "[(1,2)(8,9),(3,4)(8,9),(5,7,6),(5,6)(8,9),(8,10,9)]",
    "[(1,2),(3,4),(5,6,7),(5,6)(8,9),(8,10,9)]",
    "[(1,2)(5,6)(8,9),(3,4),(5,7,6),(8,9,10)]",
    "[(1,2)(5,6)(8,9),(3,4)(5,6)(8,9),(5,7,6),(8,9,10)]",
    "[(1,2),(3,4),(5,6,7)(8,9,10),(5,6)(8,9)]",
    "[(1,2)(5,6)(8,9),(3,4),(5,7,6)(8,10,9)]",
    "[(1,2)(5,6)(8,9),(3,4)(5,6)(8,9),(5,7,6)(8,10,9)]",
]

GAP_SCRIPT = f'''
LogTo("{str(LOG).replace(chr(92), "/")}");

V2_GENS := [{",".join(V2_LINES)}];
TOPT_GENS := [{",".join(TOPT_LINES)}];

# Relabel topt subgroups so they live in the same [3,3,2,2] embedding as v2:
# topt: 2-blocks on (1,2) (3,4); 3-blocks on (5,6,7) (8,9,10)
# v2:   3-blocks on (1,2,3) (4,5,6); 2-blocks on (7,8) (9,10)
# Map: 1->7, 2->8, 3->9, 4->10, 5->1, 6->2, 7->3, 8->4, 9->5, 10->6
# So we send [1..10] -> [7,8,9,10,1,2,3,4,5,6]
SHIFT := PermList([7,8,9,10,1,2,3,4,5,6]);

V2_GROUPS := List(V2_GENS, gens -> Group(gens));
TOPT_GROUPS := List(TOPT_GENS, gens -> Group(List(gens, g -> g^SHIFT)));

# Build N = stabilizer of partition [3,3,2,2] in S_10
# Blocks: {{1,2,3}}, {{4,5,6}}, {{7,8}}, {{9,10}}
S10 := SymmetricGroup(10);
# N preserves the block partition: S_3 on {{1,2,3}} and {{4,5,6}} (with swap),
# S_2 on {{7,8}} and {{9,10}} (with swap)
N_3blocks := WreathProduct(SymmetricGroup(3), SymmetricGroup(2));
N_2blocks := WreathProduct(SymmetricGroup(2), SymmetricGroup(2));
# Embed each into S_10 on appropriate points
shift_3 := MappingPermListList([1..6], [1..6]);   # identity, blocks on 1-6
shift_2 := MappingPermListList([1..4], [7..10]);  # 2-blocks on 7-10
N_3blocks_emb := Group(List(GeneratorsOfGroup(N_3blocks), g -> g^shift_3));
N_2blocks_emb := Group(List(GeneratorsOfGroup(N_2blocks), g -> g^shift_2));
N := Group(Concatenation(GeneratorsOfGroup(N_3blocks_emb),
                         GeneratorsOfGroup(N_2blocks_emb)));
Print("|N| = ", Size(N), "\\n");

# Verify all 20 v2 subgroups are in W_TARGET (the partition stabilizer)
Print("\\n=== v2 subgroups ===\\n");
for i in [1..Length(V2_GROUPS)] do
    if not IsSubset(N, V2_GROUPS[i]) then
        Print("v2[", i, "] NOT in N (sizes ", Size(V2_GROUPS[i]), ")\\n");
    fi;
od;
Print("\\n=== topt subgroups (after relabeling) ===\\n");
for i in [1..Length(TOPT_GROUPS)] do
    if not IsSubset(N, TOPT_GROUPS[i]) then
        Print("topt[", i, "] NOT in N (sizes ", Size(TOPT_GROUPS[i]), ")\\n");
    fi;
od;

# Compute N-orbits on combined list
ALL := Concatenation(V2_GROUPS, TOPT_GROUPS);
Print("\\nTotal: ", Length(ALL), " subgroups (20 v2 + 18 topt)\\n");

# Orbit by N-conjugation, using a canonical rep
ConjAction := function(G, n) return G^n; end;

orbs := [];
seen := List([1..Length(ALL)], x -> false);
for i in [1..Length(ALL)] do
    if seen[i] then continue; fi;
    orb := [i];
    seen[i] := true;
    for j in [i+1..Length(ALL)] do
        if seen[j] then continue; fi;
        if Size(ALL[i]) <> Size(ALL[j]) then continue; fi;
        # Check if conjugate under N
        rep := RepresentativeAction(N, ALL[i], ALL[j]);
        if rep <> fail then
            seen[j] := true;
            Add(orb, j);
        fi;
    od;
    Add(orbs, orb);
od;

Print("\\nN-orbits: ", Length(orbs), "\\n");
in_v2 := List(orbs, o -> Number(o, x -> x <= 20));
in_topt := List(orbs, o -> Number(o, x -> x > 20));
v2_unique := Filtered([1..Length(orbs)], i -> in_v2[i] > 0 and in_topt[i] = 0);
topt_unique := Filtered([1..Length(orbs)], i -> in_topt[i] > 0 and in_v2[i] = 0);
both := Filtered([1..Length(orbs)], i -> in_v2[i] > 0 and in_topt[i] > 0);
Print("Orbits in BOTH: ", Length(both), "\\n");
Print("Orbits in v2 ONLY: ", Length(v2_unique), "\\n");
Print("Orbits in topt ONLY: ", Length(topt_unique), "\\n");

if Length(v2_unique) > 0 then
    Print("\\nv2-only orbit reps:\\n");
    for i in v2_unique do
        rep_idx := orbs[i][1];
        Print("  v2[", rep_idx, "] |G|=", Size(ALL[rep_idx]),
              " gens=", GeneratorsOfGroup(ALL[rep_idx]), "\\n");
    od;
fi;
if Length(topt_unique) > 0 then
    Print("\\ntopt-only orbit reps:\\n");
    for i in topt_unique do
        rep_idx := orbs[i][1];
        Print("  topt[", rep_idx - 20, "] |G|=", Size(ALL[rep_idx]),
              " gens=", GeneratorsOfGroup(ALL[rep_idx]), "\\n");
    od;
fi;

# Also report duplicate orbits within each side
v2_orbs := Filtered(orbs, o -> ForAll(o, x -> x <= 20));
topt_orbs := Filtered(orbs, o -> ForAll(o, x -> x > 20));
Print("\\nv2 internal dups (orbit sizes in v2-only): ",
      Concatenation([List(orbs, o -> Number(o, x -> x <= 20))]), "\\n");

LogTo();
QUIT;
'''

(ROOT / "debug_holt_truecount.g").write_text(GAP_SCRIPT, encoding="utf-8")
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_holt_truecount.g"
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
