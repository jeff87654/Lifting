
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Print("Testing S6...\n");
result := CountAllConjugacyClassesFast(6);
Print("S6 Result: ", result, " (expected: 56)\n");
if result = 56 then Print("PASS\n"); else Print("FAIL\n"); fi;
QUIT;
