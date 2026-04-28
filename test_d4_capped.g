Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

progressFile := "C:/Users/jeffr/Downloads/Lifting/test_d4_capped_progress.log";
PrintTo(progressFile, "=== D_4^3 capped Aut test on [3,2]^2 x [4,3]^3 ===\n");
AppendTo(progressFile, "GOURSAT_MAX_FULL_AUT_Q = ", GOURSAT_MAX_FULL_AUT_Q, "\n\n");

combo := [[3,2],[3,2],[4,3],[4,3],[4,3]];
shifted := [];
offs := [];
pos := 0;
for c in combo do
    G := TransitiveGroup(c[1], c[2]);
    Add(shifted, ShiftGroup(G, pos));
    Add(offs, pos);
    pos := pos + c[1];
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
normArg := BuildPerComboNormalizer([4,4,4,3,3], shifted, 18);
AppendTo(progressFile, "|P| = ", Size(P), ", |N| = ", Size(normArg), "\n\n");

t0 := Runtime();
result := FindFPFClassesByLifting(P, shifted, offs, normArg);
tLift := Runtime() - t0;

AppendTo(progressFile, "Candidates: ", Length(result), "\n");
AppendTo(progressFile, "Time: ", Int(tLift/1000), "s\n");
AppendTo(progressFile, "Expected after dedup: 26956\n");
AppendTo(progressFile, "Overcounting ratio: ", Float(Length(result))/26956.0, "\n");

QUIT;
