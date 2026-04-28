LogTo("C:/Users/jeffr/Downloads/Lifting/test_d4_histogram.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n=== D_4^3 x S_3^2 histogram comparison ===\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/database/d4_cube_cache.g");
cacheK := List(D4_CUBE_CACHE, gens -> Group(gens));

# Get S_3^2 subdirects
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

# SIMPLE invariant - fast to compute
SimpleSig := function(H)
    local sz, orbBlk1, orbBlk2, orbBlk3, orbBlk4, orbBlk5, ai, dl;
    sz := Size(H);
    # Orbit sizes on each block
    orbBlk1 := SortedList(List(Orbits(H, [1..4]), Length));
    orbBlk2 := SortedList(List(Orbits(H, [5..8]), Length));
    orbBlk3 := SortedList(List(Orbits(H, [9..12]), Length));
    orbBlk4 := SortedList(List(Orbits(H, [13..15]), Length));
    orbBlk5 := SortedList(List(Orbits(H, [16..18]), Length));
    # Sort orbit patterns to be block-swap invariant
    ai := ShallowCopy(AbelianInvariants(H));
    Sort(ai);
    dl := DerivedLength(H);
    return [sz,
            SortedList([orbBlk1, orbBlk2, orbBlk3]),
            SortedList([orbBlk4, orbBlk5]),
            ai, dl];
end;

Print("Phase 1: Generate Goursat candidates...\n");
t0 := Runtime();
allCandidates := [];
for K in cacheK do
    nsK := NormalSubgroups(K);
    for Kprime in s3NReps do
        nsKprime := NormalSubgroups(Kprime);
        Append(allCandidates, GoursatGlue(K, Kprime, nsK, nsKprime));
    od;
od;
Print("  ", Length(allCandidates), " candidates in ", Int((Runtime()-t0)/1000), "s\n\n");

Print("Phase 2: Compute candidate simple-sig histogram...\n");
t0 := Runtime();
candHist := rec();
for i in [1..Length(allCandidates)] do
    key := String(SimpleSig(allCandidates[i]));
    if IsBound(candHist.(key)) then
        candHist.(key) := candHist.(key) + 1;
    else
        candHist.(key) := 1;
    fi;
    if i mod 10000 = 0 then
        Print("  ", i, "/", Length(allCandidates), " (",
              Int((Runtime()-t0)/1000), "s)\n");
    fi;
od;
Print("  Distinct candidate sigs: ", Length(RecNames(candHist)),
      " (", Int((Runtime()-t0)/1000), "s)\n\n");

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

Print("Phase 3: Compute target histogram and compare...\n");
t0 := Runtime();
targetHist := rec();
for i in [1..Length(targetGroups)] do
    key := String(SimpleSig(targetGroups[i]));
    if IsBound(targetHist.(key)) then
        targetHist.(key) := targetHist.(key) + 1;
    else
        targetHist.(key) := 1;
    fi;
    if i mod 5000 = 0 then
        Print("  ", i, "/", Length(targetGroups), "\n");
    fi;
od;
Print("  Distinct target sigs: ", Length(RecNames(targetHist)),
      " (", Int((Runtime()-t0)/1000), "s)\n\n");

# Compare histograms
Print("Phase 4: Compare histograms...\n");
coveredKeys := 0;
missingKeys := [];
insufficientKeys := 0;
for key in RecNames(targetHist) do
    if IsBound(candHist.(key)) then
        coveredKeys := coveredKeys + 1;
        if candHist.(key) < targetHist.(key) then
            insufficientKeys := insufficientKeys + 1;
        fi;
    else
        Add(missingKeys, [key, targetHist.(key)]);
    fi;
od;

Print("\n=== RESULT ===\n");
Print("Target keys: ", Length(RecNames(targetHist)), "\n");
Print("  covered:      ", coveredKeys, "\n");
Print("  missing:      ", Length(missingKeys), "\n");
Print("  insufficient: ", insufficientKeys, " (covered but count < target)\n");
if Length(missingKeys) > 0 then
    Print("\nFirst 5 missing keys:\n");
    for i in [1..Minimum(5, Length(missingKeys))] do
        Print("  ", missingKeys[i], "\n");
    od;
fi;

LogTo();
QUIT;
