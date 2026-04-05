# lift_cache.g - Precomputed S_n conjugacy class counts
# These are the known total counts of conjugacy classes of subgroups.
# Loading this file populates LIFT_CACHE so that
# CountAllConjugacyClassesFast(n) returns immediately for n <= 16.
#
# All values verified against OEIS A000638.
# S15 value confirmed 2026-02-08. S17 value confirmed 2026-03-10.
# Usage: Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

LIFT_CACHE.("1") := 1;
LIFT_CACHE.("2") := 2;
LIFT_CACHE.("3") := 4;
LIFT_CACHE.("4") := 11;
LIFT_CACHE.("5") := 19;
LIFT_CACHE.("6") := 56;
LIFT_CACHE.("7") := 96;
LIFT_CACHE.("8") := 296;
LIFT_CACHE.("9") := 554;
LIFT_CACHE.("10") := 1593;
LIFT_CACHE.("11") := 3094;
LIFT_CACHE.("12") := 10723;
LIFT_CACHE.("13") := 20832;
LIFT_CACHE.("14") := 75154;
LIFT_CACHE.("15") := 159129;
LIFT_CACHE.("16") := 686165;
LIFT_CACHE.("17") := 1466358;

Print("Loaded LIFT_CACHE for S1-S17\n");
