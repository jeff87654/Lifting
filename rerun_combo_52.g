# Rerun combo #52 of partition [4,4,4,3,2] for S17
# Key: [[2,1],[3,2],[4,3],[4,3],[4,3]]
# Factors in partition order: S4, S4, S4, S3, C2
# Expected: 11792 FPF classes (from checkpoint before OOM)

LogTo("C:/Users/jeffr/Downloads/Lifting/rerun_combo_52.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load precomputed caches
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("=== Rerunning combo #52 of [4,4,4,3,2] ===\n");
Print("Factors: S4 x S4 x S4 x S3 x C2\n");
Print("Key: [[2,1],[3,2],[4,3],[4,3],[4,3]]\n\n");

# Build factors in partition order [4,4,4,3,2]
f1 := TransitiveGroup(4, 3);  # S4 on {1..4}
f2 := TransitiveGroup(4, 3);  # S4 on {5..8}
f3 := TransitiveGroup(4, 3);  # S4 on {9..12}
f4 := TransitiveGroup(3, 2);  # S3 on {13..15}
f5 := TransitiveGroup(2, 1);  # C2 on {16..17}

# Shift to non-overlapping point sets
s1 := f1;                      # offset 0, points 1-4
s2 := ShiftGroup(f2, 4);      # offset 4, points 5-8
s3 := ShiftGroup(f3, 8);      # offset 8, points 9-12
s4 := ShiftGroup(f4, 12);     # offset 12, points 13-15
s5 := ShiftGroup(f5, 15);     # offset 15, points 16-17

shifted := [s1, s2, s3, s4, s5];
offsets := [0, 4, 8, 12, 15];

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P order: ", Size(P), "\n");
Print("P moved points: ", MovedPoints(P), "\n\n");

# Build partition normalizer (same as FindFPFClassesForPartition uses)
N := BuildConjugacyTestGroup(17, [4,4,4,3,2]);
Print("Partition normalizer |N| = ", Size(N), "\n\n");

# Clear any FPF cache for this key to force recomputation
cacheKey := "[ [ 2, 1 ], [ 3, 2 ], [ 4, 3 ], [ 4, 3 ], [ 4, 3 ] ]";
if IsBound(FPF_SUBDIRECT_CACHE.(cacheKey)) then
    Unbind(FPF_SUBDIRECT_CACHE.(cacheKey));
    Print("Cleared FPF cache for this key\n");
fi;

Print("Starting FindFPFClassesByLifting...\n");
t0 := Runtime();

result := FindFPFClassesByLifting(P, shifted, offsets, N);

elapsed := Runtime() - t0;
Print("\n=== RESULT ===\n");
Print("FPF classes found: ", Length(result), "\n");
Print("Expected: 11792\n");
Print("Match: ", Length(result) = 11792, "\n");
Print("Elapsed time: ", elapsed / 1000.0, " seconds\n");

LogTo();
QUIT;
