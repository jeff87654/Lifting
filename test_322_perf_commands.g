
LogTo("C:/Users/jeffr/Downloads/Lifting/test_322_perf_output.txt");
Print("Performance Analysis: [3,2,2] partition\n");
Print("=========================================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Reset stats
ResetH1TimingStats();
if IsBound(ResetH1OrbitalStats) then
    ResetH1OrbitalStats();
fi;

Print("Testing [3,2,2] partition of S7...\n\n");

# Set up partition [3,2,2] - same as in lifting_method_fast_v2.g
S3 := SymmetricGroup(3);
S2a := SymmetricGroup(2);
S2b := ShiftGroup(S2a, 3);
S2c := ShiftGroup(S2a, 5);
S3shifted := S3;

shifted := [S3shifted, S2b, S2c];
offs := [0, 3, 5];

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("|P| = ", Size(P), "\n");
Print("Factors: S3 x S2 x S2\n\n");

# Time the enumeration with orbital
Print("=== With USE_H1_ORBITAL := true ===\n");
USE_H1_ORBITAL := true;
ResetH1TimingStats();
if IsBound(ResetH1OrbitalStats) then
    ResetH1OrbitalStats();
fi;

startTime := Runtime();
result := FindFPFClassesByLifting(P, shifted, offs);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\n");
Print("Result: ", Length(result), " classes\n");
Print("Time: ", elapsed, " seconds\n\n");

Print("H^1 Timing Stats:\n");
PrintH1TimingStats();

if IsBound(PrintH1OrbitalStats) then
    Print("\nH^1 Orbital Stats:\n");
    PrintH1OrbitalStats();
fi;

Print("\n\n========================================\n");
Print("=== With USE_H1_ORBITAL := false ===\n");
Print("========================================\n\n");

USE_H1_ORBITAL := false;
ClearH1Cache();  # Clear cache to ensure fair comparison
ResetH1TimingStats();
if IsBound(ResetH1OrbitalStats) then
    ResetH1OrbitalStats();
fi;

startTime := Runtime();
result2 := FindFPFClassesByLifting(P, shifted, offs);
elapsed2 := (Runtime() - startTime) / 1000.0;

Print("\n");
Print("Result: ", Length(result2), " classes\n");
Print("Time: ", elapsed2, " seconds\n\n");

Print("H^1 Timing Stats (without orbital):\n");
PrintH1TimingStats();

Print("\n========================================\n");
Print("Comparison:\n");
Print("  With orbital:    ", elapsed, "s\n");
Print("  Without orbital: ", elapsed2, "s\n");
if elapsed < elapsed2 then
    Print("  Orbital speedup: ", Float(elapsed2/elapsed), "x\n");
elif elapsed > elapsed2 then
    Print("  Orbital slowdown: ", Float(elapsed/elapsed2), "x\n");
else
    Print("  No difference\n");
fi;
Print("========================================\n");

LogTo();
QUIT;
