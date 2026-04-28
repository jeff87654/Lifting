LogTo("C:/Users/jeffr/Downloads/Lifting/test_nonsolvable_bug.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Reproduce the [5,5,2] bug.
# Ground truth: 62 FPF classes. Our code gives 61.
# The error "cannot compute complements if both N and G/N are nonsolvable"
# appears for combo [S_5, S_5, C_2] at an A_5 chief factor layer.

# Let's trace exactly what happens at the non-solvable layer.
# Build the product group for combo [TG(5,5), TG(5,5), TG(2,1)]
partition := [5,5,2];
factors := [TransitiveGroup(5,5), TransitiveGroup(5,5), TransitiveGroup(2,1)];
Print("Factors: ", List(factors, f -> [TransitiveIdentification(f), Size(f)]), "\n");

# Build shifted product
offsets := [0, 5, 10];
degree := 12;
shifted_factors := [];
for i in [1..3] do
    gens := List(GeneratorsOfGroup(factors[i]),
                 g -> PermList(Concatenation(
                     [1..offsets[i]],
                     List([1..partition[i]], x -> OnPoints(x, g) + offsets[i]),
                     [offsets[i]+partition[i]+1..degree])));
    Add(shifted_factors, Group(gens));
od;
P := Group(Concatenation(List(shifted_factors, GeneratorsOfGroup)));
Print("P = ", P, ", |P| = ", Size(P), "\n");

# Get chief series
series := RefinedChiefSeries(P);
Print("Chief series length: ", Length(series), "\n");
for i in [1..Length(series)-1] do
    Print("  Layer ", i, ": |M/N| = ", Size(series[i])/Size(series[i+1]),
          ", M_bar simple? ", IsSimpleGroup(series[i]/series[i+1]), "\n");
od;

# Now manually lift through layers, checking complement counts
current := [P];
for i in [1..Length(series)-1] do
    M := series[i];
    N := series[i+1];
    layerSize := Size(M)/Size(N);
    Print("\n=== Layer ", i, ": |M/N| = ", layerSize, " ===\n");
    Print("  ", Length(current), " parents entering\n");

    if layerSize > 4 then
        # This is a non-abelian simple layer - check complement computation
        Print("  NON-ABELIAN SIMPLE LAYER\n");
        for j in [1..Length(current)] do
            S := current[j];
            hom := NaturalHomomorphismByNormalSubgroup(S, N);
            Q := Image(hom);
            M_bar := Image(hom, M);
            Print("  Parent ", j, ": |Q| = ", Size(Q), ", |M_bar| = ", Size(M_bar), "\n");
            Print("    IsSolvable(M_bar) = ", IsSolvableGroup(M_bar), "\n");
            Print("    IsSolvable(Q/M_bar) = ", IsSolvableGroup(Q/M_bar), "\n");

            # Method 1: Our NonSolvableComplementClassReps
            t0 := Runtime();
            our_compls := NonSolvableComplementClassReps(Q, M_bar);
            t1 := Runtime() - t0;
            Print("    NonSolvableComplementClassReps: ", Length(our_compls), " complements (", t1, "ms)\n");

            # Method 2: Centralizer fast path
            C := Centralizer(Q, M_bar);
            Print("    Centralizer: |C| = ", Size(C), ", target = ", Size(Q)/Size(M_bar), "\n");
            if Size(C) = Size(Q)/Size(M_bar) and Size(Intersection(C, M_bar)) = 1 then
                Print("    Centralizer IS complement (direct factor)\n");
            else
                Print("    Centralizer NOT complement\n");
                # Method 3: Brute force via ConjugacyClassesSubgroups
                Print("    Trying brute force (CCS)...\n");
                t0 := Runtime();
                targetSize := Size(Q)/Size(M_bar);
                ccs := ConjugacyClassesSubgroups(Q);
                bf_compls := [];
                for cc in ccs do
                    H := Representative(cc);
                    if Size(H) = targetSize and Size(Intersection(H, M_bar)) = 1 then
                        Add(bf_compls, H);
                    fi;
                od;
                t1 := Runtime() - t0;
                Print("    Brute force: ", Length(bf_compls), " complement classes (", t1, "ms)\n");

                if Length(bf_compls) <> Length(our_compls) then
                    Print("    *** MISMATCH! Our=", Length(our_compls), " BF=", Length(bf_compls), " ***\n");
                fi;
            fi;
        od;
    fi;

    # Actually lift through the layer using LiftThroughLayer
    current := LiftThroughLayer(P, M, N, current, shifted_factors, offsets, fail);
    Print("  After lifting: ", Length(current), " subgroups\n");
od;

Print("\n=== Final: ", Length(current), " subgroups ===\n");

# Now check FPF
fpf := Filtered(current, K -> IsFPFSubdirect(K, shifted_factors));
Print("FPF: ", Length(fpf), "\n");

# Dedup under P
unique := [];
byInv := rec();
for H in fpf do
    key := String(Size(H));
    if not IsBound(byInv.(key)) then byInv.(key) := []; fi;
    isDupe := false;
    for K in byInv.(key) do
        if RepresentativeAction(P, K, H) <> fail then isDupe := true; break; fi;
    od;
    if not isDupe then Add(byInv.(key), H); Add(unique, H); fi;
od;
Print("Unique FPF under P: ", Length(unique), "\n");
Print("Expected: should contribute to total of 62\n");

LogTo();
QUIT;
