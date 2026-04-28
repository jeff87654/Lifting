LogTo("C:/Users/jeffr/Downloads/Lifting/verify_d4cube.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

combo := [[4,3], [4,3], [4,3]];
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
Print("P order: ", Size(P), "\n");

t0 := Runtime();
ccs := ConjugacyClassesSubgroups(P);
Print("P has ", Length(ccs), " conjugacy classes (", Runtime()-t0, "ms)\n");

# Filter for subdirect products
fpf := 0;
orb1 := [1..4]; orb2 := [5..8]; orb3 := [9..12];
for cc in ccs do
    H := Representative(cc);
    g1 := Filtered(List(GeneratorsOfGroup(H), g -> RestrictedPerm(g, orb1)), x -> x <> ());
    g2 := Filtered(List(GeneratorsOfGroup(H), g -> RestrictedPerm(g, orb2)), x -> x <> ());
    g3 := Filtered(List(GeneratorsOfGroup(H), g -> RestrictedPerm(g, orb3)), x -> x <> ());
    if Length(g1) = 0 or Length(g2) = 0 or Length(g3) = 0 then continue; fi;
    if Size(Group(g1)) = 8 and Size(Group(g2)) = 8 and Size(Group(g3)) = 8 then
        fpf := fpf + 1;
    fi;
od;
Print("P-conjugacy subdirect count: ", fpf, "\n");

LogTo();
QUIT;
