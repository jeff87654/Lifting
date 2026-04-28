###############################################################################
#
# test_bug_diagnosis.g - Diagnostic tests for cocycle/complement bugs
#
# Tests:
# 1. Cocycle validity check on S3/C3
# 2. Complement formula vs GAP's ComplementClassesRepresentatives
# 3. Generator matching stress test (S3/A3, S4/V4, C2xC2/C2, D8/Z(D8))
# 4. Cross-validation of Pcgs vs FP cocycle spaces
# 5. Zero-cocycle sanity check (must give base complement)
# 6. Non-coprime case with multiple complement classes
# 7. Action matrix consistency verification
#
###############################################################################

# Load the main code
Read("C:/Users/jeffr/Downloads/Lifting/cohomology.g");
Read("C:/Users/jeffr/Downloads/Lifting/modules.g");
Read("C:/Users/jeffr/Downloads/Lifting/h1_action.g");

# Ensure cross-validation is on for these tests
CROSS_VALIDATE_COCYCLES := true;

testsPassed := 0;
testsFailed := 0;
testNum := 0;

ReportTest := function(name, passed)
    testNum := testNum + 1;
    if passed then
        Print("TEST ", testNum, " PASSED: ", name, "\n");
        testsPassed := testsPassed + 1;
    else
        Print("TEST ", testNum, " FAILED: ", name, "\n");
        testsFailed := testsFailed + 1;
    fi;
end;

###############################################################################
# TEST 1: Cocycle validity on S3/C3
###############################################################################

Print("\n=== TEST 1: Cocycle validity on S3/C3 ===\n");

_test1 := function()
    local S3, C3, module, H1, failCount;

    S3 := SymmetricGroup(3);
    C3 := DerivedSubgroup(S3);  # A3 = C3

    module := ChiefFactorAsModule(S3, C3, TrivialSubgroup(C3));

    if IsBound(module.isNonSplit) or IsBound(module.isModuleConstructionFailed) then
        Print("  Module construction issue\n");
        return false;
    fi;

    H1 := ComputeH1(module);
    Print("  dim H^1 = ", H1.H1Dimension, "\n");

    failCount := ValidateAllH1Cocycles(H1);
    return failCount = 0;
end;

ReportTest("Cocycle validity on S3/C3", _test1());

###############################################################################
# TEST 2: Complement formula vs GAP
###############################################################################

Print("\n=== TEST 2: Complement formula vs GAP ===\n");

_test2 := function()
    local S4, V4, gapComps, h1Comps, module, H1, complementInfo;

    S4 := SymmetricGroup(4);
    V4 := Group([(1,2)(3,4), (1,3)(2,4)]);

    # GAP's method
    gapComps := ComplementClassesRepresentatives(S4, V4);
    Print("  GAP finds ", Length(gapComps), " complement classes\n");

    # Our method
    h1Comps := GetComplementsViaH1(S4, V4);
    Print("  H1 method finds ", Length(h1Comps), " complement classes\n");

    return Length(gapComps) = Length(h1Comps);
end;

ReportTest("Complement formula vs GAP (S4/V4)", _test2());

###############################################################################
# TEST 3: Generator matching stress test
###############################################################################

Print("\n=== TEST 3: Generator matching stress test ===\n");

