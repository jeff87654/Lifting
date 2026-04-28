
LogTo("C:/Users/jeffr/Downloads/Lifting/profile_parent9_full.log");

USE_GENERAL_AUT_HOM := true;
GENERAL_AUT_HOM_VERBOSE := true;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/diag_combo6_v3_allcalls.g");

# Find a |Q|=115200 GAH record to use as test case.
big := Filtered(GAH_ALL_CALLS, r -> r.source = "GAH" and r.Q_size = 115200);
Print("[full] testing on first |Q|=115200 record\n\n");

r := big[1];
S := Group(r.Q_gens);  # Q = S/1 = S in our case (N=1 at last layer)
M := Group(r.M_bar_gens);
SetSize(S, r.Q_size);
SetSize(M, r.M_bar_size);

# Reconstruct partition for combo 6
T5 := TransitiveGroup(5, 5);;
T2 := TransitiveGroup(2, 1);;
factors := [T5, T5, T2, T2, T2, T2];;
partition := [5, 5, 2, 2, 2, 2];;
shifted := [];
offsets := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offsets, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;

# Step 1: Centralizer
Print("[full] === Centralizer ===\n");
t0 := Runtime();
C := Centralizer(S, M);
Print("[full] Centralizer in ", Runtime()-t0, "ms |C|=", Size(C), "\n\n");

# Step 2: NormalSubgroupsBetween
Print("[full] === NormalSubgroupsBetween ===\n");
t0 := Runtime();
N := TrivialSubgroup(S);
nbs := NormalSubgroupsBetween(S, M, N);
Print("[full] NormalSubgroupsBetween in ", Runtime()-t0, "ms (", Length(nbs),
      " between)\n\n");

# Step 3: Build hom S -> S/N (identity for N=trivial)
Print("[full] === Build hom ===\n");
t0 := Runtime();
hom := SafeNaturalHomByNSG(S, N);
Q := ImagesSource(hom);
M_bar := Image(hom, M);
Print("[full] hom in ", Runtime()-t0, "ms |Q|=", Size(Q),
      " |M_bar|=", Size(M_bar), "\n\n");

# Step 4: Full GAH call
Print("[full] === GAH ===\n");
t0 := Runtime();
gah := GeneralAutHomComplements(Q, M_bar, C);
Print("[full] GAH ", Length(gah), " complements in ", Runtime()-t0, "ms\n\n");

# Step 5: Post-GAH PreImages + FPF check (what the lifting code does after GAH)
Print("[full] === PreImages + FPF check (per complement) ===\n");
t0 := Runtime();
fpf_count := 0;
for C_bar in gah do
    C_lifted := PreImages(hom, C_bar);
    if IsFPFSubdirect(C_lifted, shifted, offsets) then
        fpf_count := fpf_count + 1;
    fi;
od;
Print("[full] PreImages+FPF for ", Length(gah), " complements in ",
      Runtime()-t0, "ms (", fpf_count, " FPF)\n\n");

LogTo();
QUIT;
