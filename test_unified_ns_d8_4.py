"""test_unified_ns_d8_4.py — drop-in test of the unified NS+filter+W_ML
path for the FULL D_8^4 entry of the [4,3]^4 LEFT cache.

Loads the precomputed normalsubgroups_D8_4.g (536,501 normals from
last night's run, 114 MB on disk) instead of recomputing NS.  Then
filters by q_size_filter = {1,2,3,6} (S19-relevant), orbit-decomposes
under N_{S_4 wr S_4}(D_8^4), times every step.

The point: if NS is treated as "free" (precomputed), what's the
cost of the rest of the unified path?  Compare to the tiered cache's
orbit count for D_8^4 to validate correctness.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "test_unified_ns_d8_4.log"
NS_FILE = ROOT / "normalsubgroups_D8_4.g"
PROTO_CACHE = ROOT / "prototype_h_cache_43_4_for_S3.g"

if LOG.exists():
    LOG.unlink()

GAP_SCRIPT = f'''
LogTo("{str(LOG).replace(chr(92), "/")}");
Print("=== Unified NS+filter+W_ML path on D_8^4 ===\\n");

# Helpers (matching predict_2factor.py)
ConjAction := function(K, g) return K^g; end;
SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

# Construct D_8^4 fresh in standard 16-point embedding
t := Runtime();
D8 := TransitiveGroup(4, 3);
H := DirectProduct(D8, D8, D8, D8);
Print("[t+", Runtime()-t, "ms] |H| = ", Size(H), "\\n");

# Build W_ML = S_4 wr S_4
t := Runtime();
W := WreathProduct(SymmetricGroup(4), SymmetricGroup(4));
Print("[t+", Runtime()-t, "ms] |W| = ", Size(W), "\\n");

# Time Normalizer(W, H)
t := Runtime();
N_W := Normalizer(W, H);
Print("[t+", Runtime()-t, "ms] |N_W(H)| = ", Size(N_W), "\\n");

# DROP IN the precomputed normals list (instead of NS)
t := Runtime();
Read("{str(NS_FILE).replace(chr(92), "/")}");
Print("[t+", Runtime()-t, "ms] loaded NORMALS_OF_D8_4: ", Length(NORMALS_OF_D8_4), " entries\\n");

# Reconstitute as Group objects (the file stored size + gens)
t := Runtime();
NS_groups := List(NORMALS_OF_D8_4, function(e)
    if Length(e.gens) = 0 then return TrivialSubgroup(H); fi;
    return Group(e.gens);
end);
Print("[t+", Runtime()-t, "ms] reconstituted ", Length(NS_groups), " Group objects\\n");

# Apply S19-relevant q_size_filter: K with |H/K| in {1, 2, 3, 6}
# K = H is excluded; K=trivial gives Q=H (|H|=4096, not in filter), excluded
q_size_filter := [1, 2, 3, 6];
t := Runtime();
NS_filtered := Filtered(NS_groups,
    K -> K <> H and Size(H)/Size(K) in q_size_filter);
Print("[t+", Runtime()-t, "ms] filtered to ", Length(NS_filtered), " K's\\n");

# Orbit decomposition under N_W
t := Runtime();
orbits := Orbits(N_W, NS_filtered, ConjAction);
Print("[t+", Runtime()-t, "ms] decomposed into ", Length(orbits), " N_W-orbits\\n");

# Per-orbit: K, hom, Q, qid, qsize, Stab
t := Runtime();
orbit_recs := [];
for orb in orbits do
    K_H := orb[1];
    hom_H := NaturalHomomorphismByNormalSubgroup(H, K_H);
    Q_H := Range(hom_H);
    Stab_NH_KH := Stabilizer(N_W, K_H, ConjAction);
    Add(orbit_recs, rec(
        qsize := Size(Q_H),
        qid := SafeId(Q_H)
    ));
od;
Print("[t+", Runtime()-t, "ms] built ", Length(orbit_recs), " orbit records\\n");

# Distribution of orbits by qsize
Print("\\n--- orbit distribution by |Q| ---\\n");
for s in Set(List(orbit_recs, r -> r.qsize)) do
    Print("  |Q|=", s, ":  ", Number(orbit_recs, r -> r.qsize = s), " orbits\\n");
od;

# Compare to the tiered cache for D_8^4
Print("\\n--- compare to tiered cache for full D_8^4 ---\\n");
t := Runtime();
Read("{str(PROTO_CACHE).replace(chr(92), "/")}");
Print("[t+", Runtime()-t, "ms] loaded prototype cache: ", Length(H_CACHE), " entries\\n");

# Find the entry with |H_gens|... actually find the H entry
proto_entry := H_CACHE[1];   # The first entry SHOULD be the largest H = D_8^4 itself
Print("Prototype cache entry 1: ", Length(proto_entry.orbits), " orbits\\n");
Print("This run                : ", Length(orbit_recs), " orbits\\n");

# Distribution match check
proto_qsizes := SortedList(List(proto_entry.orbits, r -> r.qsize));
this_qsizes := SortedList(List(orbit_recs, r -> r.qsize));
Print("Tiered cache qsize distribution: ", proto_qsizes, "\\n");
Print("Unified-NS qsize distribution:   ", this_qsizes, "\\n");
Print("Match: ", proto_qsizes = this_qsizes, "\\n");

LogTo();
QUIT;
'''

(ROOT / "test_unified_ns_d8_4.g").write_text(GAP_SCRIPT, encoding="utf-8")

bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_unified_ns_d8_4.g"
env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"

print(f"Running unified NS+filter+W_ML on D_8^4...")
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cyg}"'],
    env=env,
)
print(f"GAP rc={proc.returncode}")
print()
if LOG.exists():
    print(LOG.read_text(encoding="utf-8"))
