"""compute_normalsubgroups_D8_4.py — long-running standalone computation
of NormalSubgroups(D_8^4), saving the result to a .g file when done.
Backup option in case we need the full normal-subgroup lattice later.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "normalsubgroups_D8_4.log"
OUT = ROOT / "normalsubgroups_D8_4.g"
if LOG.exists():
    LOG.unlink()

GAP_SCRIPT = f'''
LogTo("{str(LOG).replace(chr(92), "/")}");
Print("=== NormalSubgroups(D_8^4) — full lattice ===\\n");

# Construct D_8^4 in standard 16-point embedding
t := Runtime();
D8 := TransitiveGroup(4, 3);
H := DirectProduct(D8, D8, D8, D8);
Print("[t+", Runtime()-t, "ms] |H| = ", Size(H), "\\n");

# Time + run NormalSubgroups
Print("\\n[t=0] beginning NormalSubgroups(H)...\\n");
t := Runtime();
NS := NormalSubgroups(H);
Print("[t+", Runtime()-t, "ms] NormalSubgroups(H) DONE; count=", Length(NS), "\\n");

# Distribution
sizes := SortedList(List(NS, Size));
Print("\\n--- distribution by |K| ---\\n");
for s in Set(sizes) do
    Print("  |K|=", s, "  index=", 4096/s, "  count=", Number(sizes, x -> x = s), "\\n");
od;

# Save the lattice to disk: list of generator-lists, by index
Print("\\nSaving to disk...\\n");
PrintTo("{str(OUT).replace(chr(92), "/")}",
    "NORMALS_OF_D8_4 := [\\n");
for K in NS do
    AppendTo("{str(OUT).replace(chr(92), "/")}",
        "  rec(size := ", Size(K), ", gens := ", GeneratorsOfGroup(K), "),\\n");
od;
AppendTo("{str(OUT).replace(chr(92), "/")}", "];\\n");
Print("saved to {str(OUT).replace(chr(92), "/")}\\n");

LogTo();
QUIT;
'''

(ROOT / "compute_normalsubgroups_D8_4.g").write_text(GAP_SCRIPT, encoding="utf-8")

bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/compute_normalsubgroups_D8_4.g"

env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"

print(f"Running NormalSubgroups(D_8^4) computation (will take many minutes)...")
print(f"Log: {LOG}")
print(f"Output: {OUT}")
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cyg}"'],
    env=env,
)
print(f"GAP rc={proc.returncode}")
