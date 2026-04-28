LogTo("C:/Users/jeffr/Downloads/Lifting/test_fpf_filter.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

G := Group([(1,2,3,4,5),(3,4,5),(5,6),(1,5,4,2,6),(1,5,4,3,6),(17,18)]);

# Partition [6,5,5,2] blocks start at offsets 0, 6, 11, 16
# with transitive group candidates
T6 := TransitiveGroup(6, 5);  # will be shifted to [1..6]
T5a := TransitiveGroup(5, 5); # should be at [7..11]
T5b := TransitiveGroup(5, 5); # should be at [12..16]
T2 := TransitiveGroup(2, 1);  # should be at [17..18]

# Shift them
shift := function(g, off)
    local gens;
    gens := List(GeneratorsOfGroup(g), x -> ShiftPerm(x, off));
    if Length(gens) = 0 then return Group(()); fi;
    return Group(gens);
end;

# Use the ShiftGroup helper from the loaded code
T6s := ShiftGroup(T6, 0);
T5as := ShiftGroup(T5a, 6);
T5bs := ShiftGroup(T5b, 11);
T2s := ShiftGroup(T2, 16);

shifted := [T2s, T5as, T5bs, T6s];   # order in combo name: [2,1]_[5,5]_[5,5]_[6,5]
offs := [16, 6, 11, 0];

Print("Testing IsFPFSubdirect on bogus group with combo ordering [2,1],[5,5],[5,5],[6,5]\n");
Print("Result: ", IsFPFSubdirect(G, shifted, offs), "\n");

# Also try in a different factor order
shifted2 := [T6s, T5as, T5bs, T2s];
offs2 := [0, 6, 11, 16];
Print("\nAlternate ordering [6,5],[5,5],[5,5],[2,1]: ", IsFPFSubdirect(G, shifted2, offs2), "\n");

# Show block-wise what's happening
Print("\nBlock-wise analysis:\n");
for i in [1..Length(shifted2)] do
    Print("  Block at offset ", offs2[i], ", factor ",
          [NrMovedPoints(shifted2[i]), TransitiveIdentification(shifted2[i])], "\n");
    Print("    Generators restricted to [", offs2[i]+1, "..",
          offs2[i]+NrMovedPoints(shifted2[i]), "]:\n");
    for g in GeneratorsOfGroup(G) do
        Print("      ", RestrictedPerm(g, [offs2[i]+1..offs2[i]+NrMovedPoints(shifted2[i])]), "\n");
    od;
od;

LogTo();
QUIT;
