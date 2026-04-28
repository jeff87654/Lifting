LogTo("/cygdrive/c/Users/jeffr/Downloads/Lifting/test_empty.log");
t0 := Runtime();
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
t1 := Runtime();
Print("Load time: ", t1 - t0, "ms\n");
QUIT;
