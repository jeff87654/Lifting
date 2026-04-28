
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_test_output.txt");
Print("Debug Test - [4,2,2] partition\n");
Print("================================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\nTesting partition [4,2,2] for S8:\n");
Print("================================\n\n");

startTime := Runtime();

# Test just the [4,2,2] partition
result := FindFPFClassesForPartition(8, [4,2,2]);
elapsed := (Runtime() - startTime) / 1000.0;
Print("\n[4,2,2] Result: ", Length(result), " classes\n");
Print("Time: ", elapsed, " seconds\n");

Print("\n\n================================\n");
Print("Debug Test Complete\n");
Print("================================\n");
LogTo();
QUIT;
