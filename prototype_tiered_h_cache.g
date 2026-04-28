
LogTo("C:/Users/jeffr/Downloads/Lifting/prototype_tiered_h_cache.log");
Print("=== prototype tiered H-cache for [4,3]^4 LEFT, Q in {C_2, C_3, S_3} ===\n");

# ---- Helpers -----------------------------------------------------------
ConjAction := function(K, g) return K^g; end;
SafeId := function(G)
    if Size(G) = 1 then return [1, 0, [1, 1]]; fi;
    return [Size(G), 0, IdGroup(G)];
end;
SafeGroup := function(gens, default_amb)
    if Length(gens) = 0 then return TrivialSubgroup(default_amb); fi;
    return Group(gens);
end;

# ---- Tiered enumeration ------------------------------------------------
# Tier 1: Q prime → abelianization
_IndexPNormalsAbelianization := function(H, p)
    local DH, hom, A, max_subs;
    DH := DerivedSubgroup(H);
    if Index(H, DH) mod p <> 0 then return []; fi;
    hom := NaturalHomomorphismByNormalSubgroup(H, DH);
    A := Range(hom);
    max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = p);
    return List(max_subs, K -> PreImage(hom, K));
end;

# Tier 2: GQuotients
_NormalsViaGQuotients := function(H, Q)
    return Set(List(GQuotients(H, Q), Kernel));
end;

# Top-level dispatch
_TieredEnumerate := function(H, q_groups, tier_times)
    local result, Q, sz, t, kers, big_qs, qid_set, normals;
    result := [];
    big_qs := [];
    for Q in q_groups do
        sz := Size(Q);
        if IsPrimeInt(sz) then
            t := Runtime();
            kers := _IndexPNormalsAbelianization(H, sz);
            tier_times.t1 := tier_times.t1 + (Runtime() - t);
            tier_times.t1_kers := tier_times.t1_kers + Length(kers);
            Append(result, kers);
        elif sz <= 200 then
            t := Runtime();
            kers := _NormalsViaGQuotients(H, Q);
            tier_times.t2 := tier_times.t2 + (Runtime() - t);
            tier_times.t2_kers := tier_times.t2_kers + Length(kers);
            Append(result, kers);
        else
            Add(big_qs, Q);
        fi;
    od;
    if Length(big_qs) > 0 then
        t := Runtime();
        qid_set := Set(List(big_qs, SafeId));
        normals := NormalSubgroups(H);
        kers := Filtered(normals,
                         K -> K <> H and SafeId(H/K) in qid_set);
        tier_times.t3 := tier_times.t3 + (Runtime() - t);
        tier_times.t3_kers := tier_times.t3_kers + Length(kers);
        Append(result, kers);
    fi;
    return Set(result);
end;

# Build orbit records under N_W(H) for the K-list
_OrbitRecsFromKs := function(H, N_H, normals)
    local K_orbit, K_H, hom_H, Q_H, Stab_NH_KH, orbits;
    orbits := [];
    for K_orbit in Orbits(N_H, normals, ConjAction) do
        K_H := K_orbit[1];
        hom_H := NaturalHomomorphismByNormalSubgroup(H, K_H);
        Q_H := Range(hom_H);
        Stab_NH_KH := Stabilizer(N_H, K_H, ConjAction);
        Add(orbits, rec(
            K_H_gens := GeneratorsOfGroup(K_H),
            Stab_NH_KH_gens := GeneratorsOfGroup(Stab_NH_KH),
            qsize := Size(Q_H),
            qid := SafeId(Q_H)
        ));
    od;
    return orbits;
end;

# ---- Set up the run ----------------------------------------------------
ML := 16;
S_ML := SymmetricGroup(ML);

# Block-wreath ambient W_ML = S_4 wr S_4 (size 7,962,624)
W_ML := WreathProduct(SymmetricGroup(4), SymmetricGroup(4));
Print("|W_ML| = ", Size(W_ML), "\n");

