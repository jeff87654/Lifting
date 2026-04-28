
LogTo("C:/Users/jeffr/Downloads/Lifting/diag_combo6_v3.log");

USE_GENERAL_AUT_HOM := true;
DIAG_GAH_VS_NSCR := false;
DIAG_GAH_DUMP_ALL_FILE := "C:/Users/jeffr/Downloads/Lifting/diag_combo6_v3_allcalls.g";

PrintTo("C:/Users/jeffr/Downloads/Lifting/diag_combo6_v3_allcalls.g", "GAH_ALL_CALLS := [];\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n[v3] USE_GENERAL_AUT_HOM = true (buggy mode)\n");
Print("[v3] dumping all GAH/HBC calls to ", DIAG_GAH_DUMP_ALL_FILE, "\n\n");

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

Print("[v3] |P|=", Size(P), " |N|=", Size(N), "\n");

t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

# Final dedup under N to compare to the 147 vs 154 question.
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
Print("[v3] raw FPF: ", Length(fpf), "\n");
Print("[v3] deduped (under N): ", Length(deduped), "\n");
Print("[v3] elapsed: ", Float(elapsed/1000), "s\n");
Print("[v3] expected (with GAH bug): 147\n");
Print("[v3] dump file: ", DIAG_GAH_DUMP_ALL_FILE, "\n");

LogTo();
QUIT;
