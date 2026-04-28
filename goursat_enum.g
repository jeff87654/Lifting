LogTo("C:/Users/jeffr/Downloads/Lifting/goursat_enum.log");

Print("\n=== Goursat enumeration of subdirects of S_5 x (D_4 x C_2) ===\n\n");

# Test case: S_5 on [1..5], D_4 on [6..9], C_2 on [10..11]
Sn := SymmetricGroup([1..5]);
D4 := Group([ (6,7,8,9), (6,7)(8,9) ]);
C2_1 := Group([ (10,11) ]);
H := Group(Concatenation(GeneratorsOfGroup(D4), GeneratorsOfGroup(C2_1)));

Print("|S_5| = ", Size(Sn), ", |H = D_4 x C_2| = ", Size(H), "\n\n");

# Enumerate all (N_1, N_2, phi) triples
P := Group(Concatenation(GeneratorsOfGroup(Sn), GeneratorsOfGroup(H)));

nsSn := NormalSubgroups(Sn);
nsH := NormalSubgroups(H);
Print("|NS(S_5)| = ", Length(nsSn), ", |NS(H)| = ", Length(nsH), "\n");

total := 0;
classes_found := [];

for N1 in nsSn do
    Q1 := Sn / N1;
    s1 := Size(Q1);
    for N2 in nsH do
        Q2 := H / N2;
        if Size(Q2) <> s1 then continue; fi;
        # Try to find isomorphism phi: Q1 -> Q2
        iso := IsomorphismGroups(Q1, Q2);
        if iso = fail then continue; fi;
        # For each element of Aut(Q1), we get a distinct subdirect product
        # (the total number of iso Q1 -> Q2 is |Aut(Q1)|)
        autGroup := AutomorphismGroup(Q1);
        nAut := Size(autGroup);
        total := total + nAut;
        Print("  (|N_1|=", Size(N1), ", |N_2|=", Size(N2), "): |Q|=", s1,
              ", ", nAut, " subdirect product(s)\n");
        # Actually build the subdirect product for N_1=A_5 case
        if Size(N1) = 60 and nAut = 1 then
            # Build U = {(s, h) : sgn(s) = 1 iff h in N2}
            gens := [];
            Append(gens, GeneratorsOfGroup(N1));  # A_5 generators (gens of kernel on S_5 side)
            Append(gens, GeneratorsOfGroup(N2));  # N_2 generators
            # Add one off-diagonal element (odd perm * element not in N_2)
            odd := (1,2);
            notinN2 := First(Elements(H), h -> not h in N2);
            Add(gens, odd * notinN2);
            U := Group(gens);
            Print("    U = diagonal, |U| = ", Size(U), "\n");
            Add(classes_found, U);
        fi;
    od;
od;

Print("\nTotal Goursat count: ", total, "\n");

# Dedup by P-conjugacy
Print("\nDedup built subdirects by P-conjugacy: ");
unique := [];
for U in classes_found do
    found := false;
    for V in unique do
        if RepresentativeAction(P, U, V) <> fail then
            found := true;
            break;
        fi;
    od;
    if not found then Add(unique, U); fi;
od;
Print(Length(unique), " unique\n");

LogTo();
QUIT;
