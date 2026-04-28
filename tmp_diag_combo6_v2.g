
LogTo("C:/Users/jeffr/Downloads/Lifting/diag_combo6_v2.log");

USE_GENERAL_AUT_HOM := false;
DIAG_GAH_VS_NSCR := true;
DIAG_GAH_MAX_Q_SIZE := 250000;
DIAG_GAH_DUMP_FILE := "C:/Users/jeffr/Downloads/Lifting/diag_combo6_v2_diffs.g";

PrintTo("C:/Users/jeffr/Downloads/Lifting/diag_combo6_v2_diffs.g", "DIAG_GAH_DIFFERS_LOADED := [];\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n[diag-v2] USE_GENERAL_AUT_HOM = ", USE_GENERAL_AUT_HOM,
      " (matches W506)\n");
Print("[diag-v2] DIAG_GAH_VS_NSCR = ", DIAG_GAH_VS_NSCR,
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

Print("[diag-v2] |P|=", Size(P), " |N|=", Size(N), "\n");
Print("[diag-v2] starting FindFPFClassesByLifting...\n\n");

t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

Print("\n=== RESULT ===\n");
Print("[diag-v2] Raw FPF: ", Length(fpf), "\n");
Print("[diag-v2] DIAG_GAH_DIFFERS records: ", Length(DIAG_GAH_DIFFERS), "\n");
Print("[diag-v2] Elapsed: ", Float(elapsed/1000), "s\n");

LogTo();
QUIT;
