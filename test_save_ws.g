LogTo("/cygdrive/c/Users/jeffr/Downloads/Lifting/test_save_ws.log");
Print("[t+", Runtime(), "ms] starting...\n");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
Print("[t+", Runtime(), "ms] lifting_algorithm.g loaded\n");
SaveWorkspace("/cygdrive/c/Users/jeffr/Downloads/Lifting/lifting.ws");
Print("[t+", Runtime(), "ms] workspace saved\n");
QUIT;
