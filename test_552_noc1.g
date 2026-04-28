LogTo("C:/Users/jeffr/Downloads/Lifting/test_552_noc1.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Test 1: Normal run (Phase C1 ON) - should give 61 (buggy)
startTime := Runtime();
r1 := FindFPFClassesForPartition(12, [5,5,2]);
t1 := (Runtime() - startTime) / 1000.0;
Print("WITH Phase C1: [5,5,2] = ", Length(r1), " (expected 62), time = ", t1, "s\n");

# Test 2: Disable Phase C1 by monkey-patching FindFPFClassesByLifting
# Save the original function
_OrigFindFPFClassesByLifting := FindFPFClassesByLifting;

# Wrapper that drops the partNormalizer argument
FindFPFClassesByLifting := function(P, shifted_factors, offsets, partNormalizer...)
    # Call original WITHOUT the partition normalizer (Phase C1 disabled)
    return _OrigFindFPFClassesByLifting(P, shifted_factors, offsets);
end;

if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
FPF_SUBDIRECT_CACHE := rec();

startTime := Runtime();
r2 := FindFPFClassesForPartition(12, [5,5,2]);
t2 := (Runtime() - startTime) / 1000.0;
Print("WITHOUT Phase C1: [5,5,2] = ", Length(r2), " (expected 62), time = ", t2, "s\n");

# Restore original
FindFPFClassesByLifting := _OrigFindFPFClassesByLifting;

if Length(r1) <> Length(r2) then
    Print("*** Phase C1 changes the count! C1_ON=", Length(r1), " C1_OFF=", Length(r2), " ***\n");
else
    Print("Phase C1 does NOT affect count (both = ", Length(r1), ")\n");
fi;

LogTo();
QUIT;