# Q-types we care about: C_2, C_3, S_3 (the three distinct iso classes
# appearing as quotients of TG(3,1)=C_3 and TG(3,2)=S_3)
Q_C2 := CyclicGroup(IsPermGroup, 2);
Q_C3 := CyclicGroup(IsPermGroup, 3);
Q_S3 := SymmetricGroup(3);
Q_GROUPS := [Q_C2, Q_C3, Q_S3];
Print("Q_GROUPS: |Q|=", List(Q_GROUPS, Size), "\n\n");

# Read the [4,3]^4 LEFT subs (12,525 FPF subgroups of D_8^4)
t := Runtime();
Read("C:/Users/jeffr/Downloads/Lifting/predict_species_tmp/_two_factor/[2,1]_[4,3]_[4,3]_[4,3]_[4,3]/subs_left.g");
Print("[t+", Runtime() - t, "ms] read ", Length(SUBGROUPS), " H subgroups\n\n");

# Run tiered cache build with timing
H_CACHE := [];
tier_times := rec(
    t1 := 0, t2 := 0, t3 := 0,
    t1_kers := 0, t2_kers := 0, t3_kers := 0
);
norm_total := 0;   # Normalizer time
orbit_total := 0;  # Orbit-decomp time
total_orbits := 0;

build_t0 := Runtime();
last_hb := Runtime();
for hi in [1..Length(SUBGROUPS)] do
    if hi = 1 or hi mod 500 = 0 or Runtime() - last_hb >= 60000 then
        Print("[t+", Runtime() - build_t0, "ms] hi=", hi, "/",
              Length(SUBGROUPS), " |H|=", Size(SUBGROUPS[hi]),
              " T1=", tier_times.t1, "ms T2=", tier_times.t2,
              "ms T3=", tier_times.t3, "ms norm=", norm_total,
              "ms orbits=", orbit_total, "ms\n");
        last_hb := Runtime();
    fi;
    H := SUBGROUPS[hi];

    t := Runtime();
    N_H := Normalizer(W_ML, H);
    norm_total := norm_total + (Runtime() - t);

    normals := _TieredEnumerate(H, Q_GROUPS, tier_times);

    t := Runtime();
    orbit_recs := _OrbitRecsFromKs(H, N_H, normals);
    orbit_total := orbit_total + (Runtime() - t);
    total_orbits := total_orbits + Length(orbit_recs);

    Add(H_CACHE, rec(
        H_gens := GeneratorsOfGroup(H),
        N_H_gens := GeneratorsOfGroup(N_H),
        computed_q_ids := Set(List(Q_GROUPS, SafeId)),
        orbits := orbit_recs
    ));
od;

build_total := Runtime() - build_t0;
Print("\n=== build complete ===\n");
Print("Total wall: ", build_total, "ms = ", Float(build_total/1000.0), "s\n");
Print("Tier 1 (prime abelianization): ", tier_times.t1, "ms, ",
      tier_times.t1_kers, " kernels\n");
Print("Tier 2 (GQuotients):           ", tier_times.t2, "ms, ",
      tier_times.t2_kers, " kernels\n");
Print("Tier 3 (NS+filter):            ", tier_times.t3, "ms, ",
      tier_times.t3_kers, " kernels\n");
Print("Normalizer total:              ", norm_total, "ms\n");
Print("Orbit-decomp total:            ", orbit_total, "ms\n");
Print("Total orbits in cache:         ", total_orbits, "\n");

# Save the cache
Print("\nSaving H-cache to disk...\n");
PrintTo("C:/Users/jeffr/Downloads/Lifting/prototype_h_cache_43_4_for_S3.g",
    "H_CACHE := ", H_CACHE, ";\n");
Print("saved to C:/Users/jeffr/Downloads/Lifting/prototype_h_cache_43_4_for_S3.g\n");

LogTo();
QUIT;
