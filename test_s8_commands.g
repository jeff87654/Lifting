
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Print("Testing S8...\n");
result := CountAllConjugacyClassesFast(8);
Print("S8 Result: ", result, " (expected: 296)\n");
if result = 296 then Print("PASS\n"); else Print("FAIL\n"); fi;
QUIT;
