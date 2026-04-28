"""test_normalsubgroups_only.py — minimal timing of NormalSubgroups(D_8^4)
in isolation.  Constructs D_8^4 from scratch (no file IO).
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "test_normalsubgroups_only.log"

if LOG.exists():
    LOG.unlink()

GAP_SCRIPT = f'''
LogTo("{str(LOG).replace(chr(92), "/")}");
Print("=== NormalSubgroups(D_8^4) timing ===\\n");

# Construct D_8^4 = direct product of 4 copies of D_8 = TG(4,3),
# acting on 16 points as 4 disjoint 4-blocks.
t := Runtime();
D8 := TransitiveGroup(4, 3);
H := DirectProduct(D8, D8, D8, D8);
Print("[t+", Runtime()-t, "ms] constructed D_8^4, |H|=", Size(H), "\\n");

# Just the one test
Print("\\n--- NormalSubgroups(H) ---\\n");
t := Runtime();
NS := NormalSubgroups(H);
Print("[t+", Runtime()-t, "ms] NormalSubgroups(H) DONE, count=", Length(NS), "\\n");

# Distribution by index
sizes := SortedList(List(NS, Size));
Print("\\nDistribution of |K| for K in NormalSubgroups(H):\\n");
for s in Set(sizes) do
    Print("  |K|=", s, "  index=", 4096/s, "  count=", Number(sizes, x -> x = s), "\\n");
od;

LogTo();
QUIT;
'''

(ROOT / "test_normalsubgroups_only.g").write_text(GAP_SCRIPT, encoding="utf-8")

bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_normalsubgroups_only.g"

env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"

print(f"Running standalone NormalSubgroups timing... (log: {LOG})")
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cyg}"'],
    env=env,
)
print(f"GAP rc={proc.returncode}")
print()
print(LOG.read_text(encoding="utf-8") if LOG.exists() else "(no log)")