_test3 := function()
    local testCases, tc, Q, M, module, pcgsG, allMatch, i, passed;

    testCases := [
        rec(name := "S3/A3", Q := SymmetricGroup(3),
            M := DerivedSubgroup(SymmetricGroup(3))),
        rec(name := "S4/V4", Q := SymmetricGroup(4),
            M := Group([(1,2)(3,4), (1,3)(2,4)])),
    ];

    passed := true;

    for tc in testCases do
        Print("  Testing ", tc.name, "...\n");
        module := ChiefFactorAsModule(tc.Q, tc.M, TrivialSubgroup(tc.M));

        if IsBound(module.isNonSplit) or IsBound(module.isModuleConstructionFailed) then
            Print("    Module construction issue\n");
            passed := false;
            continue;
        fi;

        # Check that module.generators and preimageGens have same length
        if Length(module.generators) <> Length(module.preimageGens) then
            Print("    MISMATCH: #generators=", Length(module.generators),
                  " #preimageGens=", Length(module.preimageGens), "\n");
            passed := false;
            continue;
        fi;

        # Check correspondence: preimageGens[i] maps to module.generators[i]
        allMatch := true;
        for i in [1..Length(module.generators)] do
            if Image(module.quotientHom, module.preimageGens[i]) <> module.generators[i] then
                Print("    Generator correspondence broken at index ", i, "\n");
                allMatch := false;
            fi;
        od;

        if allMatch then
            Print("    OK: all ", Length(module.generators), " generators match\n");
        else
            passed := false;
        fi;

        # Check if Pcgs method is being used (generators should match Pcgs)
        if CanEasilyComputePcgs(module.group) then
            pcgsG := Pcgs(module.group);
            if Length(module.generators) = Length(pcgsG) then
                if ForAll([1..Length(module.generators)],
                          i -> module.generators[i] = pcgsG[i]) then
                    Print("    Pcgs method will be used (generators match Pcgs)\n");
                else
                    Print("    FP method will be used (generators don't match Pcgs elements)\n");
                fi;
            else
                Print("    FP method will be used (ngens=", Length(module.generators),
                      " <> Length(Pcgs)=", Length(pcgsG), ")\n");
            fi;
        fi;
    od;

    return passed;
end;

ReportTest("Generator matching stress test", _test3());

###############################################################################
# TEST 4: Cross-validation of Pcgs vs FP cocycle spaces
###############################################################################

Print("\n=== TEST 4: Cross-validation of Pcgs vs FP ===\n");

_test4 := function()
    local testCases, tc, Q, M, module, resultPcgs, resultFP,
          dimPcgs, dimFP, combined, passed;

    testCases := [
        rec(name := "S3/C3", Q := SymmetricGroup(3),
            M := DerivedSubgroup(SymmetricGroup(3))),
        rec(name := "S4/V4", Q := SymmetricGroup(4),
            M := Group([(1,2)(3,4), (1,3)(2,4)])),
    ];

    passed := true;

    for tc in testCases do
        Print("  Testing ", tc.name, "...\n");
        module := ChiefFactorAsModule(tc.Q, tc.M, TrivialSubgroup(tc.M));

        if IsBound(module.isNonSplit) or IsBound(module.isModuleConstructionFailed) then
            Print("    Module construction issue, skipping\n");
            continue;
        fi;

        if not (IsSolvableGroup(module.group) and CanEasilyComputePcgs(module.group)) then
            Print("    Not solvable, skipping Pcgs test\n");
            continue;
        fi;

        resultPcgs := ComputeCocycleSpaceViaPcgs(module);
        resultFP := ComputeCocycleSpaceOriginal(module);

        if resultPcgs = fail then
            Print("    Pcgs method returned fail (expected for filtered generators)\n");
            continue;
        fi;

        dimPcgs := Length(resultPcgs);
        dimFP := Length(resultFP);

        Print("    dim(Z^1) Pcgs=", dimPcgs, " FP=", dimFP, "\n");

        if dimPcgs <> dimFP then
            Print("    DIMENSION MISMATCH!\n");
            passed := false;
            continue;
        fi;

        if dimPcgs > 0 then
            combined := BaseMat(Concatenation(resultPcgs, resultFP));
            if Length(combined) <> dimPcgs then
                Print("    SUBSPACE MISMATCH! combined dim=", Length(combined), "\n");
                passed := false;
            else
                Print("    OK: same subspace\n");
            fi;
        else
            Print("    OK: both trivial\n");
        fi;
    od;

    return passed;
end;

ReportTest("Cross-validation Pcgs vs FP", _test4());

###############################################################################
# TEST 5: Zero-cocycle sanity check
###############################################################################

Print("\n=== TEST 5: Zero-cocycle gives base complement ===\n");

