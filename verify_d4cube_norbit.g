LogTo("C:/Users/jeffr/Downloads/Lifting/verify_d4cube_norbit.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n=== Verify D_4^3 N-orbit count ===\n");

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

# Build partition normalizer
normArg := BuildPerComboNormalizer([4,4,4], shifted, 12);
Print("|P| = ", Size(P), ", |N| = ", Size(normArg), "\n\n");

# Enumerate all subdirects via ConjugacyClassesSubgroups
ccs := ConjugacyClassesSubgroups(P);
Print("P has ", Length(ccs), " P-conjugacy classes\n");

subdirects := [];
orb1 := [1..4]; orb2 := [5..8]; orb3 := [9..12];
for cc in ccs do
    H := Representative(cc);
    g1 := Filtered(List(GeneratorsOfGroup(H), g -> RestrictedPerm(g, orb1)), x -> x <> ());
    g2 := Filtered(List(GeneratorsOfGroup(H), g -> RestrictedPerm(g, orb2)), x -> x <> ());
    g3 := Filtered(List(GeneratorsOfGroup(H), g -> RestrictedPerm(g, orb3)), x -> x <> ());
    if Length(g1) = 0 or Length(g2) = 0 or Length(g3) = 0 then continue; fi;
    if Size(Group(g1)) = 8 and Size(Group(g2)) = 8 and Size(Group(g3)) = 8 then
        Add(subdirects, H);
    fi;
od;
Print("P-conjugacy subdirects: ", Length(subdirects), "\n\n");

# Now dedup these 1110 P-classes under N
Print("Deduping under N...\n");
t0 := Runtime();
nReps := [];
for H in subdirects do
    found := false;
    for K in nReps do
        if RepresentativeAction(normArg, H, K) <> fail then
            found := true;
            break;
        fi;
    od;
    if not found then
        Add(nReps, H);
    fi;
od;
Print("N-orbit count: ", Length(nReps), " (", Runtime() - t0, "ms)\n");

Print("\nExpected from cache: 264\n");
if Length(nReps) = 264 then
    Print("MATCH!\n");
else
    Print("MISMATCH!\n");
fi;

LogTo();
QUIT;
