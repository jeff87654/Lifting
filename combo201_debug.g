
LogTo("C:/Users/jeffr/Downloads/Lifting/combo201_debug.log");
Print("Computing [6,5,5] combo [[5,2],[5,2],[6,14]]\n");
Print("Started at ", StringTime(Runtime()), "\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

N := 16;
offsets := [0, 6, 11];

f1 := TransitiveGroup(6, 14);
f2 := TransitiveGroup(5, 2);
f3 := TransitiveGroup(5, 2);

Print("f1 = TransGrp(6,14): ", StructureDescription(f1), " order=", Size(f1), "\n");
Print("f2 = TransGrp(5,2): ", StructureDescription(f2), " order=", Size(f2), "\n");
Print("f3 = TransGrp(5,2): ", StructureDescription(f3), " order=", Size(f3), "\n\n");

s1 := ShiftGroup(f1, offsets[1]);
s2 := ShiftGroup(f2, offsets[2]);
s3 := ShiftGroup(f3, offsets[3]);

shifted := [s1, s2, s3];
Print("Shifted moved points: ", List(shifted, MovedPoints), "\n");

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P order = ", Size(P), "\n\n");

cs := ChiefSeries(P);
Print("Chief series (", Length(cs), " terms, ", Length(cs)-1, " layers):\n");
for i in [1..Length(cs)-1] do
    Print("  Layer ", i, ": |factor| = ", Size(cs[i]) / Size(cs[i+1]), "\n");
od;
Print("\n");

Print("Calling FindFPFClassesByLifting...\n");
LogTo();
LogTo("C:/Users/jeffr/Downloads/Lifting/combo201_debug.log");

result := FindFPFClassesByLifting(P, shifted, offsets, N);

Print("\nResult: ", Length(result), " FPF classes found\n");
Print("Completed at ", StringTime(Runtime()), "\n");

LogTo();
QUIT;
