
LogTo("C:/Users/jeffr/Downloads/Lifting/tmp_block_quotient_smoke.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
CHECKPOINT_DIR := "";
COMBO_OUTPUT_DIR := "";
RunOne := function(label, disable)
  local t0, r, t;
  FPF_SUBDIRECT_CACHE := rec();
  if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
  if IsBound(HOLT_TF_CACHE) then HOLT_TF_CACHE := rec(); fi;
  HOLT_DISABLE_BLOCK_QUOTIENT_DEDUP := disable;
  HOLT_UF_INDEX_BUCKET_MIN := 40;
  t0 := Runtime();
  r := FindFPFClassesForPartition(12, [5,5,2]);
  t := (Runtime() - t0) / 1000.0;
  Print(label, " count=", Length(r), " time=", t, "s\n");
end;
RunOne("disabled", true);
RunOne("enabled", false);
LogTo();
QUIT;
