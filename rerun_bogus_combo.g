LogTo("C:/Users/jeffr/Downloads/Lifting/rerun_bogus_combo.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed lower-degree counts
if IsExistingFile("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g") then
    Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
fi;

FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Partition [6,5,5,2] — canonical ordering by FindFPFClassesForPartition
# is to enumerate factor choices for each block; the combo in the bogus
# file is [2,1]_[5,5]_[5,5]_[6,5]. We reconstruct the shifted factors.
# Block sizes in partition are [6,5,5,2] => offsets 0,6,11,16.
# But factor choices in file name go: [2,1]_[5,5]_[5,5]_[6,5] matches
# blocks in some order — in the file the 2-block is first, then 5s, then 6.
# Inspecting generator patterns in the actual combo output ({1..6}, {7..11},
# {12..16}, {17..18}) confirms block-to-factor ordering is:
#   block [1..6]  -> T(6,5)
#   block [7..11] -> T(5,5)
#   block [12..16]-> T(5,5)
#   block [17..18]-> T(2,1)

T6 := TransitiveGroup(6, 5);
T5a := TransitiveGroup(5, 5);
T5b := TransitiveGroup(5, 5);
T2 := TransitiveGroup(2, 1);

factors := [T6, T5a, T5b, T2];
shifted := [];
offs := [];
off := 0;
for f in factors do
    Add(offs, off);
    Add(shifted, ShiftGroup(f, off));
    off := off + NrMovedPoints(f);
od;

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("|P| = ", Size(P), "\n");
Print("Offsets: ", offs, "\n");

t0 := Runtime();
Print("\n=== Running FindFPFClassesByLifting ===\n");
result := FindFPFClassesByLifting(P, shifted, offs);
elapsed := Runtime() - t0;

Print("\nResult count: ", Length(result), "\n");
Print("Time: ", elapsed/1000.0, "s\n\n");

# Check each result for transitivity on each block
blocks := [[1..6], [7..11], [12..16], [17..18]];
bogus := [];
for i in [1..Length(result)] do
    H := result[i];
    bad := [];
    for j in [1..Length(blocks)] do
        b := blocks[j];
        proj_gens := Filtered(List(GeneratorsOfGroup(H),
                g -> RestrictedPerm(g, b)), g -> g <> ());
        if Length(proj_gens) = 0 then
            Add(bad, j);
        elif not IsTransitive(Group(proj_gens), b) then
            Add(bad, j);
        elif Size(Group(proj_gens)) <> Size(shifted[j]) then
            Add(bad, j);
        fi;
    od;
    if Length(bad) > 0 then
        Add(bogus, [i, bad, H]);
    fi;
od;

Print("=== Bogus groups ===\n");
Print("Total results: ", Length(result), "\n");
Print("Bogus (bad block projections): ", Length(bogus), "\n");
for item in bogus do
    Print("  #", item[1], " bad blocks=", item[2], "\n");
    Print("    gens: ", GeneratorsOfGroup(item[3]), "\n");
od;

LogTo();
QUIT;
