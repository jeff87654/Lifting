
LogTo("C:/Users/jeffr/Downloads/Lifting/test_s10_output.txt");
Print("Testing S10 with lowered maximal descent threshold\n");
Print("===================================================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Pre-populate cache with S2-S9 results (known values)
LIFT_CACHE.("1") := 1;
LIFT_CACHE.("2") := 2;
LIFT_CACHE.("3") := 4;
LIFT_CACHE.("4") := 11;
LIFT_CACHE.("5") := 19;
LIFT_CACHE.("6") := 56;
LIFT_CACHE.("7") := 96;
LIFT_CACHE.("8") := 296;
LIFT_CACHE.("9") := 554;

Print("Testing S10 (expected: 1593)\n");
Print("============================\n\n");

startTime := Runtime();
result := CountAllConjugacyClassesFast(10);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\nS10 Result: ", result, "\n");
Print("Expected: 1593\n");
if result = 1593 then
    Print("Status: PASS\n");
else
    Print("Status: FAIL\n");
fi;
Print("Time: ", elapsed, " seconds\n");
Print("(Previous time was 740 seconds / 12.3 minutes)\n");

Print("\n===================================================\n");
Print("Test Complete\n");
Print("===================================================\n");
LogTo();
QUIT;
