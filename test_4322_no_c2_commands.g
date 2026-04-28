
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear the cache to avoid cached C2 results
FPF_SUBDIRECT_CACHE := rec();

Print("\n=== Test 1: [4,3,2,2] with C2 opt (default) ===\n");
startTime := Runtime();
result1 := FindFPFClassesForPartition(11, [4, 3, 2, 2]);
elapsed1 := (Runtime() - startTime) / 1000.0;
Print("Count with C2: ", Length(result1), " (expected 195), time: ", elapsed1, "s\n");

# Now test with just the lifting method directly for ONE combination
# The non-trivial transitive groups for degree 4: S4, A4, D4, C4, V4
# For degree 3: S3, A3=C3
# For degree 2: S2=C2
# Let's manually construct the product and call FindFPFClassesByLifting

Print("\n=== Test 2: Direct lifting for (S4, S3, C2, C2) ===\n");
T4 := SymmetricGroup(4);
T3 := SymmetricGroup(3);
T2 := Group((1,2));

# Shift to coordinates [1..4], [5..7], [8,9], [10,11]
shifted4 := Image(ActionHomomorphism(T4, [1..4]), T4);
shifted3 := Image(ActionHomomorphism(T3, [5..7],
    OnPoints, function(x) return x + 4; end), T3);

# Actually, use the proper shifting
phi4 := MappingPermListList([1,2,3,4], [1,2,3,4]);
phi3 := MappingPermListList([1,2,3], [5,6,7]);
phi2a := MappingPermListList([1,2], [8,9]);
phi2b := MappingPermListList([1,2], [10,11]);

s4 := Group(List(GeneratorsOfGroup(T4), g -> g));
s3 := Group(List(GeneratorsOfGroup(T3), g ->
    PermList(List([1..11], function(x)
        if x >= 5 and x <= 7 then
            return Image(T3.1, x-4) + 4;  # wrong approach
        fi;
        return x;
    end))));

# This is getting complicated. Let me just use the shifting functions from the codebase.
Print("\nUsing ShiftPerm to build shifted groups...\n");

# Get the shifted groups that FindFPFClassesForPartition would use
# For partition [4,3,2,2], offsets are [0, 4, 7, 9]
offsets := [0, 4, 7, 9];
n := 11;

# Build shifted transitive groups
shifted := [];

# Degree 4, offset 0: S4 acting on {1,2,3,4}
Add(shifted, SymmetricGroup([1..4]));

# Degree 3, offset 4: S3 acting on {5,6,7}
Add(shifted, SymmetricGroup([5..7]));

# Degree 2, offset 7: C2 acting on {8,9}
Add(shifted, SymmetricGroup([8..9]));

# Degree 2, offset 9: C2 acting on {10,11}
Add(shifted, SymmetricGroup([10..11]));

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P = product of (S4, S3, S2, S2), |P| = ", Size(P), "\n");

Print("\nCalling FindFPFClassesByLifting directly...\n");
startTime := Runtime();
liftResult := FindFPFClassesByLifting(P, shifted, offsets);
elapsed := (Runtime() - startTime) / 1000.0;
Print("Direct lifting count for (S4, S3, S2, S2): ", Length(liftResult), "\n");
Print("Time: ", elapsed, "s\n");

QUIT;
