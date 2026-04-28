LogTo("C:/Users/jeffr/Downloads/Lifting/test_d4_prod_dedup.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n=== D_4^3 x S_3^2 test using production AddIfNotConjugate ===\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/database/d4_cube_cache.g");
cacheK := List(D4_CUBE_CACHE, gens -> Group(gens));

# S_3^2 subdirects
S3a := Group([(13,14,15),(13,14)]);
S3b := Group([(16,17,18),(16,17)]);
S3sq := Group(Concatenation(GeneratorsOfGroup(S3a), GeneratorsOfGroup(S3b)));
subsS3sq := List(ConjugacyClassesSubgroups(S3sq), Representative);
s3Subdirects := Filtered(subsS3sq, function(H)
    local g_a, g_b;
    g_a := Filtered(List(GeneratorsOfGroup(H), g -> RestrictedPerm(g, [13..15])),
                    x -> x <> ());
    g_b := Filtered(List(GeneratorsOfGroup(H), g -> RestrictedPerm(g, [16..18])),
                    x -> x <> ());
    return Length(g_a) > 0 and Length(g_b) > 0 and
           Size(Group(g_a)) = 6 and Size(Group(g_b)) = 6;
end);
N33 := Group([(13,14,15),(13,14),(16,17,18),(16,17),(13,16)(14,17)(15,18)]);
s3NReps := [];
for H in s3Subdirects do
    found := false;
    for K in s3NReps do
        if Size(K) = Size(H) and
           RepresentativeAction(N33, H, K) <> fail then
            found := true; break;
        fi;
    od;
    if not found then Add(s3NReps, H); fi;
od;

shifted := [
    ShiftGroup(TransitiveGroup(4,3), 0),
    ShiftGroup(TransitiveGroup(4,3), 4),
    ShiftGroup(TransitiveGroup(4,3), 8),
    ShiftGroup(TransitiveGroup(3,2), 12),
    ShiftGroup(TransitiveGroup(3,2), 15),
];
N_full := BuildPerComboNormalizer([4,4,4,3,3], shifted, 18);
Print("|N_full| = ", Size(N_full), "\n\n");

GoursatGlue := function(K, G, nsK_list, nsG_list)
    local results, N_K, N_G, Q_K_size, hom_K, hom_G, Q_K, Q_G, iso,
          aut_group, a, phi, gens, gen_K, coset_K, target_coset, g_rep;
    results := [];
    for N_K in nsK_list do
        Q_K_size := Size(K) / Size(N_K);
        hom_K := NaturalHomomorphismByNormalSubgroup(K, N_K);
        Q_K := ImagesSource(hom_K);
        for N_G in nsG_list do
            if Size(G) / Size(N_G) <> Q_K_size then continue; fi;
            hom_G := NaturalHomomorphismByNormalSubgroup(G, N_G);
            Q_G := ImagesSource(hom_G);
            iso := IsomorphismGroups(Q_K, Q_G);
            if iso = fail then continue; fi;
            if Q_K_size = 1 then
                gens := Concatenation(GeneratorsOfGroup(K), GeneratorsOfGroup(G));
                Add(results, Group(gens));
            else
                aut_group := AutomorphismGroup(Q_K);
                for a in aut_group do
                    phi := a * iso;
                    gens := [];
                    Append(gens, GeneratorsOfGroup(N_K));
                    Append(gens, GeneratorsOfGroup(N_G));
                    for gen_K in GeneratorsOfGroup(K) do
                        coset_K := Image(hom_K, gen_K);
                        target_coset := Image(phi, coset_K);
                        g_rep := PreImagesRepresentative(hom_G, target_coset);
                        Add(gens, gen_K * g_rep);
                    od;
                    Add(results, Group(gens));
                od;
            fi;
        od;
    od;
    return results;
end;

# Generate all candidates
Print("Phase 1: Goursat generation...\n");
t0 := Runtime();
allCandidates := [];
for K in cacheK do
    nsK := NormalSubgroups(K);
    for Kprime in s3NReps do
        nsKprime := NormalSubgroups(Kprime);
        Append(allCandidates, GoursatGlue(K, Kprime, nsK, nsKprime));
    od;
od;
Print("  ", Length(allCandidates), " candidates in ",
      Int((Runtime()-t0)/1000), "s\n\n");

# ================================================================
# Use production AddIfNotConjugate with the upgrade cascade
# ================================================================
Print("Phase 2: Production-style dedup with rich invariant cascade\n");
CURRENT_BLOCK_RANGES := [[1,4],[5,8],[9,12],[13,15],[16,18]];
currentN := N_full;
all_fpf := [];
byInvariant := rec();
# Start with cheap, upgrade to rich on first pass since len > threshold
invFunc := CheapSubgroupInvariantFull;
_DEDUP_RA_COUNT := 0;

# Immediately upgrade to rich since we have >1000 candidates
if Length(allCandidates) > RICH_DEDUP_THRESHOLD then
    invFunc := ComputeSubgroupInvariant;
    Print("  Upgraded to rich invariants (CC + 2-subset)\n");
fi;

t0 := Runtime();
tLast := Runtime();
raLast := 0;
for _idxH in [1..Length(allCandidates)] do
    H := allCandidates[_idxH];
    AddIfNotConjugate(currentN, H, all_fpf, byInvariant, invFunc);
    allCandidates[_idxH] := 0;  # allow GC
    if Runtime() - tLast > 60000 then
        Print("    [dedup] ", _idxH, "/", Length(allCandidates) + 0,
              " checked, ", Length(all_fpf), " unique, ",
              _DEDUP_RA_COUNT - raLast, " RA in last 60s (",
              Int((Runtime() - t0) / 1000), "s total)\n");
        tLast := Runtime();
        raLast := _DEDUP_RA_COUNT;
    fi;
od;
tDedup := Runtime() - t0;

Print("\n=== RESULT ===\n");
Print("Deduped: ", Length(all_fpf), "\n");
Print("Target:  26956\n");
Print("RA calls: ", _DEDUP_RA_COUNT, "\n");
Print("Dedup time: ", Int(tDedup/1000), "s\n");
if Length(all_fpf) = 26956 then
    Print("EXACT MATCH!\n");
elif Length(all_fpf) > 26956 then
    Print("Overcount by ", Length(all_fpf) - 26956, "\n");
else
    Print("Undercount by ", 26956 - Length(all_fpf), "\n");
fi;

LogTo();
QUIT;
