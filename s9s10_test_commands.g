
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("Testing S9 (expected 554)...\n");
startTime := Runtime();
result9 := CountAllConjugacyClassesFast(9);
elapsed9 := (Runtime() - startTime) / 1000.0;
if result9 = 554 then
    Print("S_9: PASS (", result9, ") in ", elapsed9, "s\n");
else
    Print("S_9: FAIL (got ", result9, ", expected 554) in ", elapsed9, "s\n");
fi;

Print("\nTesting S10 (expected 1593)...\n");
startTime := Runtime();
result10 := CountAllConjugacyClassesFast(10);
elapsed10 := (Runtime() - startTime) / 1000.0;
if result10 = 1593 then
    Print("S_10: PASS (", result10, ") in ", elapsed10, "s\n");
else
    Print("S_10: FAIL (got ", result10, ", expected 1593) in ", elapsed10, "s\n");
fi;

Print("\nH^1 Stats:\n");
PrintH1TimingStats();

QUIT;
