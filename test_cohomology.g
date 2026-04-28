###############################################################################
#
# test_cohomology.g - Test Suite for H^1 Cohomology Functions
#
# Tests the cohomology computations against known results and compares
# with GAP's built-in ComplementClassesRepresentatives.
#
###############################################################################

# Load required modules
Read("C:/Users/jeffr/Downloads/Lifting/cohomology.g");
Read("C:/Users/jeffr/Downloads/Lifting/modules.g");

###############################################################################
# Test Utilities
###############################################################################

TestCount := 0;
PassCount := 0;
FailCount := 0;

StartTest := function(name)
    TestCount := TestCount + 1;
    Print("\n[Test ", TestCount, "] ", name, "\n");
    Print(String(ListWithIdenticalEntries(60, '-')), "\n");
end;

AssertEqual := function(actual, expected, description)
    if actual = expected then
        Print("  PASS: ", description, "\n");
        PassCount := PassCount + 1;
        return true;
    else
        Print("  FAIL: ", description, "\n");
        Print("    Expected: ", expected, "\n");
        Print("    Actual:   ", actual, "\n");
        FailCount := FailCount + 1;
        return false;
    fi;
end;

PrintSummary := function()
    Print("\n");
    Print("==========================================================\n");
    Print("Test Summary: ", PassCount, " passed, ", FailCount, " failed out of ", TestCount, " tests\n");
    Print("==========================================================\n");
end;

###############################################################################
# Test 1: Trivial action - C3 acting on (C2)^2
#
# G = C3, M = (Z/2Z)^2 with trivial action (all matrices are identity).
# H^1(G, M) = Hom(G, M) for trivial action.
# Since G = C3 and M is a 2-group, Hom(C3, M) = 0.
# Therefore H^1 = 0, meaning there's exactly 1 complement class.
###############################################################################

TestTrivialActionC3 := function()
    local G, C3part, M, p, comps, gapComps;

    StartTest("Trivial action: C3 on (C2)^2");

    # Create semidirect product with trivial action: C3 x (C2)^2
    G := DirectProduct(CyclicGroup(3), DirectProduct(CyclicGroup(2), CyclicGroup(2)));

    # Get the (C2)^2 normal subgroup
    M := Image(Embedding(G, 2));

    Print("  |G| = ", Size(G), ", |M| = ", Size(M), "\n");

    p := 2;

    # Use GetComplementsViaH1 which handles the quotient properly
    comps := GetComplementsViaH1(G, M);

    Print("  Found ", Length(comps), " complement class(es)\n");

    # Compare with GAP
    gapComps := ComplementClassesRepresentatives(G, M);
    Print("  GAP finds ", Length(gapComps), " complement class(es)\n");

    AssertEqual(Length(comps), Length(gapComps), "Matches GAP's ComplementClassesRepresentatives");
    AssertEqual(Length(comps), 1, "Exactly 1 complement class for coprime C3 on (C2)^2");

    return Length(comps) = 1;
end;

###############################################################################
# Test 2: C2 with trivial action on C2
#
# G = C2, M = C2 with trivial action.
# H^1(G, M) = Hom(G, M) = Hom(C2, C2) = C2.
# Therefore dim H^1 = 1, and there are 2 complement classes.
###############################################################################

TestTrivialActionC2onC2 := function()
    local G, M, p, comps, gapComps;

    StartTest("Trivial action: C2 on C2");

    # Create direct product C2 x C2
    G := DirectProduct(CyclicGroup(2), CyclicGroup(2));
    M := Image(Embedding(G, 2));  # Second factor is the module

    Print("  |G| = ", Size(G), ", |M| = ", Size(M), "\n");

    p := 2;

    # Use GetComplementsViaH1 which handles the quotient properly
    comps := GetComplementsViaH1(G, M);

    Print("  Found ", Length(comps), " complement class(es)\n");

    # Compare with GAP
    gapComps := ComplementClassesRepresentatives(G, M);
    Print("  GAP finds ", Length(gapComps), " complement class(es)\n");

    AssertEqual(Length(comps), Length(gapComps), "Matches GAP's ComplementClassesRepresentatives");
    # For C2 x C2, there are 2 complement classes (the two "diagonal" C2 subgroups)
    AssertEqual(Length(comps), 2, "2 complement classes for C2 x C2");

    return Length(comps) = 2;
