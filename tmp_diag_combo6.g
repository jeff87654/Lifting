
LogTo("C:/Users/jeffr/Downloads/Lifting/diag_combo6.log");

USE_GENERAL_AUT_HOM := true;
DIAG_GAH_VS_NSCR := true;
DIAG_GAH_MAX_Q_SIZE := 100000;
DIAG_GAH_DUMP_FILE := "C:/Users/jeffr/Downloads/Lifting/diag_combo6_diffs.g";

# Initialize the dump file with a fresh array.
PrintTo("C:/Users/jeffr/Downloads/Lifting/diag_combo6_diffs.g", "DIAG_GAH_DIFFERS_LOADED := [];\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n[diag] USE_GENERAL_AUT_HOM = ", USE_GENERAL_AUT_HOM, "\n");
Print("[diag] DIAG_GAH_VS_NSCR = ", DIAG_GAH_VS_NSCR,
      " (cap |Q| <= ", DIAG_GAH_MAX_Q_SIZE, ")\n\n");

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

Print("[diag] |P|=", Size(P), " |N|=", Size(N), "\n");
Print("[diag] starting FindFPFClassesByLifting...\n\n");

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

Print("\n=== RESULT ===\n");
Print("[diag] Raw FPF candidates: ", Length(fpf), "\n");
Print("[diag] Deduped: ", Length(deduped), " classes\n");
Print("[diag] Elapsed: ", Float(elapsed/1000), "s\n");
Print("[diag] DIAG_GAH_DIFFERS length: ", Length(DIAG_GAH_DIFFERS), "\n");

Print("[diag] divergent records (in ", "C:/Users/jeffr/Downloads/Lifting/diag_combo6_diffs.g", "): ",
      Length(DIAG_GAH_DIFFERS), "\n");

LogTo();
QUIT;
