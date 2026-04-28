
LogTo("C:/Users/jeffr/Downloads/Lifting/nonsolvable_tgs.log");
for d in [2..18] do
    nonsol := [];
    n := NrTransitiveGroups(d);
    for i in [1..n] do
        G := TransitiveGroup(d, i);
        if not IsSolvable(G) then
            Add(nonsol, i);
        fi;
    od;
    Print(d, ": ", nonsol, "\n");
od;
LogTo();
QUIT;
