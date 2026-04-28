
LogTo("C:/Users/jeffr/Downloads/Lifting/build_unified_trad_w_d8_4.log");
Print("=== Unified TRAD-W H-cache build for [4,3]^4 LEFT ===\n");

ConjAction := function(K, g) return K^g; end;
SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

ML := 16;
Q_SIZE_FILTER := [1, 2, 3, 6];

# Build W_ML = S_4 wr S_4
W_ML := WreathProduct(SymmetricGroup(4), SymmetricGroup(4));
Print("|W_ML| = ", Size(W_ML), "\n");

# Read LEFT subs (12525 H's)
t := Runtime();
Read("C:/Users/jeffr/Downloads/Lifting/predict_species_tmp/_two_factor/[2,1]_[4,3]_[4,3]_[4,3]_[4,3]/subs_left.g");
Print("[t+", Runtime()-t, "ms] read ", Length(SUBGROUPS), " H subgroups\n");

# Precompute NS for the FULL D_8^4 by loading from disk
t := Runtime();
Read("C:/Users/jeffr/Downloads/Lifting/normalsubgroups_D8_4.g");
Print("[t+", Runtime()-t, "ms] loaded precomputed NORMALS_OF_D8_4 (",
      Length(NORMALS_OF_D8_4), " entries)\n");

t := Runtime();
PRECOMP_NS := List(NORMALS_OF_D8_4, function(e)
    if Length(e.gens) = 0 then return TrivialSubgroup(SUBGROUPS[1]); fi;
    return Group(e.gens);
end);
Print("[t+", Runtime()-t, "ms] reconstituted ", Length(PRECOMP_NS), " precomputed groups\n");

# Build the cache
H_CACHE := [];
norm_total := 0;
ns_total := 0;
filt_total := 0;
orb_total := 0;
ns_call_count := 0;
ns_skip_count := 0;
total_orbits := 0;
build_t0 := Runtime();
last_hb := Runtime();

for hi in [1..Length(SUBGROUPS)] do
    if hi = 1 or hi mod 500 = 0 or Runtime() - last_hb >= 60000 then
        Print("[t+", Runtime()-build_t0, "ms] hi=", hi, "/",
              Length(SUBGROUPS), " |H|=", Size(SUBGROUPS[hi]),
              " norm=", norm_total, "ms ns=", ns_total,
              "ms filt=", filt_total, "ms orb=", orb_total, "ms\n");
        last_hb := Runtime();
    fi;
    H := SUBGROUPS[hi];

    t := Runtime();
    N_W := Normalizer(W_ML, H);
    norm_total := norm_total + (Runtime() - t);

    # Drop-in: if H is the FULL LEFT (|H|=4096, iter 1), use precomputed NS
    if Size(H) = 4096 and hi = 1 then
        normals := PRECOMP_NS;
        ns_skip_count := ns_skip_count + 1;
    else
        t := Runtime();
        normals := NormalSubgroups(H);
        ns_total := ns_total + (Runtime() - t);
        ns_call_count := ns_call_count + 1;
    fi;

    # Filter by qsize
    t := Runtime();
    ns_filt := Filtered(normals, K -> K <> H and Size(H)/Size(K) in Q_SIZE_FILTER);
    filt_total := filt_total + (Runtime() - t);

    # Orbit decomp + per-orbit data
    t := Runtime();
    orbit_recs := [];
    for K_orbit in Orbits(N_W, ns_filt, ConjAction) do
        K_H := K_orbit[1];
        hom_H := NaturalHomomorphismByNormalSubgroup(H, K_H);
        Q_H := Range(hom_H);
        Stab_NH_KH := Stabilizer(N_W, K_H, ConjAction);
        Add(orbit_recs, rec(
            K_H_gens := GeneratorsOfGroup(K_H),
            Stab_NH_KH_gens := GeneratorsOfGroup(Stab_NH_KH),
            qsize := Size(Q_H),
            qid := SafeId(Q_H)
        ));
    od;
    orb_total := orb_total + (Runtime() - t);
    total_orbits := total_orbits + Length(orbit_recs);

    Add(H_CACHE, rec(
        H_gens := GeneratorsOfGroup(H),
        N_H_gens := GeneratorsOfGroup(N_W),
        computed_q_sizes := Q_SIZE_FILTER,
        orbits := orbit_recs
    ));
od;

build_total := Runtime() - build_t0;
Print("\n=== build complete ===\n");
Print("Total wall: ", build_total, "ms = ", Float(build_total/1000.0), "s\n");
Print("Normalizer in W_ML: ", norm_total, "ms\n");
Print("NormalSubgroups (", ns_call_count, " calls, ", ns_skip_count, " skipped): ",
      ns_total, "ms\n");
Print("Filter:             ", filt_total, "ms\n");
Print("Orbit decomp:       ", orb_total, "ms\n");
Print("Total orbits:       ", total_orbits, "\n");

# Save the cache
Print("\nSaving cache to ", "C:/Users/jeffr/Downloads/Lifting/unified_trad_w_h_cache_43_4.g", "\n");
PrintTo("C:/Users/jeffr/Downloads/Lifting/unified_trad_w_h_cache_43_4.g",
    "H_CACHE := ", H_CACHE, ";\n");
Print("saved.\n");

# Validation: per-entry orbit count vs tiered cache
Print("\n=== validation: per-entry orbit count match ===\n");
TRAD_CACHE := H_CACHE;
H_CACHE := fail;
t := Runtime();
Read("C:/Users/jeffr/Downloads/Lifting/prototype_h_cache_43_4_for_S3.g");
Print("[t+", Runtime()-t, "ms] loaded tiered cache (", Length(H_CACHE), " entries)\n");

mismatches := 0;
for hi in [1..Length(TRAD_CACHE)] do
    trad_n := Length(TRAD_CACHE[hi].orbits);
    tier_n := Length(H_CACHE[hi].orbits);
    if trad_n <> tier_n then
        if mismatches < 5 then
            Print("  MISMATCH at hi=", hi, ": trad=", trad_n, " tier=", tier_n, "\n");
        fi;
        mismatches := mismatches + 1;
    fi;
od;
Print("Total mismatches: ", mismatches, "/", Length(TRAD_CACHE), "\n");
if mismatches = 0 then
    Print("✓ FULL VALIDATION PASS — TRAD-W matches TIERED-W exactly\n");
fi;

LogTo();
QUIT;
