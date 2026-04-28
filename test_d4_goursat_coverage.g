LogTo("C:/Users/jeffr/Downloads/Lifting/test_d4_goursat_coverage.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n=== D_4^3 Goursat coverage test ===\n");
Print("Target: 26956 groups in [3,2]x[3,2]x[4,3]^3\n\n");

# Load D_4^3 cache
Read("C:/Users/jeffr/Downloads/Lifting/database/d4_cube_cache.g");
cache := List(D4_CUBE_CACHE, gens -> Group(gens));

# Build G_rest = S_3^2 on {13..18}
G_rest := Group([(13,14,15),(13,14),(16,17,18),(16,17)]);
Print("|G_rest| = ", Size(G_rest), "\n");
nsG := NormalSubgroups(G_rest);

# Build N_full
shifted := [
    ShiftGroup(TransitiveGroup(4,3), 0),
    ShiftGroup(TransitiveGroup(4,3), 4),
    ShiftGroup(TransitiveGroup(4,3), 8),
    ShiftGroup(TransitiveGroup(3,2), 12),
    ShiftGroup(TransitiveGroup(3,2), 15),
];
N_full := BuildPerComboNormalizer([4,4,4,3,3], shifted, 18);

# Load target groups from combo file
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
Print("Loaded ", Length(targetGroups), " target groups from combo file\n\n");

# Index target groups by invariant
Print("Indexing target groups by invariant...\n");
CURRENT_BLOCK_RANGES := [[1,4],[5,8],[9,12],[13,15],[16,18]];
t0 := Runtime();
targetByInv := rec();
for i in [1..Length(targetGroups)] do
    key := InvariantKey(CheapSubgroupInvariantFull(targetGroups[i]));
    if not IsBound(targetByInv.(key)) then
        targetByInv.(key) := [];
    fi;
    Add(targetByInv.(key), targetGroups[i]);
    if i mod 5000 = 0 then
        Print("  ", i, "/", Length(targetGroups), " indexed\n");
    fi;
od;
Print("Indexing done in ", Int((Runtime()-t0)/1000), "s, ",
      Length(RecNames(targetByInv)), " distinct invariant keys\n\n");

# Goursat gluing function
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

# Process each cache entry: generate candidates, check each against targets
Print("Processing cache entries...\n");
t0 := Runtime();
totalCandidates := 0;
totalMatched := 0;
targetMatched := rec();  # track which target groups have been matched
for i in [1..Length(cache)] do
    K := cache[i];
    nsK := NormalSubgroups(K);
    candidates := GoursatGlue(K, G_rest, nsK, nsG);
    totalCandidates := totalCandidates + Length(candidates);
    for H in candidates do
        key := InvariantKey(CheapSubgroupInvariantFull(H));
        if IsBound(targetByInv.(key)) then
            # Check if H is N-conjugate to any target in this bucket
            for T in targetByInv.(key) do
                if RepresentativeAction(N_full, H, T) <> fail then
                    targetMatched.(String(Position(targetGroups, T))) := true;
                    totalMatched := totalMatched + 1;
                    break;
                fi;
            od;
        fi;
    od;
    if i mod 25 = 0 then
        Print("  cache ", i, "/", Length(cache), ": ",
              totalCandidates, " candidates, ",
              Length(RecNames(targetMatched)), "/", Length(targetGroups),
              " targets matched (", Int((Runtime()-t0)/1000), "s)\n");
    fi;
od;

Print("\n=== RESULT ===\n");
Print("Cache entries processed: ", Length(cache), "\n");
Print("Total Goursat candidates: ", totalCandidates, "\n");
Print("Targets matched: ", Length(RecNames(targetMatched)), " / ", Length(targetGroups), "\n");
Print("Total matches (with multiplicity): ", totalMatched, "\n");
Print("Time: ", Int((Runtime()-t0)/1000), "s\n");

LogTo();
QUIT;
