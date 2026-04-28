
LogTo("C:/Users/jeffr/Downloads/Lifting/test_d4_remap.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Test the specific combo that was crashing: [4,3]^3 x [6,15]
# This is from partition [6,4,4,4]
# depth=1 (degree 6): TG(6,15) at offset 0 -> [1..6]
# depth=2 (degree 4): TG(4,3) at offset 6 -> [7..10]
# depth=3 (degree 4): TG(4,3) at offset 10 -> [11..14]
# depth=4 (degree 4): TG(4,3) at offset 14 -> [15..18]

Print("Building shifted factors for [6,4,4,4] combo [6,15],[4,3],[4,3],[4,3]...\n");
shifted := [
    ShiftGroup(TransitiveGroup(6,15), 0),   # A_6 on [1..6]
    ShiftGroup(TransitiveGroup(4,3), 6),    # D_4 on [7..10]
    ShiftGroup(TransitiveGroup(4,3), 10),   # D_4 on [11..14]
    ShiftGroup(TransitiveGroup(4,3), 14),   # D_4 on [15..18]
];
offs := [0, 6, 10, 14];
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("|P| = ", Size(P), "\n");

N := BuildPerComboNormalizer([6,4,4,4], shifted, 18);
Print("|N| = ", Size(N), "\n");

Print("Calling FindFPFClassesByLifting...\n");
t0 := Runtime();
result := FindFPFClassesByLifting(P, shifted, offs, N);
t1 := Runtime() - t0;
Print("Result: ", Length(result), " groups in ", t1/1000.0, "s\n");

# Verify groups act on correct domain and are FPF
Print("Verifying results...\n");
bad := 0;
for H in result do
    moved := MovedPoints(H);
    if not IsSubset([1..18], moved) then
        Print("  BAD: moved points outside [1..18]: ", moved, "\n");
        bad := bad + 1;
    fi;
    # Check FPF: transitive on each block
    if not IsTransitive(H, [1..6]) then
        Print("  BAD: not transitive on [1..6], orbits=", Orbits(H, [1..6]), "\n");
        bad := bad + 1;
    fi;
    if not IsTransitive(H, [7..10]) then
        Print("  BAD: not transitive on [7..10]\n");
        bad := bad + 1;
    fi;
    if not IsTransitive(H, [11..14]) then
        Print("  BAD: not transitive on [11..14]\n");
        bad := bad + 1;
    fi;
    if not IsTransitive(H, [15..18]) then
        Print("  BAD: not transitive on [15..18]\n");
        bad := bad + 1;
    fi;
od;
if bad = 0 then
    Print("ALL ", Length(result), " groups PASS FPF check\n");
else
    Print(bad, " FAILURES\n");
fi;

# Also test that the invariant computation works (this is where the crash was)
Print("Testing invariant computation...\n");
CURRENT_BLOCK_RANGES := [[1,6],[7,10],[11,14],[15,18]];
for i in [1..Minimum(5, Length(result))] do
    inv := ComputeSubgroupInvariant(result[i]);
    Print("  group ", i, " size=", Size(result[i]), " inv_len=", Length(inv), "\n");
od;
Print("Invariant computation OK\n");

LogTo();
QUIT;
