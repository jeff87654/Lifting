LogTo("/cygdrive/c/Users/jeffr/Downloads/Lifting/test_load_ws.log");
Print("[t+", Runtime(), "ms] script start (lifting_algorithm.g already loaded from workspace)\n");
# Verify a function from lifting_algorithm.g is available
Print("FindFPFClassesByLifting bound: ", IsBound(FindFPFClassesByLifting), "\n");
QUIT;
