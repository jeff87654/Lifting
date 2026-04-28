
LogTo("C:/Users/jeffr/Downloads/Lifting/test_666.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\nUSE_GENERAL_AUT_HOM = ", USE_GENERAL_AUT_HOM, "\n");

T1 := TransitiveGroup(6, 12);;
T2 := TransitiveGroup(6, 14);;
T3 := TransitiveGroup(6, 14);;
Print("TG(6,12): |G|=", Size(T1), " desc=", StructureDescription(T1), "\n");
Print("TG(6,14): |G|=", Size(T2), " desc=", StructureDescription(T2), "\n");

partition := [6, 6, 6];;
factors := [T1, T2, T3];;

shifted := [ShiftGroup(T1, 0), ShiftGroup(T2, 6), ShiftGroup(T3, 12)];;
offsets := [0, 6, 12];;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));;
Print("|P| = ", Size(P), "\n\n");

N := BuildPerComboNormalizer(partition, factors, 18);;
Print("|N| = ", Size(N), "\n\n");

FPF_SUBDIRECT_CACHE := rec();

t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

Print("\n=== RESULT ===\n");
Print("Raw FPF candidates: ", Length(fpf), "\n");
Print("Elapsed: ", elapsed, "ms\n");

# Dedup
CURRENT_BLOCK_RANGES := [[1,6], [7,12], [13,18]];
deduped := [];
byInv := rec();
for H in fpf do
    AddIfNotConjugate(N, H, deduped, byInv, ComputeSubgroupInvariant);
od;
Print("Deduped: ", Length(deduped), "\n");
Print("Sizes: ", List(deduped, Size), "\n");

LogTo();
QUIT;
