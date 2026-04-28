
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_c2_output.txt");
Print("Debug C2 optimization\n");
Print("======================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Test the quotient map computation for S4
Print("Testing GetQuotientMapsToC2 for S4:\n");
S4 := SymmetricGroup(4);
info := GetQuotientMapsToC2(S4);
Print("Dimension (r): ", info.dimension, "\n");
Print("Number of index-2 subgroups: ", Length(info.kernels), "\n\n");

# For [4,2,2], we have T = S4, k = 2 C2 factors
# So we need to enumerate subdirects of C2^r x C2^2
r := info.dimension;
k := 2;
Print("For [4,2,2]: r = ", r, ", k = ", k, "\n");
Print("Need to enumerate subdirects of C2^", r, " x C2^", k, " = C2^", r+k, "\n");
Print("Total space size: ", 2^(r+k), "\n");
Print("Number of non-zero vectors: ", 2^(r+k) - 1, "\n\n");

# The problem is that we're enumerating all Combinations of vectors
# For dim d subspaces, we check C(2^n-1, d) combinations
# For n=3 (r=1, k=2): C(7, 1) + C(7, 2) + C(7, 3) = 7 + 21 + 35 = 63 - manageable
# But we also need to check subdirect conditions

Print("Testing EnumerateSubdirectSubspacesRplusK(", r, ", ", k, "):\n");
startTime := Runtime();
subspaces := EnumerateSubdirectSubspacesRplusK(r, k);
elapsed := (Runtime() - startTime) / 1000.0;
Print("Found ", Length(subspaces), " subdirect subspaces in ", elapsed, " seconds\n\n");

# Now test with D4 (dihedral group of order 8)
Print("Testing GetQuotientMapsToC2 for D8 (dihedral):\n");
D8 := DihedralGroup(IsPermGroup, 8);
info := GetQuotientMapsToC2(D8);
Print("Dimension (r): ", info.dimension, "\n\n");

Print("======================\n");
Print("Debug Complete\n");
Print("======================\n");
LogTo();
QUIT;
