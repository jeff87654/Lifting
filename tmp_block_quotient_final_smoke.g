
LogTo("C:/Users/jeffr/Downloads/Lifting/tmp_block_quotient_final_smoke.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
CHECKPOINT_DIR := "";
COMBO_OUTPUT_DIR := "";
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
Print("LOADED_OK\n");
t0 := Runtime();
r := FindFPFClassesForPartition(12, [5,5,2]);
t := (Runtime() - t0) / 1000.0;
Print("smoke count=", Length(r), " time=", t, "s\n");
LogTo();
QUIT;
