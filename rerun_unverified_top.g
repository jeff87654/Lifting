###############################################################################
# Rerun the biggest combos in the 12 partitions that have no prebugfix backup.
# Compare to disk count and report deltas.
#
# COMBOS_TO_RUN := [ [partition, [factors]], ... ]
# Set MY_LOG_FILE.
###############################################################################

LogTo(MY_LOG_FILE);
Print("Rerun verifier: ", Length(COMBOS_TO_RUN), " combos\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_DISABLE_DEDUP := true;
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

results := [];
for entry in COMBOS_TO_RUN do
    part := entry[1];
    factor_specs := entry[2];  # list of [d, k] pairs
    disk_count := entry[3];

    Print("\n>> partition=", part, " factors=", factor_specs, "\n");

    # Build factors
    currentFactors := List(factor_specs, p -> TransitiveGroup(p[1], p[2]));

    # Build shifted product
    shifted := [];
    offs := [];
    off := 0;
    block_ranges := [];
    for f in currentFactors do
        Add(offs, off);
        Add(shifted, ShiftGroup(f, off));
        Add(block_ranges, [off+1, off + NrMovedPoints(f)]);
        off := off + NrMovedPoints(f);
    od;
    P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
    SetSize(P, Product(List(shifted, Size)));

    Npart := BuildPerComboNormalizer(part, currentFactors, 18);
    CURRENT_BLOCK_RANGES := block_ranges;

    FPF_SUBDIRECT_CACHE := rec();
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

    t0 := Runtime();
    fpf := FindFPFClassesByLifting(P, shifted, offs, Npart);
    elapsed := (Runtime() - t0)/1000.0;

    delta := Length(fpf) - disk_count;
    Add(results, [part, factor_specs, disk_count, Length(fpf), delta, elapsed]);

    Print("  disk=", disk_count, "  rerun=", Length(fpf),
          "  delta=", delta, "  (", elapsed, "s)\n");
od;

Print("\n=== Summary ===\n");
Print("partition  factors  disk  rerun  delta  time(s)\n");
for r in results do
    Print(r[1], "  ", r[2], "  ", r[3], "  ", r[4], "  ", r[5], "  ", r[6], "\n");
od;

LogTo();
QUIT;
