"""test_normal_subgroups_43_4.py — time NormalSubgroups(D_8^4) and related operations
to see what's actually slow in iter 1 of the [4,3]^4 H-cache build.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "test_normal_subgroups_43_4.log"
SUBS = ROOT / "predict_species_tmp" / "_two_factor" / "[2,1]_[4,3]_[4,3]_[4,3]_[4,3]" / "subs_left.g"

if LOG.exists():
    LOG.unlink()

GAP_SCRIPT = f'''
LogTo("{str(LOG).replace(chr(92), "/")}");
Print("=== test_normal_subgroups_43_4 ===\\n");

t := Runtime();
Read("{str(SUBS).replace(chr(92), "/")}");
Print("[t+", Runtime()-t, "ms] read subs file: ", Length(SUBGROUPS), " subgroups\\n");

H := SUBGROUPS[1];
Print("|H| = ", Size(H), "  (skipping StructureDescription, slow for |H|=4096)\\n");

# Build the block-wreath W = S_4 wr S_4
t := Runtime();
W := WreathProduct(SymmetricGroup(4), SymmetricGroup(4));
Print("[t+", Runtime()-t, "ms] built W = S_4 wr S_4, |W|=", Size(W), "\\n");

# Time Normalizer(W, H)
Print("\\n--- Normalizer(W, H) ---\\n");
t := Runtime();
N_W := Normalizer(W, H);
Print("[t+", Runtime()-t, "ms] Normalizer(W, H) done, |N_W|=", Size(N_W), "\\n");

# Time abelianization-based index-2 enumeration FIRST (cheap, expected)
Print("\\n--- Abelianization-based index-2 normals ---\\n");
t := Runtime();
DH := DerivedSubgroup(H);
Print("[t+", Runtime()-t, "ms] DerivedSubgroup done, |[H,H]|=", Size(DH), "\\n");

t := Runtime();
H_ab_hom := NaturalHomomorphismByNormalSubgroup(H, DH);
A := Range(H_ab_hom);
Print("[t+", Runtime()-t, "ms] abelianization: |H/[H,H]|=", Size(A),
      ", AbelianInvariants=", AbelianInvariants(A), "\\n");

t := Runtime();
maxs_A := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = 2);
Print("[t+", Runtime()-t, "ms] index-2 maximals in A: ", Length(maxs_A), "\\n");

t := Runtime();
index2_in_H := List(maxs_A, K -> PreImage(H_ab_hom, K));
Print("[t+", Runtime()-t, "ms] preimages in H: ", Length(index2_in_H), "\\n");

# Time NormalSubgroups(H) — the suspected bottleneck
Print("\\n--- NormalSubgroups(H) (FULL lattice) ---\\n");
t := Runtime();
NS := NormalSubgroups(H);
Print("[t+", Runtime()-t, "ms] NormalSubgroups(H) done, count=", Length(NS), "\\n");

# Cross-check
ns_idx2 := Filtered(NS, K -> Index(H, K) = 2);
Print("NormalSubgroups index-2 count: ", Length(ns_idx2), "\\n");
Print("Abelianization index-2 count:  ", Length(index2_in_H), "\\n");
Print("Match: ", Length(ns_idx2) = Length(index2_in_H), "\\n");

LogTo();
QUIT;
'''

(ROOT / "test_normal_subgroups_43_4.g").write_text(GAP_SCRIPT, encoding="utf-8")

bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_normal_subgroups_43_4.g"

env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"

print(f"Running test... (log: {LOG})")
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cyg}"'],
    env=env,
)
print(f"GAP rc={proc.returncode}")
print()
print(LOG.read_text(encoding="utf-8") if LOG.exists() else "(no log)")
