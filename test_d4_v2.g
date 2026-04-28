LogTo("C:/Users/jeffr/Downloads/Lifting/test_d4_v2.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n=== D_4^3 x S_3^2 subdirect test (fixed) ===\n\n");

# Load D_4^3 cache
Read("C:/Users/jeffr/Downloads/Lifting/database/d4_cube_cache.g");
cacheK := List(D4_CUBE_CACHE, gens -> Group(gens));
Print("|cache K (D_4^3)|=", Length(cacheK), "\n");

# Step 1: enumerate S_3^2 subdirects on {13..18}
S3a := Group([(13,14,15),(13,14)]);
S3b := Group([(16,17,18),(16,17)]);
S3sq := Group(Concatenation(GeneratorsOfGroup(S3a), GeneratorsOfGroup(S3b)));

# Brute force: enumerate all subgroups of S_3^2 projecting onto each S_3
subsS3sq := List(ConjugacyClassesSubgroups(S3sq), Representative);
Print("|subgroups(S_3^2)|=", Length(subsS3sq), "\n");

s3Subdirects := [];
for H in subsS3sq do
    g_a := Filtered(List(GeneratorsOfGroup(H), g -> RestrictedPerm(g, [13..15])),
                    x -> x <> ());
    g_b := Filtered(List(GeneratorsOfGroup(H), g -> RestrictedPerm(g, [16..18])),
                    x -> x <> ());
    if Length(g_a) > 0 and Length(g_b) > 0 and
       Size(Group(g_a)) = 6 and Size(Group(g_b)) = 6 then
        Add(s3Subdirects, H);
    fi;
od;
Print("|S_3^2 subdirects|=", Length(s3Subdirects), "\n");

# Dedup under N_[3,3]
N33 := Group([(13,14,15),(13,14),(16,17,18),(16,17),(13,16)(14,17)(15,18)]);
Print("|N_[3,3]|=", Size(N33), "\n");

s3NReps := [];
for H in s3Subdirects do
    found := false;
    for K in s3NReps do
        if Size(K) = Size(H) then
            if RepresentativeAction(N33, H, K) <> fail then
                found := true; break;
            fi;
        fi;
    od;
    if not found then Add(s3NReps, H); fi;
od;
Print("|S_3^2 subdirects under N_[3,3]|=", Length(s3NReps), "\n");
for H in s3NReps do
    Print("  |K'|=", Size(H), "\n");
od;
Print("\n");

# Step 2: Goursat gluing of each (K in cache, K' in s3NReps) pair
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

Print("Generating Goursat candidates (K, K') pairs...\n");
t0 := Runtime();
allCandidates := [];
for K_idx in [1..Length(cacheK)] do
    K := cacheK[K_idx];
    nsK := NormalSubgroups(K);
    for Kprime in s3NReps do
        nsKprime := NormalSubgroups(Kprime);
        Append(allCandidates, GoursatGlue(K, Kprime, nsK, nsKprime));
    od;
    if K_idx mod 50 = 0 then
        Print("  K ", K_idx, "/", Length(cacheK), ": ",
              Length(allCandidates), " candidates (",
              Int((Runtime()-t0)/1000), "s)\n");
    fi;
od;
Print("Total candidates: ", Length(allCandidates), " (",
      Int((Runtime()-t0)/1000), "s)\n\n");

Print("Size distribution (first 20 sizes):\n");
sizes := SortedList(List(allCandidates, Size));
Print("  min=", Minimum(sizes), ", max=", Maximum(sizes), "\n");

# Check if size 384 is present
has384 := 384 in sizes;
Print("  384 present? ", has384, "\n");

LogTo();
QUIT;
