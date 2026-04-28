LogTo("C:/Users/jeffr/Downloads/Lifting/rerun_55_55_8x.log");
Print("Rerunning all 50 [5,5]_[5,5]_[8,k] combos in [8,5,5]\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_DISABLE_DEDUP := true;
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Output to a fresh directory so we don't clobber the current run
out_dir := "C:/Users/jeffr/Downloads/Lifting/rerun_55_55_8x_out";
if not IsDirectoryPath(out_dir) then
    Exec("mkdir -p \"C:/Users/jeffr/Downloads/Lifting/rerun_55_55_8x_out\"");
fi;

# Build [8,5,5] partition shifted factors layout: block 1 = {1..8} for T(8,k),
# blocks 2,3 = {9..13},{14..18} for T(5,5)=S_5
part := [8,5,5];
factor_55 := TransitiveGroup(5,5);   # S_5
results := [];

t_total := Runtime();
for k in [1..NrTransitiveGroups(8)] do
    factor_8k := TransitiveGroup(8, k);

    # Skip non-FPF transitive groups (FindFPFClassesByLifting handles this)
    # but here we're given specific T(8,k), they're all FPF (transitive).

    currentFactors := [factor_8k, factor_55, factor_55];

    # Build shifted product
    shifted := [];
    offs := [];
    off := 0;
    for f in currentFactors do
        Add(offs, off);
        Add(shifted, ShiftGroup(f, off));
        off := off + NrMovedPoints(f);
    od;
    P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
    SetSize(P, Product(List(shifted, Size)));
    Npart := BuildPerComboNormalizer(part, currentFactors, 18);
    CURRENT_BLOCK_RANGES := [[1,8],[9,13],[14,18]];

    FPF_SUBDIRECT_CACHE := rec();
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

    t0 := Runtime();
    fpf := FindFPFClassesByLifting(P, shifted, offs, Npart);
    elapsed := (Runtime() - t0) / 1000.0;

    Add(results, [k, Length(fpf), elapsed]);
    Print("[8,", k, "] -> ", Length(fpf), " (", elapsed, "s)\n");
od;

Print("\n=== Summary ===\n");
Print("k  count  time(s)\n");
for r in results do
    Print(r[1], "  ", r[2], "  ", r[3], "\n");
od;
Print("Total time: ", (Runtime() - t_total)/1000.0, "s\n");

# Also write to a parseable file
out_file := Concatenation(out_dir, "/rerun_results.txt");
PrintTo(out_file, "k count time\n");
for r in results do
    AppendTo(out_file, r[1], " ", r[2], " ", r[3], "\n");
od;
Print("Results written to ", out_file, "\n");

LogTo();
QUIT;
