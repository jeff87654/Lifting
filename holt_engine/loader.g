# holt_engine/loader.g
#
# Single entry point: Read("holt_engine/loader.g") loads the whole engine.
# Files are listed in dependency order (leaves first, engine last).
#
# Feature flag:
#   USE_HOLT_ENGINE        false by default; Phase 4 flips this on to route
#                          FindFPFClassesForPartition through the new engine
#                          instead of FindFPFClassesByLifting.

if not IsBound(USE_HOLT_ENGINE) then
  USE_HOLT_ENGINE := false;
fi;

HOLT_ENGINE_DIR := "C:/Users/jeffr/Downloads/Lifting/holt_engine/";

Read(Concatenation(HOLT_ENGINE_DIR, "subgroup_record.g"));
Read(Concatenation(HOLT_ENGINE_DIR, "heartbeat.g"));
Read(Concatenation(HOLT_ENGINE_DIR, "checkpoint.g"));
Read(Concatenation(HOLT_ENGINE_DIR, "dedup_invariants.g"));
Read(Concatenation(HOLT_ENGINE_DIR, "series_builder.g"));
Read(Concatenation(HOLT_ENGINE_DIR, "module_layer.g"));
Read(Concatenation(HOLT_ENGINE_DIR, "orbit_action.g"));
Read(Concatenation(HOLT_ENGINE_DIR, "presentation_engine.g"));
Read(Concatenation(HOLT_ENGINE_DIR, "cohomology_lifter.g"));
Read(Concatenation(HOLT_ENGINE_DIR, "tf_database.g"));
Read(Concatenation(HOLT_ENGINE_DIR, "symmetric_specialization.g"));
Read(Concatenation(HOLT_ENGINE_DIR, "engine.g"));
Read(Concatenation(HOLT_ENGINE_DIR, "verification.g"));

HOLT_ENGINE_LOADED := true;
Print("holt_engine loaded\n");
