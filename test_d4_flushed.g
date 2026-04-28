Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

progressFile := "C:/Users/jeffr/Downloads/Lifting/test_d4_flushed_progress.log";
PrintTo(progressFile, "=== D_4^3 x S_3^2 test (flushed progress) ===\n");

Read("C:/Users/jeffr/Downloads/Lifting/database/d4_cube_cache.g");
cacheK := List(D4_CUBE_CACHE, gens -> Group(gens));
AppendTo(progressFile, "Cache: ", Length(cacheK), " D_4^3 reps\n");

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
AppendTo(progressFile, "S_3^2 N-reps sizes: ", List(s3NReps, Size), "\n");

shifted := [
    ShiftGroup(TransitiveGroup(4,3), 0),
    ShiftGroup(TransitiveGroup(4,3), 4),
    ShiftGroup(TransitiveGroup(4,3), 8),
    ShiftGroup(TransitiveGroup(3,2), 12),
    ShiftGroup(TransitiveGroup(3,2), 15),
];
N_full := BuildPerComboNormalizer([4,4,4,3,3], shifted, 18);
AppendTo(progressFile, "|N_full| = ", Size(N_full), "\n");

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

AppendTo(progressFile, "Phase 1: Goursat generation...\n");
t0 := Runtime();
allCandidates := [];
for K in cacheK do
    nsK := NormalSubgroups(K);
    for Kprime in s3NReps do
        nsKprime := NormalSubgroups(Kprime);
        Append(allCandidates, GoursatGlue(K, Kprime, nsK, nsKprime));
    od;
od;
AppendTo(progressFile, "  Generated ", Length(allCandidates), " candidates in ",
    Int((Runtime()-t0)/1000), "s\n");

# Shuffle
allCandidates := Shuffle(allCandidates);
AppendTo(progressFile, "  Shuffled.\n");

# Dedup using the production rich invariant (ComputeSubgroupInvariant)
AppendTo(progressFile, "Phase 2: dedup with ComputeSubgroupInvariant (rich)...\n");
CURRENT_BLOCK_RANGES := [[1,4],[5,8],[9,12],[13,15],[16,18]];
t0 := Runtime();
tLast := Runtime();
raCount := 0;
raLast := 0;
byInv := rec();
deduped := [];
total := Length(allCandidates);
for _idxH in [1..total] do
    H := allCandidates[_idxH];
    inv := ComputeSubgroupInvariant(H);
    key := InvariantKey(inv);
    if IsBound(byInv.(key)) then
        isDup := false;
        for rep in byInv.(key) do
            raCount := raCount + 1;
            if RepresentativeAction(N_full, H, rep) <> fail then
                isDup := true; break;
            fi;
        od;
        if not isDup then
            Add(byInv.(key), H);
            Add(deduped, H);
        fi;
    else
        byInv.(key) := [H];
        Add(deduped, H);
    fi;
    if Runtime() - tLast > 60000 then
        AppendTo(progressFile, "    [dedup] ", _idxH, "/", total,
            " checked, ", Length(deduped), " unique, ",
            raCount - raLast, " RA in last 60s (",
            Int((Runtime() - t0) / 1000), "s total)\n");
        tLast := Runtime();
        raLast := raCount;
    fi;
od;
tDedup := Runtime() - t0;

AppendTo(progressFile, "=== RESULT ===\n");
AppendTo(progressFile, "Deduped: ", Length(deduped), "\n");
AppendTo(progressFile, "Target:  26956\n");
AppendTo(progressFile, "RA calls: ", raCount, "\n");
AppendTo(progressFile, "Dedup time: ", Int(tDedup/1000), "s\n");
if Length(deduped) = 26956 then
    AppendTo(progressFile, "EXACT MATCH!\n");
elif Length(deduped) > 26956 then
    AppendTo(progressFile, "Overcount by ", Length(deduped) - 26956, "\n");
else
    AppendTo(progressFile, "Undercount by ", 26956 - Length(deduped), "\n");
fi;

QUIT;
