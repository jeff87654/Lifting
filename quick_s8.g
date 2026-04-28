
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
startTime := Runtime();
result := CountAllConjugacyClassesFast(8);
elapsed := (Runtime() - startTime) / 1000.0;
Print("S8 Result: ", result, " Time: ", elapsed, "s
");
if result = 296 then Print("PASS
"); else Print("FAIL
"); fi;
QUIT;
