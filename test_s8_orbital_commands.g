
LogTo("C:/Users/jeffr/Downloads/Lifting/test_s8_orbital_output.txt");
Print("S8 Test with H^1 Orbital Optimization\n");
Print("======================================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("Configuration:\n");
Print("  USE_H1_COMPLEMENTS: ", USE_H1_COMPLEMENTS, "\n");
if IsBound(USE_H1_ORBITAL) then
    Print("  USE_H1_ORBITAL: ", USE_H1_ORBITAL, "\n");
else
    Print("  USE_H1_ORBITAL: not defined\n");
fi;
Print("\n");

# Reset statistics
ResetH1TimingStats();
if IsBound(ResetH1OrbitalStats) then
    ResetH1OrbitalStats();
fi;

Print("Running S8 enumeration...\n");
startTime := Runtime();
result := CountAllConjugacyClassesFast(8);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\nS8 Result: ", result, " (expected: 296)\n");
Print("Time: ", elapsed, " seconds\n");

if result = 296 then
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

Print("\n========================================\n");
Print("Test Complete\n");
Print("========================================\n");
LogTo();
QUIT;
