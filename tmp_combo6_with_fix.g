
LogTo("C:/Users/jeffr/Downloads/Lifting/combo6_with_fix.log");

USE_GENERAL_AUT_HOM := true;
DIAG_GAH_VS_NSCR := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

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

Print("\n[fix] |P|=", Size(P), " |N|=", Size(N), "\n");
Print("[fix] starting FindFPFClassesByLifting (USE_GENERAL_AUT_HOM=true with FIX)...\n\n");

t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

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

Print("\n=== RESULT ===\n");
Print("[fix] Raw FPF: ", Length(fpf), "\n");
Print("[fix] Deduped: ", Length(deduped), " classes\n");
Print("[fix] Elapsed: ", Float(elapsed/1000), "s\n");
Print("[fix] Expected: 154 (prebug baseline)\n");
if Length(deduped) = 154 then
    Print("[fix] *** MATCH: bug fixed! ***\n");
else
    Print("[fix] *** MISMATCH: still ", Length(deduped) - 154, " off\n");
fi;

LogTo();
QUIT;
