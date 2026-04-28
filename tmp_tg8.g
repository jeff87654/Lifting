
LogTo("C:/Users/jeffr/Downloads/Lifting/tg8_check.log");
Print("TG(8,Y) structures:\n");
for Y in [1,2,4,12,22,25,32,35,36,37,48,49] do
    G := TransitiveGroup(8, Y);
    Print("TG(8,", Y, "): |G|=", Size(G),
          ", IsSolvable=", IsSolvable(G),
          ", IsPrimitive=", IsPrimitive(G, [1..8]),
          ", Desc=", StructureDescription(G), "\n");
od;
Print("\nIsomorphism test for anomalous set {12,25,32,36,37,48,49}:\n");
anom := [12, 25, 32, 36, 37, 48, 49];
for i in [1..Length(anom)] do
    for j in [i+1..Length(anom)] do
        G1 := TransitiveGroup(8, anom[i]);
        G2 := TransitiveGroup(8, anom[j]);
        iso := IsomorphismGroups(G1, G2);
        Print("  TG(8,", anom[i], ") vs TG(8,", anom[j], "): |G1|=", Size(G1),
              " |G2|=", Size(G2),
              " isomorphic=", iso <> fail, "\n");
    od;
od;
LogTo();
QUIT;
