LogTo("C:/Users/jeffr/Downloads/Lifting/check_nonsolv_pairs.log");
Print("Non-solvable transitive groups by degree:\n");
for d in [5..14] do
    nonsolv := [];
    for k in [1..NrTransitiveGroups(d)] do
        G := TransitiveGroup(d, k);
        if not IsSolvable(G) then
            Add(nonsolv, [k, StructureDescription(G)]);
        fi;
    od;
    Print("degree ", d, ": ", Length(nonsolv), " nonsolv -> ", nonsolv, "\n");
od;
LogTo();
QUIT;
