G := TransitiveGroup(8, 26);
Print("T(8,26): order=", Size(G), ", structure=", StructureDescription(G), "\n");
Print("IsAbelian=", IsAbelian(G), ", IsSolvable=", IsSolvable(G), "\n");
Print("# normal subgroups=", Length(NormalSubgroups(G)), "\n");
N := Normalizer(SymmetricGroup(8), G);
Print("|N_S8(T(8,26))|=", Size(N), ", quotient=", Size(N)/Size(G), "\n");
QUIT;
