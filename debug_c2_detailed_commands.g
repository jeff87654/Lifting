
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_c2_detailed_output.txt");
Print("Debug C2 optimization - detailed\n");
Print("=================================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Manually trace through the [4,2,2] case

Print("Setting up [4,2,2] partition:\n");
partition := [4, 2, 2];
transFactors := [SymmetricGroup(4), SymmetricGroup(2), SymmetricGroup(2)];

# Build shifted groups
shifted := [];
offsets := [];
off := 0;
for i in [1..3] do
    Add(offsets, off);
    Add(shifted, ShiftGroup(transFactors[i], off));
    off := off + NrMovedPoints(transFactors[i]);
od;

Print("Offsets: ", offsets, "\n");
Print("Shifted group sizes: ", List(shifted, Size), "\n\n");

# Count C2 factors
numC2 := 2;  # Last two factors
nonC2Start := 1;
k := numC2;

Print("numC2 = ", numC2, "\n");
Print("nonC2Start = ", nonC2Start, "\n\n");

# The mixed factor is just S4
mixed := shifted[1];
Print("Mixed factor (S4) size: ", Size(mixed), "\n");

# Get quotient maps
quotientInfo := GetQuotientMapsToC2(mixed);
r := quotientInfo.dimension;
kernels := quotientInfo.kernels;
Print("r (dimension of Hom(S4, C2)): ", r, "\n");
Print("Number of kernels: ", Length(kernels), "\n\n");

# Enumerate subspaces
Print("Enumerating subdirect subspaces of C2^", r+k, "...\n");
startTime := Runtime();
allSubspaces := EnumerateSubdirectSubspacesRplusK(r, k);
Print("Found ", Length(allSubspaces), " subspaces in ", (Runtime()-startTime)/1000.0, "s\n\n");

# Test building subdirects
Print("Building subdirects from each subspace...\n");
count := 0;
fpfCount := 0;
for subspace in allSubspaces do
    count := count + 1;
    Print("Subspace ", count, "/", Length(allSubspaces), ": ");

    startTime := Runtime();
    S := BuildSubdirectFromSubspace(mixed, kernels, subspace, shifted, offsets, k, nonC2Start);
    buildTime := (Runtime()-startTime)/1000.0;

    Print("Built group of size ", Size(S), " in ", buildTime, "s, ");

    startTime := Runtime();
    isFPF := IsFPFSubdirect(S, shifted, offsets);
    fpfTime := (Runtime()-startTime)/1000.0;

    Print("FPF check: ", isFPF, " in ", fpfTime, "s\n");

    if isFPF then
        fpfCount := fpfCount + 1;
    fi;
od;

Print("\nTotal FPF subdirects found: ", fpfCount, "\n");

Print("\n=================================\n");
Print("Debug Complete\n");
Print("=================================\n");
LogTo();
QUIT;
