
LogTo("C:/Users/jeffr/Downloads/Lifting/test_unified_ns_d8_4.log");
Print("=== Unified NS+filter+W_ML path on D_8^4 ===\n");

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
Print("[t+", Runtime()-t, "ms] |H| = ", Size(H), "\n");

# Build W_ML = S_4 wr S_4
t := Runtime();
W := WreathProduct(SymmetricGroup(4), SymmetricGroup(4));
Print("[t+", Runtime()-t, "ms] |W| = ", Size(W), "\n");

# Time Normalizer(W, H)
t := Runtime();
N_W := Normalizer(W, H);
Print("[t+", Runtime()-t, "ms] |N_W(H)| = ", Size(N_W), "\n");

# DROP IN the precomputed normals list (instead of NS)
t := Runtime();
Read("C:/Users/jeffr/Downloads/Lifting/normalsubgroups_D8_4.g");
Print("[t+", Runtime()-t, "ms] loaded NORMALS_OF_D8_4: ", Length(NORMALS_OF_D8_4), " entries\n");

# Reconstitute as Group objects (the file stored size + gens)
t := Runtime();
NS_groups := List(NORMALS_OF_D8_4, function(e)
    if Length(e.gens) = 0 then return TrivialSubgroup(H); fi;
    return Group(e.gens);
end);
Print("[t+", Runtime()-t, "ms] reconstituted ", Length(NS_groups), " Group objects\n");

# Apply S19-relevant q_size_filter: K with |H/K| in (1, 2, 3, 6)
# K = H is excluded; K=trivial gives Q=H (|H|=4096, not in filter), excluded
q_size_filter := [1, 2, 3, 6];
t := Runtime();
NS_filtered := Filtered(NS_groups,
    K -> K <> H and Size(H)/Size(K) in q_size_filter);
Print("[t+", Runtime()-t, "ms] filtered to ", Length(NS_filtered), " K's\n");

# Orbit decomposition under N_W
t := Runtime();
orbits := Orbits(N_W, NS_filtered, ConjAction);
Print("[t+", Runtime()-t, "ms] decomposed into ", Length(orbits), " N_W-orbits\n");

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
Print("[t+", Runtime()-t, "ms] built ", Length(orbit_recs), " orbit records\n");

# Distribution of orbits by qsize
Print("\n--- orbit distribution by |Q| ---\n");
for s in Set(List(orbit_recs, r -> r.qsize)) do
    Print("  |Q|=", s, ":  ", Number(orbit_recs, r -> r.qsize = s), " orbits\n");
od;

# Compare to the tiered cache for D_8^4
Print("\n--- compare to tiered cache for full D_8^4 ---\n");
t := Runtime();
Read("C:/Users/jeffr/Downloads/Lifting/prototype_h_cache_43_4_for_S3.g");
Print("[t+", Runtime()-t, "ms] loaded prototype cache: ", Length(H_CACHE), " entries\n");

# Find the entry with |H_gens|... actually find the H entry
proto_entry := H_CACHE[1];   # The first entry SHOULD be the largest H = D_8^4 itself
Print("Prototype cache entry 1: ", Length(proto_entry.orbits), " orbits\n");
Print("This run                : ", Length(orbit_recs), " orbits\n");

# Distribution match check
proto_qsizes := SortedList(List(proto_entry.orbits, r -> r.qsize));
this_qsizes := SortedList(List(orbit_recs, r -> r.qsize));
Print("Tiered cache qsize distribution: ", proto_qsizes, "\n");
Print("Unified-NS qsize distribution:   ", this_qsizes, "\n");
Print("Match: ", proto_qsizes = this_qsizes, "\n");

LogTo();
QUIT;
