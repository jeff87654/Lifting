LogTo("C:/Users/jeffr/Downloads/Lifting/test_552_missing.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Step 1: Get our computed FPF classes for [5,5,2]
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("Computing FindFPFClassesForPartition(12, [5,5,2])...\n");
t0 := Runtime();
ourResult := FindFPFClassesForPartition(12, [5,5,2]);
Print("Our code: ", Length(ourResult), " groups (", (Runtime()-t0)/1000.0, "s)\n");

# Build actual groups from generator lists
ourGroups := List(ourResult, gens -> Group(List(gens, PermList)));
Print("Built ", Length(ourGroups), " groups from generators\n");

# Step 2: Get brute-force reference groups with orbit partition [5,5,2]
Print("\nComputing brute-force ConjugacyClassesSubgroups(S_12)...\n");
t0 := Runtime();
S12 := SymmetricGroup(12);
ccs := ConjugacyClassesSubgroups(S12);
Print("Brute force: ", Length(ccs), " total classes (", (Runtime()-t0)/1000.0, "s)\n");

# Filter for [5,5,2] orbit partition
refGroups := [];
for c in ccs do
    H := Representative(c);
    orbs := List(Orbits(H, [1..12]), Length);
    Sort(orbs);
    orbs := Reversed(orbs);
    if orbs = [5,5,2] then
        Add(refGroups, H);
    fi;
od;
Print("Reference [5,5,2] groups: ", Length(refGroups), "\n");

# Step 3: For each reference group, check if it's in our list
Print("\nChecking which reference groups are missing from our computation...\n");
missing := [];
for i in [1..Length(refGroups)] do
    H := refGroups[i];
    found := false;
    for j in [1..Length(ourGroups)] do
        if RepresentativeAction(S12, ourGroups[j], H) <> fail then
            found := true;
            break;
        fi;
    od;
    if not found then
        Print("MISSING group #", i, ": Size=", Size(H),
              " Orbits=", List(Orbits(H, [1..12]), Length),
              " AbelianInvariants=", AbelianInvariants(H),
              " IsTransitive(orbit1)=", IsTransitive(H, Orbits(H,[1..12])[1]),
              "\n");
        Add(missing, H);
    else
        Print("Found group #", i, "\n");
    fi;
od;

Print("\n=== SUMMARY ===\n");
Print("Our count: ", Length(ourGroups), "\n");
Print("Reference count: ", Length(refGroups), "\n");
Print("Missing: ", Length(missing), "\n");

# Detailed info on missing groups
for i in [1..Length(missing)] do
    H := missing[i];
    Print("\n--- Missing group ", i, " ---\n");
    Print("Size: ", Size(H), "\n");
    Print("Order: ", Size(H), "\n");
    Print("Generators: ", GeneratorsOfGroup(H), "\n");
    orbs := Orbits(H, [1..12]);
    Print("Orbits: ", orbs, "\n");
    for j in [1..Length(orbs)] do
        orb := orbs[j];
        stab := Action(H, orb);
        Print("  Orbit ", j, " (size ", Length(orb), "): ");
        if IsTransitive(stab, [1..Length(orb)]) then
            tid := TransitiveIdentification(stab);
            Print("TransitiveGroup(", Length(orb), ",", tid, ") = ", StructureDescription(stab), "\n");
        else
            Print("NOT transitive! ", StructureDescription(stab), "\n");
        fi;
    od;
    Print("StructureDescription: ", StructureDescription(H), "\n");
    Print("AbelianInvariants: ", AbelianInvariants(H), "\n");
    Print("DerivedLength: ", DerivedLength(H), "\n");
od;

LogTo();
QUIT;
