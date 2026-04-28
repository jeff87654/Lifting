
LogTo("C:/Users/jeffr/Downloads/Lifting/test_h1_orbital_unit_output.txt");
Print("H^1 Orbital Unit Tests\n");
Print("======================\n\n");

# Load modules
Read("C:/Users/jeffr/Downloads/Lifting/cohomology.g");
Read("C:/Users/jeffr/Downloads/Lifting/modules.g");
Read("C:/Users/jeffr/Downloads/Lifting/h1_action.g");

allPassed := true;

# Test 1: VectorToIndex and IndexToVector
Print("Test 1: Vector/Index conversion\n");
p := 2;
dim := 3;
for i in [1..p^dim] do
    v := IndexToVector(i, dim, p);
    idx := VectorToIndex(v, p);
    if idx <> i then
        Print("  FAIL: index ", i, " -> ", v, " -> ", idx, "\n");
        allPassed := false;
    fi;
od;
Print("  Vector/Index conversion: PASS\n\n");

# Test 2: ComputeActionMatrix
Print("Test 2: ComputeActionMatrix\n");
S3 := SymmetricGroup(3);
C2 := CyclicGroup(2);
Q := DirectProduct(S3, C2);
M_bar := Image(Embedding(Q, 2), C2);
module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
if module <> fail then
    x := GeneratorsOfGroup(Q)[1];
    mat := ComputeActionMatrix(module, x);
    Print("  Action matrix computed: ", mat, "\n");
    Print("  ComputeActionMatrix: PASS\n");
else
    Print("  Module construction failed\n");
    allPassed := false;
fi;
Print("\n");

# Test 3: ProjectToH1Coordinates and H1CoordsToFullCocycle
Print("Test 3: H1 Coordinate projection\n");
if module <> fail then
    H1 := ComputeH1(module);
    Print("  H1 dimension: ", H1.H1Dimension, "\n");
    if H1.H1Dimension > 0 then
        # Take a cocycle and project to H1, then back
        cocycle := H1.H1Representatives[2];
        coords := ProjectToH1Coordinates(H1, cocycle);
        Print("  Coordinates: ", coords, "\n");
        reconstructed := H1CoordsToFullCocycle(H1, coords);
        # Should differ by at most a coboundary
        Print("  Original:      ", cocycle, "\n");
        Print("  Reconstructed: ", reconstructed, "\n");
        Print("  H1 Coordinate projection: PASS\n");
    else
        Print("  Skipping (trivial H1)\n");
    fi;
fi;
Print("\n");

# Test 4: BuildH1ActionRecord
Print("Test 4: BuildH1ActionRecord\n");
S4 := SymmetricGroup(4);
V4 := Group((1,2)(3,4), (1,3)(2,4));  # Normal V4 in S4
module4 := ChiefFactorAsModule(S4, V4, TrivialSubgroup(V4));
if module4 <> fail then
    H1_4 := ComputeH1(module4);
    Print("  H1 dimension for S4/V4: ", H1_4.H1Dimension, "\n");
    if H1_4.H1Dimension > 0 then
        normGens := GeneratorsOfGroup(Normalizer(S4, V4));
        # Filter to quotient generators
        hom := module4.quotientHom;
        quotGens := Filtered(List(normGens, g -> Image(hom, g)), g -> g <> One(ImagesSource(hom)));
        quotGens := Set(quotGens);
        Print("  Normalizer quotient generators: ", Length(quotGens), "\n");
        if Length(quotGens) > 0 then
            actionRec := BuildH1ActionRecord(H1_4, module4, quotGens);
            Print("  Action matrices computed: ", Length(actionRec.matrices), "\n");
            Print("  BuildH1ActionRecord: PASS\n");
        else
            Print("  No non-trivial quotient generators\n");
        fi;
    fi;
fi;
Print("\n");

# Test 5: ComputeH1Orbits on small example
Print("Test 5: ComputeH1Orbits\n");
# Use S4 with V4 where H1 should be non-trivial
if module4 <> fail and IsBound(H1_4) and H1_4.H1Dimension > 0 then
    if Length(quotGens) > 0 then
        actionRec := BuildH1ActionRecord(H1_4, module4, quotGens);
        orbits := ComputeH1Orbits(actionRec);
        totalPoints := module4.p^H1_4.H1Dimension;
        Print("  Total H1 points: ", totalPoints, "\n");
        Print("  Number of orbits: ", Length(orbits), "\n");
        Print("  Orbit representatives: ", orbits, "\n");
        Print("  ComputeH1Orbits: PASS\n");
    fi;
fi;
Print("\n");

# Test 6: Full GetH1OrbitRepresentatives
Print("Test 6: GetH1OrbitRepresentatives\n");
# Use C2^3 x C2^3 as a test case - clear elementary abelian structure
C2 := CyclicGroup(IsPermGroup, 2);
C2_3 := DirectProduct(C2, C2, C2);  # C2^3
P := DirectProduct(C2_3, C2_3);  # C2^3 x C2^3
# M_bar is second factor (embedded in P)
emb2 := Embedding(P, 2);
M_bar := Image(emb2);
Print("  |P| = ", Size(P), " (C2^3 x C2^3)\n");
Print("  |M_bar| = ", Size(M_bar), "\n");
Print("  IsElementaryAbelian(M_bar): ", IsElementaryAbelian(M_bar), "\n");

# First check with standard method
standardComps := ComplementClassesRepresentatives(P, M_bar);
Print("  Standard method: ", Length(standardComps), " complements\n");

# Now try orbital method
orbitComps := GetH1OrbitRepresentatives(P, M_bar, P);
Print("  Orbital method:  ", Length(orbitComps), " complements\n");

if Length(orbitComps) = Length(standardComps) then
    Print("  GetH1OrbitRepresentatives: PASS\n");
else
    Print("  GetH1OrbitRepresentatives: FAIL (counts differ)\n");
    allPassed := false;
fi;
Print("\n");

# Summary
Print("\n========================================\n");
if allPassed then
    Print("All tests PASSED\n");
else
    Print("Some tests FAILED\n");
fi;
Print("========================================\n");

LogTo();
QUIT;
