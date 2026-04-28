
LogTo("C:/Users/jeffr/Downloads/Lifting/tg_sn_enum.log");
for d in [5..18] do
    n := NrTransitiveGroups(d);
    for t in [1..n] do
        G := TransitiveGroup(d, t);
        sz := Size(G);
        if sz in [120, 720, 5040, 40320] then
            desc := StructureDescription(G);
            Print(d, "\t", t, "\t", sz, "\t", desc, "\n");
        fi;
    od;
od;
LogTo();
QUIT;
