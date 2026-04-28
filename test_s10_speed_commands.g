
LogTo("C:/Users/jeffr/Downloads/Lifting/test_s10_speed_output.txt");
Print("S10 Speed Test with H^1 Orbital Optimization\n");
Print("=============================================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("Configuration:\n");
Print("  USE_H1_COMPLEMENTS: ", USE_H1_COMPLEMENTS, "\n");
Print("  USE_H1_ORBITAL: ", USE_H1_ORBITAL, "\n\n");

# Reset statistics
ResetH1TimingStats();
if IsBound(ResetH1OrbitalStats) then
    ResetH1OrbitalStats();
fi;

Print("Running S10 enumeration...\n\n");
startTime := Runtime();
result := CountAllConjugacyClassesFast(10);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\n");
Print("============================================\n");
Print("S10 Result: ", result, " (expected: 1593)\n");
Print("Total Time: ", elapsed, " seconds\n");
Print("============================================\n");

if result = 1593 then
    Print("Status: PASS\n");
else
    Print("Status: FAIL\n");
fi;

Print("\nH^1 Timing Statistics:\n");
PrintH1TimingStats();

if IsBound(PrintH1OrbitalStats) then
    Print("\nH^1 Orbital Statistics:\n");
    PrintH1OrbitalStats();
fi;

LogTo();
QUIT;
