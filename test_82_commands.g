
LogTo("C:/Users/jeffr/Downloads/Lifting/test_82_output.txt");
Print("Testing [8,2] partition with lowered maximal descent threshold\n");
Print("=============================================================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("Testing partition [8,2] for S10:\n");
Print("================================\n\n");

startTime := Runtime();
result := FindFPFClassesForPartition(10, [8,2]);
elapsed := (Runtime() - startTime) / 1000.0;

Print("\n[8,2] Result: ", Length(result), " classes\n");
Print("Time: ", elapsed, " seconds\n");
Print("(Previous time was 242 seconds)\n");

Print("\n=============================================================\n");
Print("Test Complete\n");
Print("=============================================================\n");
LogTo();
QUIT;
