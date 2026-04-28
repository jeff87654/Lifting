"""debug_3322_combo1.py — check if topt's 6 classes for
[2,1]_[2,1]_[3,1]_[3,2] in [3,3,2,2] are actually 5 distinct S_10-classes.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "debug_3322_combo1.log"
if LOG.exists():
    LOG.unlink()

GAP_SCRIPT = f'''
LogTo("{str(LOG).replace(chr(92), "/")}");

# topt's 6 entries for [2,1]_[2,1]_[3,1]_[3,2]
gens_list := [
    [(1,2)(3,4),(5,6,7),(8,9,10),(8,9)],
    [(1,2)(3,4)(8,9),(5,6,7),(8,10,9)],
    [(1,2),(3,4),(5,6,7),(8,9,10),(8,9)],
    [(1,2)(8,9),(3,4),(5,6,7),(8,10,9)],
    [(1,2),(3,4)(8,9),(5,6,7),(8,10,9)],
    [(1,2)(8,9),(3,4)(8,9),(5,6,7),(8,10,9)]
];

groups := List(gens_list, gens -> Group(gens));
Print("topt entries:\\n");
for i in [1..Length(groups)] do
    Print("  ", i, ": |G|=", Size(groups[i]), "\\n");
od;

S10 := SymmetricGroup(10);
Print("\\n=== pairwise S_10-conjugacy check ===\\n");
for i in [1..Length(groups)] do
    for j in [i+1..Length(groups)] do
        ra := RepresentativeAction(S10, groups[i], groups[j]);
        if ra <> fail then
            Print("  ", i, " ~ ", j, " via sigma = ", ra, "\\n");
        fi;
    od;
od;

# Build union-find equivalence classes
parent := [1..Length(groups)];
UFFind := function(x)
    while parent[x] <> x do
        parent[x] := parent[parent[x]];
        x := parent[x];
    od;
    return x;
end;
for i in [1..Length(groups)] do
    for j in [i+1..Length(groups)] do
        if RepresentativeAction(S10, groups[i], groups[j]) <> fail then
            parent[UFFind(j)] := UFFind(i);
        fi;
    od;
od;
classes := Set(List([1..Length(groups)], UFFind));
Print("\\nDistinct S_10-classes: ", Length(classes), "\\n");
Print("Class membership: ", List([1..Length(groups)], UFFind), "\\n");

LogTo();
QUIT;
'''
(ROOT / "debug_3322_combo1.g").write_text(GAP_SCRIPT, encoding="utf-8")
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_3322_combo1.g"
env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cyg}"'],
    env=env)
print(LOG.read_text(encoding="utf-8") if LOG.exists() else "(no log)")
