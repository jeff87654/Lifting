LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/bench_m8m9.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;

CountAllConjugacyClassesFast(10);

RunPart := function(n, p, expected, mode)
  local t0, r, e;
  if mode = "baseline" then
    HOLT_DISABLE_CANON_DEDUP := true;
    HOLT_DISABLE_UF_DEDUP := true;
  elif mode = "m8" then
    HOLT_DISABLE_CANON_DEDUP := false;
    HOLT_DISABLE_UF_DEDUP := true;
  elif mode = "m8m9" then
    HOLT_DISABLE_CANON_DEDUP := false;
    HOLT_DISABLE_UF_DEDUP := false;
  fi;
  HOLT_ENGINE_MODE := "clean_first";
  if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
  if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
  t0 := Runtime();
  r := FindFPFClassesForPartition(n, p);
  e := (Runtime() - t0) / 1000.0;
  Print("[", mode, "] ", p, " = ", Length(r), " (expected ", expected, ") in ", e, "s\n");
  return rec(n := Length(r), t := e);
end;

# [5,5,5] expected 155
b5 := RunPart(15, [5,5,5], 155, "baseline");
m5 := RunPart(15, [5,5,5], 155, "m8");
u5 := RunPart(15, [5,5,5], 155, "m8m9");

# [6,4,3,2] was 1949s in v2 — test on smaller [4,4,4,2] of S_14 instead (~5min)
# |P|=192 per combo typically, should be manageable
b2 := RunPart(14, [4,4,4,2], 2092, "baseline");
m2 := RunPart(14, [4,4,4,2], 2092, "m8");
u2 := RunPart(14, [4,4,4,2], 2092, "m8m9");

Print("\n=== SUMMARY ===\n");
Print("[5,5,5]:   baseline ", b5.t, "s, m8 ", m5.t, "s (",
      Float(b5.t / m5.t), "x), m8m9 ", u5.t, "s (", Float(b5.t / u5.t), "x)\n");
Print("[4,4,4,2]: baseline ", b2.t, "s, m8 ", m2.t, "s (",
      Float(b2.t / m2.t), "x), m8m9 ", u2.t, "s (", Float(b2.t / u2.t), "x)\n");

LogTo();
QUIT;
