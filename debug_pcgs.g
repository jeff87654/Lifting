# Debug Pcgs alignment issues
Read("C:/Users/jeffr/Downloads/Lifting/cohomology.g");
Read("C:/Users/jeffr/Downloads/Lifting/modules.g");

# Test case: S4 acting on V4
Print("\n=== Debug Pcgs Alignment ===\n");

S4 := SymmetricGroup(4);
V4 := First(NormalSubgroups(S4), N -> Size(N) = 4 and IsElementaryAbelian(N));
Print("S4 = ", S4, ", |S4| = ", Size(S4), "\n");
Print("V4 = ", V4, ", |V4| = ", Size(V4), "\n");

# Create module
module := ChiefFactorAsModule(S4, V4, TrivialSubgroup(V4));
Print("\nModule created:\n");
Print("  G = Q/M_bar: ", module.group, "\n");
Print("  |G| = ", Size(module.group), "\n");
Print("  IsSolvable(G) = ", IsSolvableGroup(module.group), "\n");
Print("  CanEasilyComputePcgs(G) = ", CanEasilyComputePcgs(module.group), "\n");

Print("\n  module.generators:\n");
for i in [1..Length(module.generators)] do
    Print("    [", i, "] ", module.generators[i], " order=", Order(module.generators[i]), "\n");
od;

Print("\n  Fresh Pcgs(G):\n");
pcgs := Pcgs(module.group);
Print("  Length(pcgs) = ", Length(pcgs), "\n");
Print("  RelativeOrders = ", RelativeOrders(pcgs), "\n");
for i in [1..Length(pcgs)] do
    Print("    [", i, "] ", pcgs[i], " order=", Order(pcgs[i]), "\n");
od;

Print("\n  Are they equal? ", module.generators = pcgs, "\n");

# Check matrices
Print("\n  module.matrices:\n");
for i in [1..Length(module.matrices)] do
    Print("    Matrix ", i, ":\n");
    for row in module.matrices[i] do
        Print("      ", row, "\n");
    od;
od;

# Try computing Z^1 with original method
Print("\n=== Computing Z^1 (Original Method) ===\n");
Z1_orig := ComputeCocycleSpaceOriginal(module);
Print("dim Z^1 (original) = ", Length(Z1_orig), "\n");

# Try computing Z^1 with Pcgs method
Print("\n=== Computing Z^1 (Pcgs Method) ===\n");
Z1_pcgs := ComputeCocycleSpaceViaPcgs(module);
if Z1_pcgs = fail then
    Print("Pcgs method returned fail\n");
else
    Print("dim Z^1 (pcgs) = ", Length(Z1_pcgs), "\n");
fi;

# Compute B^1
Print("\n=== Computing B^1 ===\n");
B1 := ComputeCoboundarySpace(module);
Print("dim B^1 = ", Length(B1), "\n");

# Check containment
if Z1_pcgs <> fail and Length(Z1_pcgs) > 0 and Length(B1) > 0 then
    Print("\n=== Checking B^1 ⊆ Z^1 ===\n");
    combined := Concatenation(Z1_pcgs, B1);
    combined := BaseMat(combined);
    Print("dim(span(Z^1 ∪ B^1)) = ", Length(combined), "\n");
    if Length(combined) = Length(Z1_pcgs) then
        Print("PASS: B^1 ⊆ Z^1\n");
    else
        Print("FAIL: B^1 ⊄ Z^1\n");
        Print("  Z^1 has dim ", Length(Z1_pcgs), " but span has dim ", Length(combined), "\n");
    fi;
fi;

# Also test with original Z^1
if Length(Z1_orig) > 0 and Length(B1) > 0 then
    Print("\n=== Checking B^1 ⊆ Z^1 (Original) ===\n");
    combined := Concatenation(Z1_orig, B1);
    combined := BaseMat(combined);
    Print("dim(span(Z^1_orig ∪ B^1)) = ", Length(combined), "\n");
    if Length(combined) = Length(Z1_orig) then
        Print("PASS: B^1 ⊆ Z^1_orig\n");
    else
        Print("FAIL: B^1 ⊄ Z^1_orig\n");
    fi;
fi;

QUIT;
