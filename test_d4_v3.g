LogTo("C:/Users/jeffr/Downloads/Lifting/test_d4_v3.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n=== D_4^3 x S_3^2 verification v3 ===\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/database/d4_cube_cache.g");
cacheK := List(D4_CUBE_CACHE, gens -> Group(gens));

# S_3^2 subdirects (pre-computed from previous run: 3 of sizes 6, 18, 36)
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
Print("S_3^2 N-orbit reps: ", Length(s3NReps), " (sizes: ",
      List(s3NReps, Size), ")\n");

shifted := [
    ShiftGroup(TransitiveGroup(4,3), 0),
    ShiftGroup(TransitiveGroup(4,3), 4),
    ShiftGroup(TransitiveGroup(4,3), 8),
    ShiftGroup(TransitiveGroup(3,2), 12),
    ShiftGroup(TransitiveGroup(3,2), 15),
];
N_full := BuildPerComboNormalizer([4,4,4,3,3], shifted, 18);

# Goursat
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
Print("Generating candidates...\n");
t0 := Runtime();
allCandidates := [];
for K in cacheK do
    nsK := NormalSubgroups(K);
    for Kprime in s3NReps do
        nsKprime := NormalSubgroups(Kprime);
        Append(allCandidates, GoursatGlue(K, Kprime, nsK, nsKprime));
    od;
od;
Print("Total candidates: ", Length(allCandidates), " (",
      Int((Runtime()-t0)/1000), "s)\n\n");

# Index candidates by invariant
Print("Indexing candidates by invariant...\n");
CURRENT_BLOCK_RANGES := [[1,4],[5,8],[9,12],[13,15],[16,18]];
t0 := Runtime();
candByInv := rec();
for H in allCandidates do
    key := InvariantKey(CheapSubgroupInvariantFull(H));
    if not IsBound(candByInv.(key)) then candByInv.(key) := []; fi;
    Add(candByInv.(key), H);
od;
Print("Indexed in ", Int((Runtime()-t0)/1000), "s, ",
      Length(RecNames(candByInv)), " distinct keys\n\n");

# Load target groups
filepath := "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[4,4,4,3,3]/[3,2]_[3,2]_[4,3]_[4,3]_[4,3].g";
content := StringFile(filepath);
joined := "";
i := 1;
while i <= Length(content) do
    if i < Length(content) and content[i] = '\\' and content[i+1] = '\n' then
        i := i + 2;
    else Append(joined, [content[i]]); i := i + 1;
    fi;
od;
lines := SplitString(joined, "\n");
targetGroups := [];
for line in lines do
    if Length(line) > 0 and line[1] = '[' then
        gens := EvalString(line);
        if Length(gens) > 0 then Add(targetGroups, Group(gens)); fi;
    fi;
od;
Print("Loaded ", Length(targetGroups), " target groups\n\n");

# Sample 50 random targets and verify each matches a candidate
Print("Random sample verification (50 targets)...\n");
t0 := Runtime();
matched := 0;
unmatched := 0;
for i in [1..50] do
    targetIdx := Random(1, Length(targetGroups));
    T := targetGroups[targetIdx];
    tkey := InvariantKey(CheapSubgroupInvariantFull(T));
    if not IsBound(candByInv.(tkey)) then
        unmatched := unmatched + 1;
        Print("  target #", targetIdx, " |T|=", Size(T),
              " NO CANDIDATE WITH MATCHING INVARIANT\n");
    else
        bucket := candByInv.(tkey);
        found := false;
        for H in bucket do
            if RepresentativeAction(N_full, H, T) <> fail then
                found := true; break;
            fi;
        od;
        if found then
            matched := matched + 1;
        else
            unmatched := unmatched + 1;
            Print("  target #", targetIdx, " |T|=", Size(T),
                  " bucket size ", Length(bucket),
                  " — NO CONJUGATE FOUND\n");
        fi;
    fi;
od;
Print("\nMatched ", matched, "/50, unmatched ", unmatched, "/50 (",
      Int((Runtime()-t0)/1000), "s)\n");

LogTo();
QUIT;
