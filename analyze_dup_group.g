LogTo("C:/Users/jeffr/Downloads/Lifting/analyze_dup_group.log");

G := Group([(1,2,3,4,5),(3,4,5),(5,6),(1,5,4,2,6),(1,5,4,3,6),(17,18)]);

Print("Group order: ", Size(G), "\n");
Print("LargestMovedPoint: ", LargestMovedPoint(G), "\n");
Print("Orbits of G on [1..18]: ", Orbits(G, [1..18]), "\n");
Print("MovedPoints(G): ", MovedPoints(G), "\n");
Print("Fixed points on [1..18]: ",
      Filtered([1..18], p -> ForAll(GeneratorsOfGroup(G), g -> p^g = p)), "\n");
Print("Is FPF on [1..18]? ",
      ForAll([1..18], p -> ForAny(G, g -> p^g <> p)), "\n");

blocks := [[1..6], [7..11], [12..16], [17..18]];
Print("\nBlocks (partition [6,5,5,2]): ", blocks, "\n");
for i in [1..Length(blocks)] do
    b := blocks[i];
    gens := List(GeneratorsOfGroup(G),
                 g -> RestrictedPerm(g, b));
    gens := Filtered(gens, g -> g <> ());
    Hb := Group(Concatenation([()], gens));
    Print("  Block ", b, ":\n");
    Print("    Projection size: ", Size(Hb), "\n");
    Print("    Projection transitive on block? ", IsTransitive(Hb, b), "\n");
    Print("    Orbits on block: ", Orbits(Hb, b), "\n");
od;

Print("\nStructure description: ", StructureDescription(G), "\n");

Print("\nConjugacy test - are [5,5] projections related?\n");
b1 := [7..11]; b2 := [12..16];
p1 := Group(Concatenation([()], Filtered(List(GeneratorsOfGroup(G),
            g -> RestrictedPerm(g, b1)), g -> g <> ())));
p2 := Group(Concatenation([()], Filtered(List(GeneratorsOfGroup(G),
            g -> RestrictedPerm(g, b2)), g -> g <> ())));
Print("  |projection to block [7..11]| = ", Size(p1), "\n");
Print("  |projection to block [12..16]| = ", Size(p2), "\n");

LogTo();
QUIT;
