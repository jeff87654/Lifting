LogTo("C:/Users/jeffr/Downloads/Lifting/test_option_b_w214.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n=== Option B test: [2,1]^3 x [4,3]^3 combo ===\n");
Print("Partition [4,4,4,2,2,2], worker 214's current monster\n\n");

# Build the combo
combo := [[2,1], [2,1], [2,1], [4,3], [4,3], [4,3]];
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
Print("|P| = ", Size(P), "\n");

# Build per-combo normalizer (same as worker would)
partition := [4,4,4,2,2,2];
normArg := BuildPerComboNormalizer(partition, shifted, 18);
Print("|N| (per-combo) = ", Size(normArg), "\n\n");

Print("USE_RICH_INTERLAYER_INV = ", USE_RICH_INTERLAYER_INV, "\n\n");

t0 := Runtime();
result := FindFPFClassesByLifting(P, shifted, offs, normArg);
tTotal := Runtime() - t0;

Print("\n=== RESULT ===\n");
Print("Final candidate count: ", Length(result), "\n");
Print("Total time: ", tTotal, "ms (", Int(tTotal/1000), "s)\n");

LogTo();
QUIT;
