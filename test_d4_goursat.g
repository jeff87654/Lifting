LogTo("C:/Users/jeffr/Downloads/Lifting/test_d4_goursat.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n=== D_4^3 cache + Goursat gluing with S_3^2 ===\n");
Print("Target: [3,2]x[3,2]x[4,3]x[4,3]x[4,3] combo, expected 26956 classes\n\n");

# Load D_4^3 cache
Read("C:/Users/jeffr/Downloads/Lifting/database/d4_cube_cache.g");
cache := List(D4_CUBE_CACHE, gens -> Group(gens));
Print("Loaded ", Length(cache), " D_4^3 reps\n");

# Build G = S_3^2 on {13..18}
G_rest := Group([
    (13,14,15), (13,14),  # S_3 on {13,14,15}
    (16,17,18), (16,17)   # S_3 on {16,17,18}
]);
Print("|G_rest| = |S_3^2| = ", Size(G_rest), "\n");

# Build full partition normalizer N = N_[4,4,4,3,3]
partition := [4,4,4,3,3];
shifted := [
    ShiftGroup(TransitiveGroup(4,3), 0),
    ShiftGroup(TransitiveGroup(4,3), 4),
    ShiftGroup(TransitiveGroup(4,3), 8),
    ShiftGroup(TransitiveGroup(3,2), 12),
    ShiftGroup(TransitiveGroup(3,2), 15),
];
N_full := BuildPerComboNormalizer(partition, shifted, 18);
Print("|N_full| = ", Size(N_full), "\n\n");

# Enumerate normal subgroups of G_rest once
nsG := NormalSubgroups(G_rest);
Print("|NS(G_rest)| = ", Length(nsG), "\n\n");

# Goursat gluing function:
# Given K (on {1..12}) and G (on {13..18}), enumerate all subdirect products
# H <= K x G by iterating over (N_K, N_G, phi) Goursat triples.
GoursatGlue := function(K, G, nsK, nsG_list)
    local results, N_K, N_G, Q_K_size, hom_K, hom_G, Q_K, Q_G, iso,
          aut_group, a, phi, gens, gen_K, coset_K, target_coset, g_rep;
    results := [];
    for N_K in nsK do
        Q_K_size := Size(K) / Size(N_K);
        hom_K := NaturalHomomorphismByNormalSubgroup(K, N_K);
        Q_K := ImagesSource(hom_K);
        for N_G in nsG_list do
            if Size(G) / Size(N_G) <> Q_K_size then continue; fi;
            hom_G := NaturalHomomorphismByNormalSubgroup(G, N_G);
            Q_G := ImagesSource(hom_G);
            iso := IsomorphismGroups(Q_K, Q_G);
            if iso = fail then continue; fi;
            # Enumerate all isomorphisms = iso composed with Aut(Q_K)
            if Q_K_size = 1 then
                # Trivial case: just one isomorphism
                gens := Concatenation(GeneratorsOfGroup(K), GeneratorsOfGroup(G));
                Add(results, Group(gens));
            else
                aut_group := AutomorphismGroup(Q_K);
                for a in aut_group do
                    phi := a * iso;  # composition: first a, then iso
                    # Build H: for each gen of K, pair with pre-image of its image in G
                    gens := [];
                    Append(gens, GeneratorsOfGroup(N_K));  # these project trivially in K/N_K
                    Append(gens, GeneratorsOfGroup(N_G));  # these project trivially in G/N_G
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

# For each cache entry, Goursat-glue with G_rest
Print("Running Goursat gluing...\n");
t0 := Runtime();
allResults := [];
for i in [1..Length(cache)] do
    K := cache[i];
    nsK := NormalSubgroups(K);
    glued := GoursatGlue(K, G_rest, nsK, nsG);
    Append(allResults, glued);
    if i mod 50 = 0 then
        Print("  cache ", i, "/", Length(cache), ": ", Length(allResults),
              " candidates so far (", Int((Runtime()-t0)/1000), "s)\n");
    fi;
od;
tGlue := Runtime() - t0;
Print("Generated ", Length(allResults), " raw candidates in ", tGlue, "ms\n\n");

# Dedup under N_full
Print("Deduping under N_full (", Length(allResults), " candidates)...\n");
t0 := Runtime();
tLast := Runtime();
raCount := 0;
raLast := 0;
CURRENT_BLOCK_RANGES := [[1,4],[5,8],[9,12],[13,15],[16,18]];
byInv := rec();
deduped := [];
for _idxH in [1..Length(allResults)] do
    H := allResults[_idxH];
    inv := CheapSubgroupInvariantFull(H);
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
    if Runtime() - tLast > 30000 then
        Print("    [dedup] ", _idxH, "/", Length(allResults),
              " checked, ", Length(deduped), " unique, ",
              raCount - raLast, " RA (",
              Int((Runtime() - t0) / 1000), "s total)\n");
        tLast := Runtime();
        raLast := raCount;
    fi;
od;
tDedup := Runtime() - t0;
Print("Deduped: ", Length(deduped), " unique in ", Int(tDedup/1000), "s, ",
      raCount, " total RA calls\n\n");

Print("=== RESULT ===\n");
Print("Got:      ", Length(deduped), "\n");
Print("Expected: 26956\n");
if Length(deduped) = 26956 then
    Print("MATCH!\n");
else
    Print("MISMATCH (diff = ", 26956 - Length(deduped), ")\n");
fi;

LogTo();
QUIT;
