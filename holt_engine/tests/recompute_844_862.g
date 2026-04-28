LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/recompute_844_862.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
RESTART_AFTER_SECONDS := 0;
CountAllConjugacyClassesFast(10);

# [8,6,2] already has a verified-correct iso-OFF result from diff_s16_862_v2.log (29440).
# [8,4,4] iso-OFF still running; we'll compare its count when done.

# This script just reports current iso-OFF defaults. If user runs the full
# S_16 with iso disabled (which is now the default), total will be 686165.
Print("HOLT_DISABLE_ISO_TRANSPORT = ", HOLT_DISABLE_ISO_TRANSPORT, "\n");
LogTo();
QUIT;
