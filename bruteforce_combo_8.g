###############################################################################
# Brute-force CCS(P) for combo 8 of [6,4,4,4]:
#   factors: TG(6,15) x TG(4,1) x TG(4,2) x TG(4,2)
#   |P| = 360 x 4 x 4 x 4 = 23040
#
# Filter to FPF subdirect products (projection to each block = the factor)
# then quotient by partition normalizer Npart.  Compare count to 41 (fresh).
###############################################################################

LogTo("C:/Users/jeffr/Downloads/Lifting/bruteforce_combo_8.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Build P
factors := [TransitiveGroup(6,15), TransitiveGroup(4,1),
            TransitiveGroup(4,2), TransitiveGroup(4,2)];
shifted := []; offs := []; off := 0;
for f in factors do
    Add(offs, off);
    Add(shifted, ShiftGroup(f, off));
    off := off + NrMovedPoints(f);
od;
P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
SetSize(P, Product(List(shifted, Size)));
Print("|P| = ", Size(P), "\n");

# Block ranges
blocks := [[1,6],[7,10],[11,14],[15,18]];
Npart := BuildPerComboNormalizer([6,4,4,4], factors, 18);
Print("|Npart| = ", Size(Npart), "\n");

# Compute ALL conjugacy classes of subgroups of P (P-conjugacy)
Print("\nComputing ConjugacyClassesSubgroups(P)...\n");
t0 := Runtime();
ccs := ConjugacyClassesSubgroups(P);
ccs_reps := List(ccs, Representative);
Print("Got ", Length(ccs_reps), " P-conjugacy classes in ", (Runtime()-t0)/1000.0, "s\n");

# Filter: H must project onto factor i in every block i
# Projection check: image of H restricted to block i must equal shifted[i]
projects_correctly := function(H)
    local i, blockPts, restricted;
    for i in [1..Length(blocks)] do
        blockPts := [blocks[i][1]..blocks[i][2]];
        # Image of H acting on blockPts must equal shifted factor
        # (as permutation groups on the block points)
        if not IsSubset(H, []) then  # always true; just placeholder
            # Cheap: check the projection size matches the factor size, then equality.
            # restricted := Group(List(GeneratorsOfGroup(H), g -> Permutation(g, blockPts)));
            restricted := Action(H, blockPts);
            if Size(restricted) <> Size(shifted[i]) then return false; fi;
            # Equality of permutation groups on the same point set
            # Use Group(GeneratorsOfGroup(restricted)) = Group(GeneratorsOfGroup(target))
            # Better: subset both ways
            if not IsSubgroup(Action(shifted[i], blockPts), restricted) then
                return false;
            fi;
            if not IsSubgroup(restricted, Action(shifted[i], blockPts)) then
                return false;
            fi;
        fi;
    od;
    return true;
end;

Print("\nFiltering to FPF subdirect products (projection = factor)...\n");
t1 := Runtime();
fpf_reps := Filtered(ccs_reps, projects_correctly);
Print("Got ", Length(fpf_reps), " P-conjugacy classes that project correctly in ",
      (Runtime()-t1)/1000.0, "s\n");

# Now dedup under Npart-conjugation: for each pair of P-class reps that
# project correctly, check if they're Npart-conjugate.
Print("\nDeduping ", Length(fpf_reps), " P-class reps under Npart...\n");
t2 := Runtime();
npart_reps := [];
for H in fpf_reps do
    is_dup := false;
    for K in npart_reps do
        if RepresentativeAction(Npart, H, K) <> fail then
            is_dup := true; break;
        fi;
    od;
    if not is_dup then Add(npart_reps, H); fi;
od;
Print("Got ", Length(npart_reps), " Npart-classes in ", (Runtime()-t2)/1000.0, "s\n");

Print("\n=== Verdict ===\n");
Print("Brute-force count: ", Length(npart_reps), "\n");
Print("Fresh lift count:   41\n");
Print("Stored (Apr 7):     12\n");
Print("Predicted:          9\n");

if Length(npart_reps) = 41 then
    Print("RESULT: Fresh value 41 MATCHES brute-force. Fresh is correct.\n");
elif Length(npart_reps) = 12 then
    Print("RESULT: Stored value 12 MATCHES brute-force. Fresh code over-produces.\n");
else
    Print("RESULT: Neither matches. True value is ", Length(npart_reps), ".\n");
fi;

LogTo();
QUIT;
