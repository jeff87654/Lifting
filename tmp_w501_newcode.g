
LogTo("C:/Users/jeffr/Downloads/Lifting/w501_newcode.log");
GENERAL_AUT_HOM_VERBOSE := true;
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n========== W501 combo with NEW code ==========\n");

T1 := TransitiveGroup(6, 16);
T2 := TransitiveGroup(12, 242);
shifted := [ShiftGroup(T1, 0), ShiftGroup(T2, 6)];
offsets := [0, 6];
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("|P| = ", Size(P), "\n");
N := BuildPerComboNormalizer([6, 12], [T1, T2], 18);
Print("|N| = ", Size(N), "\n\n");

t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

Print("\nRESULT: ", Length(fpf), " raw FPF, ",
      Float(elapsed/1000), "s\n");

LogTo();
QUIT;
