LogTo("C:/Users/jeffr/Downloads/Lifting/verify_goursat_count.log");

# Ground truth: [2,1]x[4,3]x[12,301] produces 20 FPF classes via lifting.
# Let's directly enumerate subdirect products via Goursat and see if we
# actually get 20 or some other number.

Print("\n=== Verifying Goursat count for [2,1]x[4,3]x[12,301] ===\n\n");

# First, let's count in a smaller test case: S_5 x D_4 x C_2
# (same structure but with S_5 instead of S_12)
n := 5;
Sn := SymmetricGroup(n);
G2 := DihedralGroup(IsPermGroup, 8);  # D_4
G3 := SymmetricGroup(2);               # C_2
H := DirectProduct(G2, G3);

Print("Using S_", n, " x D_4 x C_2 as a smaller test\n");
Print("|S_n| = ", Size(Sn), ", |D_4| = ", Size(G2), ", |C_2| = ", Size(G3), "\n");
Print("|H| = |D_4 x C_2| = ", Size(H), "\n\n");

# Count via Goursat for (Sn, H):
# - N_S = Sn: 1 subdirect (full product)
# - N_S = A_n: one subdirect per index-2 normal subgroup of H
# - N_S = {1}: zero (impossible)
nsH := NormalSubgroups(H);
idx2 := Filtered(nsH, N -> Size(H)/Size(N) = 2);
Print("Goursat 2-factor count: 1 + ", Length(idx2), " = ", 1 + Length(idx2), "\n");
Print("  Index-2 normal subgroups of H:\n");
for N in idx2 do
    Print("    ", StructureDescription(N), " (order ", Size(N), ")\n");
od;

# Now count by direct enumeration using chief series lifting (the ground truth)
Print("\n--- Direct enumeration via NrTransitiveGroups analog ---\n");

# Build P = Sn x D_4 x C_2 as a perm group on n+4+2 = 11 points
# with Sn acting on [1..n], D_4 on [n+1..n+4], C_2 on [n+5..n+6]
# We need all subdirect products: subgroups projecting onto each factor.

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

shifted := [];
Add(shifted, SymmetricGroup(n));
Add(shifted, ShiftGroup(TransitiveGroup(4, 3), n));
Add(shifted, ShiftGroup(TransitiveGroup(2, 1), n + 4));

offs := [0, n, n + 4];

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("|P| = ", Size(P), "\n");

t0 := Runtime();
result := FindFPFClassesByLifting(P, shifted, offs);
tLift := Runtime() - t0;
Print("Lifting produced ", Length(result), " FPF classes in ", tLift, "ms\n");

LogTo();
QUIT;
