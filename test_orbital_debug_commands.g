
LogTo("C:/Users/jeffr/Downloads/Lifting/test_orbital_debug_output.txt");
Print("Orbital Method Debug Test\n");
Print("==========================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/cohomology.g");
Read("C:/Users/jeffr/Downloads/Lifting/modules.g");
Read("C:/Users/jeffr/Downloads/Lifting/h1_action.g");

# Test case: S3 x C2 with M_bar = C2
Print("Test 1: S3 x C2 with M_bar = C2\n");
Print("================================\n");
S3 := SymmetricGroup(3);
C2 := CyclicGroup(IsPermGroup, 2);
Q := DirectProduct(S3, C2);
emb2 := Embedding(Q, 2);
M_bar := Image(emb2);

Print("  |Q| = ", Size(Q), "\n");
Print("  |M_bar| = ", Size(M_bar), "\n");
Print("  Q/M_bar = S3, |G| = ", Size(Q)/Size(M_bar), "\n");
Print("  IsElementaryAbelian(M_bar): ", IsElementaryAbelian(M_bar), "\n\n");

# Create module and compute H1
module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
if module <> fail then
    Print("  Module created successfully\n");
    Print("  dim(M) = ", module.dimension, "\n");
    Print("  |module.generators| = ", Length(module.generators), "\n");
    Print("  |module.preimageGens| = ", Length(module.preimageGens), "\n");

    H1 := ComputeH1(module);
    Print("  dim(H^1) = ", H1.H1Dimension, "\n");
    Print("  |H^1| = ", H1.numComplements, "\n\n");

    # Get normalizer generators
    normGens := ComputeNormalizerPreimageGens(Q, M_bar, Q);
    Print("  normGens (preimages in Q, not in M_bar): ", Length(normGens), "\n");
    for i in [1..Length(normGens)] do
        Print("    normGens[", i, "] = ", normGens[i], "\n");
    od;
    Print("\n");

    # Build action record
    Print("  Building H1 action record...\n");
    H1action := BuildH1ActionRecord(H1, module, normGens);
    if H1action = fail then
        Print("  BuildH1ActionRecord FAILED\n");
    else
        Print("  Action matrices:\n");
        for i in [1..Length(H1action.matrices)] do
            Print("    mat[", i, "] = ", H1action.matrices[i], "\n");
        od;
        Print("\n");

        # Compute orbits
        orbitReps := ComputeH1Orbits(H1action);
        Print("  Number of orbits: ", Length(orbitReps), "\n");
        Print("  Expected (|H^1|): ", H1.numComplements, "\n");
        Print("  Orbit representatives:\n");
        for i in [1..Minimum(10, Length(orbitReps))] do
            Print("    orbit[", i, "] = ", orbitReps[i], "\n");
        od;
    fi;
    Print("\n");
else
    Print("  Module creation FAILED\n\n");
fi;

# Compare orbital vs standard
Print("Comparison: Orbital vs Standard method\n");
Print("======================================\n");
standardComps := ComplementClassesRepresentatives(Q, M_bar);
Print("  Standard method: ", Length(standardComps), " complements\n");

orbitalComps := GetH1OrbitRepresentatives(Q, M_bar, Q);
Print("  Orbital method:  ", Length(orbitalComps), " complements\n");

if Length(orbitalComps) = Length(standardComps) then
    Print("  MATCH!\n");
else
    Print("  MISMATCH!\n");
fi;

Print("\n\nTest 2: S4 with M_bar = V4 (Klein four-group)\n");
Print("==============================================\n");
S4 := SymmetricGroup(4);
V4 := Group((1,2)(3,4), (1,3)(2,4));

Print("  |S4| = ", Size(S4), "\n");
Print("  |V4| = ", Size(V4), "\n");
Print("  S4/V4 = S3, |G| = ", Size(S4)/Size(V4), "\n");

standardComps := ComplementClassesRepresentatives(S4, V4);
Print("  Standard method: ", Length(standardComps), " complements\n");

orbitalComps := GetH1OrbitRepresentatives(S4, V4, S4);
Print("  Orbital method:  ", Length(orbitalComps), " complements\n");

if Length(orbitalComps) = Length(standardComps) then
    Print("  MATCH!\n");
else
    Print("  MISMATCH!\n");
fi;

Print("\n========================================\n");
Print("Debug Test Complete\n");
Print("========================================\n");
LogTo();
QUIT;
