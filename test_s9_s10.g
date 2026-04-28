###############################################################################
# Test script for S9 and S10
###############################################################################

# Expected results
EXPECTED_S9 := 554;
EXPECTED_S10 := 1593;

# Load the lifting algorithm
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n========================================\n");
Print("Testing S9 and S10\n");
Print("========================================\n\n");

ResetH1TimingStats();

# Test S9
Print("Testing S9...\n");
start_time := Runtime();
count9 := CountAllConjugacyClassesFast(9);
elapsed9 := (Runtime() - start_time) / 1000.0;

if count9 = EXPECTED_S9 then
    Print("  PASS: S9 = ", count9, " (expected ", EXPECTED_S9, ") in ", elapsed9, "s\n");
else
    Print("  FAIL: S9 = ", count9, " (expected ", EXPECTED_S9, ") in ", elapsed9, "s\n");
fi;

PrintH1TimingStats();
ResetH1TimingStats();

# Test S10
Print("\nTesting S10...\n");
start_time := Runtime();
count10 := CountAllConjugacyClassesFast(10);
elapsed10 := (Runtime() - start_time) / 1000.0;

if count10 = EXPECTED_S10 then
    Print("  PASS: S10 = ", count10, " (expected ", EXPECTED_S10, ") in ", elapsed10, "s\n");
else
    Print("  FAIL: S10 = ", count10, " (expected ", EXPECTED_S10, ") in ", elapsed10, "s\n");
fi;

Print("\n========================================\n");
Print("Summary:\n");
Print("  S9:  ", count9, " in ", elapsed9, "s\n");
Print("  S10: ", count10, " in ", elapsed10, "s\n");
Print("========================================\n");

PrintH1TimingStats();

QUIT;
