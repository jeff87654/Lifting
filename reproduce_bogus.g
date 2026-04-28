LogTo("C:/Users/jeffr/Downloads/Lifting/reproduce_bogus.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed S1-S17 counts
if IsExistingFile("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g") then
    Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
fi;

# Clear caches for fresh run
FPF_SUBDIRECT_CACHE := rec();
if IsBound(LIFT_CACHE) then LIFT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# The bogus group
bogus := Group([(1,2,3,4,5),(3,4,5),(5,6),(1,5,4,2,6),(1,5,4,3,6),(17,18)]);

# Build the specific combo factors for [6,5,5,2] => [6,5], [5,5], [5,5], [2,1]
T6_5 := TransitiveGroup(6, 5);
T5_5 := TransitiveGroup(5, 5);
T2_1 := TransitiveGroup(2, 1);

factors := [T6_5, T5_5, T5_5, T2_1];
shifted := [];
offs := [];
off := 0;
for f in factors do
    Add(offs, off);
    Add(shifted, ShiftGroup(f, off));
    off := off + NrMovedPoints(f);
od;

Print("Factors: ", List(factors, f -> [NrMovedPoints(f), TransitiveIdentification(f)]), "\n");
Print("Offsets: ", offs, "\n");
Print("|P| = ", Product(List(shifted, Size)), "\n");

# Run FindFPFClassesByLifting on just the [6,5,5] part first
mixed := [shifted[1], shifted[2], shifted[3]];
mixedOffs := [offs[1], offs[2], offs[3]];
mixedP := Group(Concatenation(List(mixed, GeneratorsOfGroup)));
Print("\n[6,5,5] base lifting...\n");
baseGens := FindFPFClassesByLifting(mixedP, mixed, mixedOffs);
Print("  Base result count: ", Length(baseGens), "\n");

# Check if any baseGens produces the bogus group after extension
trivBlocks := 0;
for g in baseGens do
    # Check projection to each [5,5] block
    p1 := Group(Concatenation([()], Filtered(List(GeneratorsOfGroup(g),
                x -> RestrictedPerm(x, [7..11])), x -> x <> ())));
    p2 := Group(Concatenation([()], Filtered(List(GeneratorsOfGroup(g),
                x -> RestrictedPerm(x, [12..16])), x -> x <> ())));
    if Size(p1) = 1 or Size(p2) = 1 then
        trivBlocks := trivBlocks + 1;
    fi;
od;
Print("  Base groups with trivial [5,5] block projection: ", trivBlocks, "\n");

# Now check if the bogus group is among FPF results produced from lifting
# Try to reproduce via FindFPFClassesForPartition
Print("\nRunning FindFPFClassesForPartition(18, [6,5,5,2])...\n");
t0 := Runtime();
FindFPFClassesForPartition(18, [6,5,5,2]);
Print("Total time: ", (Runtime() - t0) / 1000.0, "s\n");

LogTo();
QUIT;
