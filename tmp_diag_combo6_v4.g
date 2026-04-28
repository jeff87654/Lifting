
LogTo("C:/Users/jeffr/Downloads/Lifting/diag_combo6_v4.log");

USE_GENERAL_AUT_HOM := true;
DIAG_GAH_VS_NSCR := true;
DIAG_GAH_MAX_Q_SIZE := 100000;
DIAG_GAH_DUMP_FILE := "C:/Users/jeffr/Downloads/Lifting/diag_combo6_v4_diffs.g";

PrintTo("C:/Users/jeffr/Downloads/Lifting/diag_combo6_v4_diffs.g", "DIAG_GAH_DIFFERS_LOADED := [];\n");

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

Print("\n[v4] |P|=", Size(P), " (cap |Q|<=", DIAG_GAH_MAX_Q_SIZE, ")\n\n");

t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

Print("\n=== RESULT ===\n");
Print("[v4] raw FPF: ", Length(fpf), "\n");
Print("[v4] divergent records: ", Length(DIAG_GAH_DIFFERS), "\n");
Print("[v4] elapsed: ", Float(elapsed/1000), "s\n");

LogTo();
QUIT;
