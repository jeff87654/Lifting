LogTo("C:/Users/jeffr/Downloads/Lifting/direct_enum.log");

# Directly enumerate subdirect products of S_5 x D_4 x C_2
# to figure out whether Goursat gives 8 or 20.

Print("\n=== Direct enumeration of subdirects of S_5 x D_4 x C_2 ===\n\n");

# Build as a permutation group on 11 points
Sn := SymmetricGroup([1..5]);
D4 := Group([ (6,7,8,9), (6,7)(8,9) ]);  # D_4 on {6,7,8,9}
C2 := Group([ (10,11) ]);

P := Group(Concatenation(
    GeneratorsOfGroup(Sn),
    GeneratorsOfGroup(D4),
    GeneratorsOfGroup(C2)));
Print("|P| = ", Size(P), " = ", 120*8*2, "? ", Size(P) = 120*8*2, "\n");

# Enumerate all subgroups via ConjugacyClassesSubgroups and
# check which are subdirect products (project onto each factor exactly)
orb1 := [1..5]; orb2 := [6..9]; orb3 := [10..11];

CountSubdirects := function(subs)
    local count, H, pi1, pi2, pi3, g1, g2, g3;
    count := 0;
    for H in subs do
        g1 := Filtered(List(GeneratorsOfGroup(H), g -> RestrictedPerm(g, orb1)), x -> x <> ());
        g2 := Filtered(List(GeneratorsOfGroup(H), g -> RestrictedPerm(g, orb2)), x -> x <> ());
        g3 := Filtered(List(GeneratorsOfGroup(H), g -> RestrictedPerm(g, orb3)), x -> x <> ());
        if Length(g1) = 0 or Length(g2) = 0 or Length(g3) = 0 then
            continue;
        fi;
        pi1 := Group(g1);
        pi2 := Group(g2);
        pi3 := Group(g3);
        if Size(pi1) = 120 and Size(pi2) = 8 and Size(pi3) = 2 then
            count := count + 1;
        fi;
    od;
    return count;
end;

Print("Computing ConjugacyClassesSubgroups(P)... (|P|=", Size(P), ")\n");
t0 := Runtime();
ccs := ConjugacyClassesSubgroups(P);
Print("Found ", Length(ccs), " conjugacy classes in ", Runtime() - t0, "ms\n");

subs := List(ccs, Representative);
n_subdirect := CountSubdirects(subs);
Print("Number of P-classes that are subdirect products: ", n_subdirect, "\n\n");

# Also count via direct product structure (not up to P-conjugacy):
# These are subgroups H of P with π_1(H)=Sn, π_2(H)=D_4, π_3(H)=C_2
Print("--- Counting Goursat (pairs approach) ---\n");
Print("Normal subgroups of S_5: {1}, A_5, S_5 (3 total)\n");

nsSn := NormalSubgroups(Sn);
Print("Actual NormalSubgroups(S_5): ", Length(nsSn), "\n");

H := DirectProduct(D4, C2);
nsH := NormalSubgroups(H);
Print("Normal subgroups of H = D_4 x C_2: ", Length(nsH), " total\n");

# Group by quotient isomorphism type
quot_by_type := rec();
for N in nsH do
    Q := H / N;
    key := String(IdSmallGroup(Q));
    if not IsBound(quot_by_type.(key)) then
        quot_by_type.(key) := [];
    fi;
    Add(quot_by_type.(key), [N, Q]);
od;
Print("H quotient types: ", RecNames(quot_by_type), "\n");
for key in RecNames(quot_by_type) do
    Print("  ", key, ": ", Length(quot_by_type.(key)), " normal subgroups\n");
od;

# Normal subgroups of S_5 by quotient type
for N in nsSn do
    Q := Sn / N;
    Print("  S_5/", StructureDescription(N), " = ", StructureDescription(Q),
          " (id=", IdSmallGroup(Q), ")\n");
od;

LogTo();
QUIT;
