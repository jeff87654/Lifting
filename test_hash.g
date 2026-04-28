LogTo("C:/Users/jeffr/Downloads/Lifting/test_hash.log");
Print("Testing _ComputeCodeHash...\n");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Print("Loaded. Now calling _ComputeCodeHash():\n");
t0 := Runtime();
h := _ComputeCodeHash();
Print("Hash: ", h, " (", Runtime() - t0, "ms)\n");
LogTo();
QUIT;