end;

###############################################################################
# Test 3: S3 conjugation action on C3
#
# G = S3, M = C3 (the normal Sylow 3-subgroup of S3).
# S3 acts on C3 by conjugation (nontrivial action by C2 part).
# For this action, H^1(S3, C3) = 0.
# There's exactly 1 complement (the Sylow 2-subgroup is the unique complement).
###############################################################################

TestS3onC3 := function()
    local S3, M, G, p, module, H1, comps;

    StartTest("S3 conjugation action on C3");

    S3 := SymmetricGroup(3);
    M := SylowSubgroup(S3, 3);  # The normal C3

    Print("  |S3| = ", Size(S3), ", |M| = ", Size(M), "\n");

    p := 3;

    # Create module from S3 acting on M = C3 by conjugation
    # But we need Q/M acting on M, so form the quotient
    # Actually, for S3 with M = C3, Q = S3 and G = S3/C3 = C2

    # Use GetComplementsViaH1 which handles the quotient construction
    comps := GetComplementsViaH1(S3, M);

    Print("  Found ", Length(comps), " complement class(es)\n");

    # Verify against GAP's built-in
    if IsSolvableGroup(S3) then
        AssertEqual(Length(comps), Length(ComplementClassesRepresentatives(S3, M)),
                    "Matches ComplementClassesRepresentatives");
    fi;

    AssertEqual(Length(comps), 1, "Exactly 1 complement class for S3");

    return Length(comps) = 1;
end;

###############################################################################
# Test 4: D8 with V4 normal subgroup
#
# G = D8 (dihedral group of order 8), M = V4 (Klein four-group, center of D8).
# D8/V4 = C2. The action of C2 on V4 by conjugation has H^1 nonzero.
# There should be 2 conjugacy classes of complements.
###############################################################################

TestD8onV4 := function()
    local D8, M, comps, gapComps;

    StartTest("D8 with V4 normal subgroup");

    D8 := DihedralGroup(8);

    # Find the normal V4 subgroup (order 4, elementary abelian)
    M := First(NormalSubgroups(D8), N -> Size(N) = 4 and IsElementaryAbelian(N));

    if M = fail then
        # D8 might not have V4, try with C2 (derived subgroup)
        M := DerivedSubgroup(D8);
    fi;

    Print("  |D8| = ", Size(D8), ", |M| = ", Size(M), "\n");

    if not IsElementaryAbelian(M) then
        Print("  SKIP: Could not find elementary abelian normal subgroup\n");
        return true;
    fi;

    # Get GAP's complement count
    gapComps := ComplementClassesRepresentatives(D8, M);
    Print("  GAP finds ", Length(gapComps), " complement class(es)\n");

    # If D8/M has order coprime to |M|, there's exactly 1 complement
    if Gcd(Size(D8)/Size(M), Size(M)) = 1 then
        Print("  (Coprime case: expecting 1 complement)\n");
    fi;

    comps := GetComplementsViaH1(D8, M);
    Print("  H^1 method found ", Length(comps), " complement class(es)\n");

    AssertEqual(Length(comps), Length(gapComps), "Matches ComplementClassesRepresentatives");

    return Length(comps) = Length(gapComps);
end;

###############################################################################
# Test 5: Comparison tests on small groups
#
# Test various small groups and compare complement counts.
###############################################################################

