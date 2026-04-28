###############################################################################
# Test script for cohomology optimizations
# Tests S2-S8 to verify correctness before running full S10 benchmark
###############################################################################

# Expected results (OEIS A006118 for S_n)
EXPECTED_COUNTS := [2, 4, 11, 19, 56, 96, 296];

# Load the lifting algorithm
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Run tests
Print("\n========================================\n");
Print("Testing Cohomology Optimizations\n");
Print("========================================\n\n");

ResetH1TimingStats();

all_passed := true;

for n in [2..8] do
    Print("Testing S", n, "...\n");
    start_time := Runtime();

    # Use the fast method
    count := CountAllConjugacyClassesFast(n);

    elapsed := (Runtime() - start_time) / 1000.0;
    expected := EXPECTED_COUNTS[n-1];

    if count = expected then
        Print("  PASS: S", n, " = ", count, " (expected ", expected, ") in ", elapsed, "s\n");
    else
        Print("  FAIL: S", n, " = ", count, " (expected ", expected, ") in ", elapsed, "s\n");
        all_passed := false;
    fi;
od;

Print("\n========================================\n");
if all_passed then
    Print("All tests PASSED!\n");
else
    Print("Some tests FAILED!\n");
fi;
Print("========================================\n");

PrintH1TimingStats();

QUIT;
