"""test_ns_breakdown.py — break down where time goes inside NormalSubgroups
+ post-processing on a typical |H|=2048 subgroup of D_8^4.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "test_ns_breakdown.log"
NS_FILE = ROOT / "normalsubgroups_D8_4.g"
if LOG.exists():
    LOG.unlink()

GAP_SCRIPT = f'''
LogTo("{str(LOG).replace(chr(92), "/")}");
Print("=== NS breakdown on |H|=2048 subgroup of D_8^4 ===\\n");

# Construct D_8^4
D8 := TransitiveGroup(4, 3);
LEFT := DirectProduct(D8, D8, D8, D8);
Print("|LEFT| = ", Size(LEFT), "\\n");

# Pick an index-2 subgroup of LEFT — first thing of size 2048 in NORMALS_OF_D8_4
t := Runtime();
Read("{str(NS_FILE).replace(chr(92), "/")}");
Print("[t+", Runtime()-t, "ms] loaded NORMALS_OF_D8_4 records\\n");

t := Runtime();
H_record := First(NORMALS_OF_D8_4, e -> e.size = 2048);
H := Group(H_record.gens);
Print("[t+", Runtime()-t, "ms] picked H, |H|=", Size(H), "\\n");

Print("HasPcgs(H): ", HasPcgs(H), "\\n");
Print("IsSolvable(H): ", IsSolvableGroup(H), "\\n");

# NS call
Print("\\n--- NS itself ---\\n");
t := Runtime();
NS := NormalSubgroups(H);
ns_t := Runtime() - t;
Print("[t+", ns_t, "ms] NormalSubgroups(H) returned ", Length(NS), " entries\\n");

# Check if Size is cached on outputs
n_with_size := 0;
n_with_pcgs := 0;
for K in NS do
    if HasSize(K) then n_with_size := n_with_size + 1; fi;
    if HasPcgs(K) then n_with_pcgs := n_with_pcgs + 1; fi;
od;
Print("Of ", Length(NS), " output groups: ",
      n_with_size, " have Size cached, ", n_with_pcgs, " have Pcgs cached\\n");

# Touch each (no real work)
t := Runtime();
for K in NS do
    # do nothing
od;
Print("[t+", Runtime()-t, "ms] empty iteration over NS\\n");

# Compute Size on each
t := Runtime();
sizes := List(NS, Size);
Print("[t+", Runtime()-t, "ms] computed Size on each\\n");

# After computing Size: now should be cached
n_with_size := Number(NS, K -> HasSize(K));
Print("After computing: ", n_with_size, " have Size cached\\n");

# Compute IdGroup of quotient on each (qid)
t := Runtime();
qids := List(NS, function(K)
    local hom, Q;
    if Size(K) = Size(H) then return [1, 0]; fi;
    hom := NaturalHomomorphismByNormalSubgroup(H, K);
    Q := Range(hom);
    return Size(Q);   # just size to keep test simple
end);
Print("[t+", Runtime()-t, "ms] computed quotient sizes\\n");

# Distribution of normal subgroup sizes
Print("\\n--- distribution by |K| ---\\n");
for s in Set(sizes) do
    Print("  |K|=", s, "  count=", Number(sizes, x -> x = s), "\\n");
od;

LogTo();
QUIT;
'''

(ROOT / "test_ns_breakdown.g").write_text(GAP_SCRIPT, encoding="utf-8")
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_ns_breakdown.g"
env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"
print(f"Running... (log: {LOG})")
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cyg}"'],
    env=env,
)
print(f"GAP rc={proc.returncode}")
if LOG.exists():
    print(LOG.read_text(encoding="utf-8"))