TestSmallGroupComparison := function(ordG, idG)
    local G, normals, M, compsH1, compsGAP;

    StartTest(Concatenation("SmallGroup(", String(ordG), ", ", String(idG), ")"));

    G := SmallGroup(ordG, idG);
    Print("  |G| = ", Size(G), "\n");

    # Find elementary abelian normal subgroups
    normals := Filtered(NormalSubgroups(G), N ->
        Size(N) > 1 and Size(N) < Size(G) and IsElementaryAbelian(N));

    if Length(normals) = 0 then
        Print("  SKIP: No proper elementary abelian normal subgroups\n");
        return true;
    fi;

    M := normals[1];  # Test with first one
    Print("  Testing with |M| = ", Size(M), "\n");

    compsH1 := GetComplementsViaH1(G, M);
    compsGAP := ComplementClassesRepresentatives(G, M);

    Print("  H^1 method: ", Length(compsH1), " complements\n");
    Print("  GAP method: ", Length(compsGAP), " complements\n");

    return AssertEqual(Length(compsH1), Length(compsGAP),
                      "Complement count matches GAP");
end;

###############################################################################
# Test 6: Direct test of cocycle space computation
#
# For G = C2, M = C2 with trivial action:
# - Z^1 should have dimension 1 (one generator, no relations except g^2=1)
# - B^1 should have dimension 0 (trivial action means e^g - e = 0)
# - H^1 = Z^1/B^1 has dimension 1
###############################################################################

TestCocycleSpaceDirectly := function()
    local G, M, p, module, Z1, B1;

    StartTest("Direct cocycle space computation (C2 trivial on C2)");

    G := CyclicGroup(2);
    M := CyclicGroup(2);

    p := 2;
    module := rec(
        p := p,
        dimension := 1,
        field := GF(p),
        group := G,
        generators := GeneratorsOfGroup(G),
        matrices := [IdentityMat(1, GF(p))],  # Trivial action
        pcgsM := Pcgs(M),
        moduleGroup := M
    );

    Z1 := ComputeCocycleSpace(module);
    B1 := ComputeCoboundarySpace(module);

    Print("  dim Z^1 = ", Length(Z1), "\n");
    Print("  dim B^1 = ", Length(B1), "\n");
    Print("  dim H^1 = ", Length(Z1) - Length(B1), "\n");

    AssertEqual(Length(B1), 0, "B^1 = 0 for trivial action");
    AssertEqual(Length(Z1), 1, "Z^1 has dimension 1");

    return Length(Z1) - Length(B1) = 1;
end;

###############################################################################
# Test 7: Test on A4 with V4
#
# A4 has V4 as normal subgroup, quotient is C3.
# C3 acts on V4 = (C2)^2 by cycling the three nontrivial elements.
# H^1(C3, V4) = 0 since p=2 doesn't divide |C3|=3.
###############################################################################

TestA4onV4 := function()
    local A4, V4, comps;

    StartTest("A4 with V4 normal subgroup");

    A4 := AlternatingGroup(4);

    # V4 is the unique normal subgroup of order 4 in A4
    V4 := First(NormalSubgroups(A4), N -> Size(N) = 4);

    Print("  |A4| = ", Size(A4), ", |V4| = ", Size(V4), "\n");

    comps := GetComplementsViaH1(A4, V4);

    Print("  Found ", Length(comps), " complement class(es)\n");

    # A4 = V4 ⋊ C3, and the action gives H^1 = 0
    AssertEqual(Length(comps), 1, "Exactly 1 complement class (coprime case)");

    return Length(comps) = 1;
end;

###############################################################################
# Test 8: Elementary abelian 2^3 as module for S3
#
# S3 acting on (C2)^3 via permutation of coordinates.
###############################################################################

TestS3onC2cubed := function()
    local S3, C2, M, G, gens, matrices, g, perm, mat, i, j, module, H1;

    StartTest("S3 permutation action on (C2)^3");

    S3 := SymmetricGroup(3);
    M := DirectProduct(CyclicGroup(2), CyclicGroup(2), CyclicGroup(2));

    Print("  |S3| = ", Size(S3), ", |M| = ", Size(M), "\n");

    # Build permutation representation matrices
    gens := [(1,2,3), (1,2)];
    matrices := [];

    for g in gens do
        mat := NullMat(3, 3, GF(2));
        # Permutation matrix: row i gets a 1 in column i^g
        for i in [1..3] do
            j := i^g;
            mat[i][j] := One(GF(2));
        od;
        Add(matrices, mat);
    od;

    module := rec(
        p := 2,
        dimension := 3,
        field := GF(2),
        group := Group(gens),
        generators := gens,
        matrices := matrices,
        pcgsM := Pcgs(M),
        moduleGroup := M
    );

    H1 := ComputeH1(module);
    PrintH1Summary(H1);

    # For permutation action of S3 on (C2)^3:
    # dim Z^1 and dim B^1 can be computed from representation theory
    Print("  This is a permutation module test\n");

    return true;  # Manual verification needed
