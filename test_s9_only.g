###############################################################################
# Test script for S9 only
###############################################################################

EXPECTED_S9 := 554;

# Load the lifting algorithm
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n========================================\n");
Print("Testing S9\n");
Print("========================================\n\n");

ResetH1TimingStats();

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

QUIT;