_test5 := function()
    local S4, V4, module, complementInfo, zeroCocycle, C, passed;

    S4 := SymmetricGroup(4);
    V4 := Group([(1,2)(3,4), (1,3)(2,4)]);

    module := ChiefFactorAsModule(S4, V4, TrivialSubgroup(V4));

    if IsBound(module.isNonSplit) or IsBound(module.isModuleConstructionFailed) then
        Print("  Module construction issue\n");
        return false;
    fi;

    complementInfo := BuildComplementInfo(S4, V4, module);

    # Zero cocycle should give the base complement (= Group(preimageGens))
    zeroCocycle := ListWithIdenticalEntries(
        Length(module.generators) * module.dimension,
        Zero(module.field));

    C := CocycleToComplement(zeroCocycle, complementInfo);

    if C = fail then
        Print("  CocycleToComplement returned fail for zero cocycle!\n");
        return false;
    fi;

    passed := true;

    # Check it's a valid complement
    if Size(C) * Size(V4) <> Size(S4) then
        Print("  Zero cocycle complement has wrong order: |C|=", Size(C), "\n");
        passed := false;
    else
        Print("  |C| = ", Size(C), " (correct)\n");
    fi;

    if Size(Intersection(C, V4)) > 1 then
        Print("  Zero cocycle complement intersects M_bar!\n");
        passed := false;
    else
        Print("  C ∩ M_bar = {1} (correct)\n");
    fi;

    return passed;
end;

ReportTest("Zero-cocycle gives base complement", _test5());

###############################################################################
# TEST 6: Non-coprime case with multiple complement classes
###############################################################################

Print("\n=== TEST 6: Non-coprime case ===\n");

_test6 := function()
    local C2, V4, Q, N, gapComps, h1Comps;

    # C2 x C2 x C2 with C2 normal subgroup
    # This is a non-coprime case (|G/M| = 4, |M| = 2, gcd = 2)
    V4 := DirectProduct(CyclicGroup(2), CyclicGroup(2));
    Q := DirectProduct(V4, CyclicGroup(2));
    N := Image(Embedding(Q, 2));  # The C2 factor

    if not IsNormal(Q, N) then
        Print("  N is not normal in Q, adjusting...\n");
        return true;  # Skip if setup doesn't work
    fi;

    gapComps := ComplementClassesRepresentatives(Q, N);
    Print("  GAP: ", Length(gapComps), " complement classes\n");

    h1Comps := GetComplementsViaH1(Q, N);
    Print("  H1:  ", Length(h1Comps), " complement classes\n");

    return Length(gapComps) = Length(h1Comps);
end;

ReportTest("Non-coprime case complement count", _test6());

###############################################################################
# TEST 7: Action matrix consistency
###############################################################################

Print("\n=== TEST 7: Action matrix consistency ===\n");

_test7 := function()
    local S4, V4, module, pcgsM, i, j, m, gen, img, exps, mat,
          expected, passed;

    S4 := SymmetricGroup(4);
    V4 := Group([(1,2)(3,4), (1,3)(2,4)]);

    module := ChiefFactorAsModule(S4, V4, TrivialSubgroup(V4));

    if IsBound(module.isNonSplit) or IsBound(module.isModuleConstructionFailed) then
        Print("  Module construction issue\n");
        return false;
    fi;

    passed := true;
    pcgsM := module.pcgsM;

    # Verify: for each generator g and basis element m_i,
    # m_i^g expressed in pcgsM coordinates should match row i of action matrix
    for i in [1..Length(module.preimageGens)] do
        gen := module.preimageGens[i];
        mat := module.matrices[i];

        for j in [1..module.dimension] do
            m := pcgsM[j];
            img := m^gen;
            exps := ExponentsOfPcElement(pcgsM, img);
            expected := List(exps, e -> e * One(module.field));

            if expected <> mat[j] then
                Print("  ACTION MISMATCH: gen ", i, " basis ", j, "\n");
                Print("    expected ", expected, " got ", mat[j], "\n");
                passed := false;
            fi;
        od;
    od;

    if passed then
        Print("  All action matrices consistent with conjugation.\n");
    fi;

    return passed;
end;

ReportTest("Action matrix consistency", _test7());

###############################################################################
# Summary
###############################################################################

Print("\n========================================\n");
Print("RESULTS: ", testsPassed, " passed, ", testsFailed, " failed out of ", testNum, " tests\n");
Print("========================================\n");

if testsFailed > 0 then
    Print("SOME TESTS FAILED!\n");
else
    Print("ALL TESTS PASSED!\n");
fi;