end;

###############################################################################
# Test 9: Verify complement construction
#
# Check that CocycleToComplement actually produces valid complements.
###############################################################################

TestComplementConstruction := function()
    local G, M, module, H1, complementInfo, comps, C, inter, i;

    StartTest("Complement construction verification");

    # Use S3 with C3
    G := SymmetricGroup(3);
    M := SylowSubgroup(G, 3);

    Print("  Testing with S3 and C3\n");

    module := ChiefFactorAsModule(G, M, TrivialSubgroup(M));
    H1 := ComputeH1(module);
    complementInfo := BuildComplementInfo(G, M, module);

    comps := EnumerateComplementsFromH1(H1, complementInfo);

    for i in [1..Length(comps)] do
        C := comps[i];

        # Check complement properties
        if Size(C) * Size(M) <> Size(G) then
            Print("  FAIL: |C| * |M| != |G| for complement ", i, "\n");
            return false;
        fi;

        inter := Intersection(C, M);
        if Size(inter) <> 1 then
            Print("  FAIL: C ∩ M != 1 for complement ", i, "\n");
            return false;
        fi;

        Print("  Complement ", i, ": |C| = ", Size(C), ", valid\n");
    od;

    Print("  All complements valid!\n");
    return true;
end;

###############################################################################
# Test 10: Batch comparison with ComplementClassesRepresentatives
###############################################################################

TestBatchComparison := function()
    local testCases, tc, G, M, compsH1, compsGAP, allPassed;

    StartTest("Batch comparison with GAP");

    testCases := [
        [SymmetricGroup(3), SylowSubgroup(SymmetricGroup(3), 3), "S3, C3"],
        [SymmetricGroup(4), First(NormalSubgroups(SymmetricGroup(4)),
            N -> Size(N) = 4), "S4, V4"],
        [AlternatingGroup(4), First(NormalSubgroups(AlternatingGroup(4)),
            N -> Size(N) = 4), "A4, V4"]
    ];

    allPassed := true;

    for tc in testCases do
        G := tc[1];
        M := tc[2];

        if M = fail or not IsElementaryAbelian(M) then
            Print("  SKIP: ", tc[3], " - no suitable M\n");
            continue;
        fi;

        Print("  Testing ", tc[3], "...\n");

        compsH1 := GetComplementsViaH1(G, M);
        compsGAP := ComplementClassesRepresentatives(G, M);

        if Length(compsH1) = Length(compsGAP) then
            Print("    PASS: ", Length(compsH1), " complements\n");
        else
            Print("    FAIL: H1=", Length(compsH1), ", GAP=", Length(compsGAP), "\n");
            allPassed := false;
        fi;
    od;

    return allPassed;
end;

###############################################################################
# Run all tests
###############################################################################

RunAllTests := function()
    TestCount := 0;
    PassCount := 0;
    FailCount := 0;

    Print("Running Cohomology Test Suite\n");
    Print("==========================================================\n");

    TestTrivialActionC3();
    TestTrivialActionC2onC2();
    TestS3onC3();
    TestD8onV4();
    TestCocycleSpaceDirectly();
    TestA4onV4();
    TestComplementConstruction();
    TestBatchComparison();

    # Small group tests
    TestSmallGroupComparison(12, 3);   # A4
    TestSmallGroupComparison(24, 12);  # S4

    PrintSummary();

    return FailCount = 0;
end;

###############################################################################

Print("Cohomology test suite loaded.\n");
Print("=============================\n");
Print("Run: RunAllTests()\n");
Print("Individual: TestTrivialActionC3(), TestS3onC3(), etc.\n\n");
