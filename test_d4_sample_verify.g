LogTo("C:/Users/jeffr/Downloads/Lifting/test_d4_sample_verify.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n=== D_4^3 Goursat sample verification ===\n");
Print("Pick 50 random target groups, verify each matches a Goursat candidate\n\n");

# Load cache and build infrastructure
Read("C:/Users/jeffr/Downloads/Lifting/database/d4_cube_cache.g");
cache := List(D4_CUBE_CACHE, gens -> Group(gens));
G_rest := Group([(13,14,15),(13,14),(16,17,18),(16,17)]);
nsG := NormalSubgroups(G_rest);
shifted := [
    ShiftGroup(TransitiveGroup(4,3), 0),
    ShiftGroup(TransitiveGroup(4,3), 4),
    ShiftGroup(TransitiveGroup(4,3), 8),
    ShiftGroup(TransitiveGroup(3,2), 12),
    ShiftGroup(TransitiveGroup(3,2), 15),
];
N_full := BuildPerComboNormalizer([4,4,4,3,3], shifted, 18);
Print("|cache|=", Length(cache), ", |G_rest|=", Size(G_rest),
      ", |N_full|=", Size(N_full), "\n\n");

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

# Pre-compute ALL Goursat candidates (60K)
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

Print("Generating all Goursat candidates...\n");
t0 := Runtime();
allCandidates := [];
for K in cache do
    nsK := NormalSubgroups(K);
    Append(allCandidates, GoursatGlue(K, G_rest, nsK, nsG));
od;
Print("Generated ", Length(allCandidates), " in ", Int((Runtime()-t0)/1000), "s\n\n");

# Pick 50 random target groups and verify each matches a candidate
CURRENT_BLOCK_RANGES := [[1,4],[5,8],[9,12],[13,15],[16,18]];
Print("Random sample verification...\n");
sampleSize := 50;
matched := 0;
unmatched := 0;
t0 := Runtime();
for i in [1..sampleSize] do
    targetIdx := Random(1, Length(targetGroups));
    T := targetGroups[targetIdx];
    T_inv_key := InvariantKey(CheapSubgroupInvariantFull(T));
    T_size := Size(T);

    # Scan candidates for a match
    foundMatch := false;
    for H in allCandidates do
        if Size(H) = T_size then
            if InvariantKey(CheapSubgroupInvariantFull(H)) = T_inv_key then
                if RepresentativeAction(N_full, H, T) <> fail then
                    foundMatch := true;
                    break;
                fi;
            fi;
        fi;
    od;

    if foundMatch then
        matched := matched + 1;
    else
        unmatched := unmatched + 1;
        Print("  target #", targetIdx, " NOT MATCHED (|T|=", Size(T), ")\n");
    fi;

    if i mod 10 = 0 then
        Print("  sample ", i, "/", sampleSize, ": ", matched, " matched, ",
              unmatched, " unmatched (", Int((Runtime()-t0)/1000), "s)\n");
    fi;
od;

Print("\n=== RESULTS ===\n");
Print("Matched: ", matched, "/", sampleSize, "\n");
Print("Unmatched: ", unmatched, "/", sampleSize, "\n");
if unmatched = 0 then
    Print("SUCCESS — coverage looks good\n");
fi;

LogTo();
QUIT;
