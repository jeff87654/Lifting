LogTo("C:/Users/jeffr/Downloads/Lifting/explore_sn_fastpath.log");

# Goal: enumerate FPF subdirect products of P = S_n x H where H is a
# direct product of other transitive groups, using the Goursat lemma.
#
# For n >= 5, S_n has only 3 normal subgroups: {1}, A_n, S_n
# So there are very few common quotients with H.

Print("\n=== Fast path exploration for S_n combos ===\n\n");

# Case 1: [2,1] x [4,4] x [12,301] = C_2 x A_4 x S_12
# W151's stuck combo
n := 12;
S_n := TransitiveGroup(12, 301);
G2 := TransitiveGroup(4, 4);   # A_4
G3 := TransitiveGroup(2, 1);    # C_2
Print("S_12 = ", StructureDescription(S_n), ", |S_12| = ", Size(S_n), "\n");
Print("TG(4,4) = ", StructureDescription(G2), ", order ", Size(G2), "\n");
Print("TG(2,1) = ", StructureDescription(G3), ", order ", Size(G3), "\n");

H := DirectProduct(G2, G3);
Print("H = G2 x G3, order ", Size(H), " = ", StructureDescription(H), "\n\n");

# Normal subgroups
Print("Normal subgroups of S_12: {1}, A_12, S_12\n");

nsH := NormalSubgroups(H);
Print("Normal subgroups of H (", Length(nsH), " total):\n");
for N in nsH do
    Q := H / N;
    Print("  |N|=", Size(N), ", quotient = ", StructureDescription(Q),
          " (order ", Size(Q), ")\n");
od;

# Common quotients with S_12:
# S_12 has quotients: S_12 (order 479001600), C_2, {1}
# H has the quotients listed above
# Common: any quotient of both
Print("\nCommon quotients needed for Goursat gluing:\n");
Print("  S_12 quotients: {1}, C_2, S_12\n");
Print("  Need H to have each of these as a quotient\n\n");

# For Q = {1}: full direct product
Print("Q = {1}: full product S_12 x H, order ", Size(S_n) * Size(H), "\n");

# For Q = C_2: need N_H with H/N_H = C_2
idx2 := Filtered(nsH, N -> Size(H)/Size(N) = 2);
Print("Q = C_2: ", Length(idx2), " index-2 normal subgroups of H\n");
for N in idx2 do
    Print("  N_H of order ", Size(N), " = ", StructureDescription(N), "\n");
od;

# For Q = S_12: need N_H with H/N_H = S_12. Impossible since |H|=24 < |S_12|
Print("Q = S_12: impossible (|H| = 24 < |S_12|)\n\n");

Print("=> Total subdirect products for [2,1]x[4,4]x[12,301]: ");
Print(1 + Length(idx2), "\n");

LogTo();
QUIT;
