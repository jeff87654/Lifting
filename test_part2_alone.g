LogTo("C:/Users/jeffr/Downloads/Lifting/test_part2_alone.log");
SetInfoLevel(InfoWarning, 0);
Print("Loading cycles part 2 alone...\n");
t0 := Runtime();
P2 := ReadAsFunction("C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache/s18_subgroups_cycles_part2.g")();
Print("Loaded ", Length(P2), " in ", (Runtime()-t0)/1000.0, "s\n");
LogTo();
QUIT;
