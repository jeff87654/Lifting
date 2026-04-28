LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/recompute_844_resume.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
RESTART_AFTER_SECONDS := 0;
HOLT_DISABLE_ISO_TRANSPORT := true;

CountAllConjugacyClassesFast(10);

outdir := "C:/Users/jeffr/Downloads/Lifting/parallel_s16_m6m7/[8,4,4]";
COMBO_OUTPUT_DIR := outdir;
if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
if IsBound(HOLT_TF_CACHE) then HOLT_TF_CACHE := rec(); fi;

t0 := Runtime();
r844 := FindFPFClassesForPartition(16, [8,4,4]);
e := (Runtime() - t0) / 1000.0;
Print("\n=== [8,4,4] = ", Length(r844), " in ", e, "s (expected 80189) ===\n");

PrintTo(Concatenation(outdir, "/summary.txt"),
        "partition: [8,4,4]\n",
        "total_classes: ", Length(r844), "\n",
        "session_added: ", Length(r844), "\n",
        "elapsed_seconds: ", e, "\n");

LogTo();
QUIT;
