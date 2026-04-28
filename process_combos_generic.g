###############################################################################
# Generic worker for re-running specific combos in any S_n partition.
#
# Globals to set before reading this file:
#   MY_WORKER_ID      = "A" / "B" / "C" / "D"
#   MY_LOG_FILE       = absolute path to log file
#   MY_PART           = partition list, e.g. [6,4,4,4]
#   MY_OUT_DIR        = absolute path to parallel_s18/[partition]/
#   MY_BLOCK_RANGES   = list of [lo,hi] block ranges, e.g. [[1,6],[7,10],...]
#   MY_N              = degree (e.g. 18)
#   MY_COMBOS         = list of combos. Each combo is a list of [degree, transId]
#                       pairs in BLOCK ORDER (matching MY_PART entry-by-entry).
#                       Example for [6,4,4,4] combo [4,2]_[4,3]_[4,3]_[6,14]:
#                         [[6,14], [4,2], [4,3], [4,3]]
#                       (note: ordered as the partition is — block 1 first.
#                        the filename convention sorts the [k,*] by k then id.)
#   MY_FORCE_OVERWRITE = true to overwrite existing disk files unconditionally.
#
###############################################################################

LogTo(MY_LOG_FILE);
Print("Worker ", MY_WORKER_ID, ": ", Length(MY_COMBOS),
      " combos for partition ", MY_PART, "\n");

# Disable interactive break loop so CALL_WITH_CATCH can intercept
# errors that would otherwise drop into a break prompt and halt the
# non-interactive worker (e.g. NoMethodFound from GroupByGenerators
# inside Action(H, blockPts) for awkward subgroup actions).
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_DISABLE_DEDUP := false;
# CRITICAL: M9 union-find dedup uses generator-only depth-1 BFS, missing
# conjugacies that require non-generator group elements. Force pairwise RA
# (correct but slower). Verified 20->8 vs M9 wrong 20->18 for [5,5]_[5,5]_[8,3].
HOLT_DISABLE_UF_DEDUP := true;
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

CURRENT_BLOCK_RANGES := MY_BLOCK_RANGES;

# Build filename in the standard convention used by run_s18.py:
# sort the [degree, id] tuples by (degree, id) ASCENDING and join with _.
_BuildFname := function(combo)
    local sorted_combo, parts;
    sorted_combo := SortedList(combo);
    parts := List(sorted_combo, p -> Concatenation("[", String(p[1]), ",",
                                                  String(p[2]), "]"));
    return Concatenation(JoinStringsWithSeparator(parts, "_"), ".g");
end;

_done := 0;
_total_classes := 0;
_total_t := 0;

for cmb in MY_COMBOS do
    fname := _BuildFname(cmb);
    fpath := Concatenation(MY_OUT_DIR, "/", fname);

    if (not MY_FORCE_OVERWRITE) and IsExistingFile(fpath) then
        _content := StringFile(fpath);
        if _content <> fail and PositionSublist(_content, "# deduped: ") <> fail then
            Print("  SKIP ", fname, " (exists)\n");
            continue;
        fi;
    fi;

    Print("\n>> ", fname, "\n");
    t_combo := Runtime();

    # Build factors in partition order (cmb is in partition order)
    currentFactors := List(cmb, p -> TransitiveGroup(p[1], p[2]));

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

    Npart := BuildPerComboNormalizer(MY_PART, currentFactors, MY_N);
    FPF_SUBDIRECT_CACHE := rec();
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

    raw := FindFPFClassesByLifting(P, shifted, offs, Npart);
    n_cand := Length(raw);
    Print("  raw: ", n_cand, " candidates, deduping...\n");

    fpf := HoltDedupUnderG(raw, Npart);
    elapsed := Runtime() - t_combo;
    _total_t := _total_t + elapsed;
    _done := _done + 1;
    _total_classes := _total_classes + Length(fpf);

    Print("  -> deduped: ", Length(fpf), " classes (", elapsed/1000.0, "s)\n");

    # Atomic write to .tmp then rename. cacheKey uses the same SORTED ordering
    # the filename is built from, matching run_s18.py's per-combo file format.
    tmp_path := Concatenation(fpath, ".tmp");
    cacheKey := SortedList(List(currentFactors,
                                f -> [NrMovedPoints(f),
                                      TransitiveIdentification(f)]));
    PrintTo(tmp_path, "# combo: ", cacheKey, "\n");
    AppendTo(tmp_path, "# candidates: ", n_cand, "\n");
    AppendTo(tmp_path, "# deduped: ", Length(fpf), "\n");
    AppendTo(tmp_path, "# elapsed_ms: ", elapsed, "\n");
    for h in fpf do
        gens := GeneratorsOfGroup(h);
        s := "";
        if Length(gens) > 0 then
            s := JoinStringsWithSeparator(List(gens, String), ",");
        fi;
        AppendTo(tmp_path, "[", s, "]\n");
    od;

    if IsExistingFile(fpath) then
        Exec(Concatenation("rm \"", fpath, "\""));
    fi;
    Exec(Concatenation("mv \"", tmp_path, "\" \"", fpath, "\""));

    Print("  WRITTEN ", fname, "\n");
od;

Print("\nWorker ", MY_WORKER_ID, " done: ", _done, " combos, ",
      _total_classes, " classes total, ", _total_t/1000.0, "s\n");
LogTo();
QUIT;
