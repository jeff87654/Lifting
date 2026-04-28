
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/profiling.g");

Print("\nProfiling S9...\n\n");
startTime := Runtime();
result := CountAllConjugacyClassesFast(9);
totalTime := Runtime() - startTime;

Print("\nS_9 Result: ", result, " (expected 554)\n");
Print("Total time: ", totalTime / 1000.0, "s\n\n");

PrintProfilingReport();
QUIT;
