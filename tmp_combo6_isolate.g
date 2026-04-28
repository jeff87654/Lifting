
LogTo("C:/Users/jeffr/Downloads/Lifting/test_combo6_isolate.log");

# ISOLATION: disable GeneralAutHomComplements before loading the file
# that defines it (the file only binds it if not already bound).
USE_GENERAL_AUT_HOM := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\nUSE_GENERAL_AUT_HOM = ", USE_GENERAL_AUT_HOM, "\n\n");

T5 := TransitiveGroup(5, 5);;
T2 := TransitiveGroup(2, 1);;
partition := [5, 5, 2, 2, 2, 2];;
factors := [T5, T5, T2, T2, T2, T2];;

shifted := [];
offsets := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offsets, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
N := BuildPerComboNormalizer(partition, factors, 18);

FPF_SUBDIRECT_CACHE := rec();

Print("Running FindFPFClassesByLifting with USE_GENERAL_AUT_HOM=false...\n");
t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

# Dedup under N
CURRENT_BLOCK_RANGES := [];
off := 0;
for k in [1..Length(partition)] do
    Add(CURRENT_BLOCK_RANGES, [off + 1, off + partition[k]]);
    off := off + partition[k];
od;
deduped := [];
byInv := rec();
for H in fpf do
    AddIfNotConjugate(N, H, deduped, byInv, ComputeSubgroupInvariant);
od;

Print("\n=== RESULT (USE_GENERAL_AUT_HOM=false) ===\n");
Print("Raw FPF candidates: ", Length(fpf), "\n");
Print("Deduped: ", Length(deduped), " classes\n");
Print("Elapsed: ", Float(elapsed/1000), "s\n");
Print("\nExpected (prebug): 154\n");
Print("Previous w506 (USE_GENERAL_AUT_HOM=true): 147\n");

LogTo();
QUIT;
