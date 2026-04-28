
LogTo("C:/Users/jeffr/Downloads/Lifting/test_gf2_dedup.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n=== TEST: GF(2) post-lift dedup on V_4^4 x C_2 (C_2^9) ===\n\n");

# Build the combo: [4,2]^4 x [2,1] for partition [4,4,4,4,2]
combo := [[4,2],[4,2],[4,2],[4,2],[2,1]];

# Build shifted factors
shifted := [];
offs := [];
pos := 0;
for c in combo do
    G := TransitiveGroup(c[1], c[2]);
    Add(shifted, ShiftGroup(G, pos));
    Add(offs, pos);
    pos := pos + c[1];
od;

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P = ", StructureDescription(P), ", |P| = ", Size(P), "\n");
Print("IsElementaryAbelian(P) = ", IsElementaryAbelian(P), "\n\n");

# Build partition normalizer for this combo
normGens := [];
for i in [1..Length(shifted)] do
    N_i := Normalizer(SymmetricGroup([offs[i]+1..offs[i]+combo[i][1]]), shifted[i]);
    Append(normGens, GeneratorsOfGroup(N_i));
od;
# Add block-swap generators for identical factors
for i in [1..Length(combo)-1] do
    for j in [i+1..Length(combo)] do
        if combo[i] = combo[j] then
            swapPerm := ();
            for k in [1..combo[i][1]] do
                swapPerm := swapPerm * (offs[i]+k, offs[j]+k);
            od;
            Add(normGens, swapPerm);
        fi;
    od;
od;
partNorm := Group(normGens);
Print("|partNorm| = ", Size(partNorm), "\n\n");

# === Lifting with GF(2) post-lift dedup ===
Print("=== Lifting + GF(2) post-lift dedup ===\n");
t0 := Runtime();
result := FindFPFClassesByLifting(P, shifted, offs, partNorm);
tLift := Runtime() - t0;
Print("\nResult: ", Length(result), " N-orbit reps in ", tLift, "ms (",
      Int(tLift/1000), "s)\n");

LogTo();
QUIT;
