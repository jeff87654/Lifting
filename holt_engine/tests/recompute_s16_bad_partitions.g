LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/recompute_s16_bad.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
RESTART_AFTER_SECONDS := 0;
HOLT_DISABLE_ISO_TRANSPORT := true;  # the fix

CountAllConjugacyClassesFast(10);

# Runs with per-combo output persisted to the parallel_s16_m6m7 dirs.
RunOnePart := function(partition)
  local t0, res, e, outdir;
  outdir := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_s16_m6m7/[",
                           JoinStringsWithSeparator(List(partition, String), ","),
                           "]");
  COMBO_OUTPUT_DIR := outdir;
  if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
  if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
  if IsBound(HOLT_TF_CACHE) then HOLT_TF_CACHE := rec(); fi;
  t0 := Runtime();
  res := FindFPFClassesForPartition(16, partition);
  e := (Runtime() - t0) / 1000.0;
  Print("\n=== ", partition, " = ", Length(res), " in ", e, "s ===\n");
  # Write summary.txt
  PrintTo(Concatenation(outdir, "/summary.txt"),
          "partition: [",
          JoinStringsWithSeparator(List(partition, String), ","), "]\n",
          "total_classes: ", Length(res), "\n",
          "session_added: ", Length(res), "\n",
          "elapsed_seconds: ", e, "\n");
  return Length(res);
end;

r862 := RunOnePart([8,6,2]);
Print("expected [8,6,2] = 29440, got ", r862, "\n");

r844 := RunOnePart([8,4,4]);
Print("expected [8,4,4] = 80189, got ", r844, "\n");

Print("\n=== FINAL ===\n");
Print("[8,6,2]: ", r862, " / 29440\n");
Print("[8,4,4]: ", r844, " / 80189\n");

LogTo();
QUIT;
