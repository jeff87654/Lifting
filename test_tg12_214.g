LogTo("C:/Users/jeffr/Downloads/Lifting/test_tg12_214.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n=== Reproduce crash: combo [2,1],[4,4],[12,214] ===\n\n");

combo := [[2,1],[4,4],[12,214]];
shifted := [];
offs := [];
pos := 0;
for c in combo do
    G := TransitiveGroup(c[1], c[2]);
    Add(shifted, ShiftGroup(G, pos));
    Add(offs, pos);
    pos := pos + c[1];
od;

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P order = ", Size(P), "\n");

Print("\n--- CoprimePriorityChiefSeries ---\n");
series := CoprimePriorityChiefSeries(P, shifted);
Print("Series length: ", Length(series), "\n");
for i in [1..Length(series)] do
    Print("  series[", i, "]: order ", Size(series[i]), "\n");
od;
Print("\nLayers:\n");
for i in [1..Length(series)-1] do
    M := series[i];
    N := series[i+1];
    Print("  Layer ", i, ": |M|=", Size(M), " |N|=", Size(N),
          " |M/N|=", Size(M)/Size(N), "\n");
    if not IsSubgroup(M, N) then
        Print("    *** BUG: N is NOT a subgroup of M! ***\n");
    fi;
    if not IsNormal(P, N) then
        Print("    *** BUG: N is NOT normal in P! ***\n");
    fi;
od;

Print("\n--- RefinedChiefSeries (for comparison) ---\n");
series2 := RefinedChiefSeries(P);
Print("Series length: ", Length(series2), "\n");
for i in [1..Length(series2)-1] do
    Print("  Layer ", i, ": |M/N|=", Size(series2[i])/Size(series2[i+1]), "\n");
od;

Print("\n--- Attempting FindFPFClassesByLifting ---\n");
result := FindFPFClassesByLifting(P, shifted, offs);
Print("Result: ", Length(result), " FPF classes\n");

LogTo();
QUIT;
