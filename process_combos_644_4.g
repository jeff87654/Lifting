###############################################################################
# Process specific [6,4,4,4] combos given as MY_COMBOS list of [k4a,k4b,k4c,k6].
# Bypasses FindFPFClassesForPartition's iterator — each worker has its own list.
#
# Set MY_WORKER_ID, MY_LOG_FILE, MY_COMBOS before calling.
###############################################################################

LogTo(MY_LOG_FILE);
Print("Worker ", MY_WORKER_ID, ": ", Length(MY_COMBOS), " combos assigned\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_DISABLE_DEDUP := false;  # ENABLE HoltDedupUnderG since we're bypassing incrementalDedup
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

part := [6,4,4,4];
combo_dir := "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[6,4,4,4]";
CURRENT_BLOCK_RANGES := [[1,6],[7,10],[11,14],[15,18]];

_done := 0;
_total_classes := 0;
_total_t := 0;

for cmb in MY_COMBOS do
    k6 := cmb[1]; k4a := cmb[2]; k4b := cmb[3]; k4c := cmb[4];

    # Filename uses sorted [4,*] keys then [6,*] last.
    sorted_4s := SortedList([k4a, k4b, k4c]);
    fname := Concatenation("[4,", String(sorted_4s[1]), "]_[4,",
                          String(sorted_4s[2]), "]_[4,",
                          String(sorted_4s[3]), "]_[6,",
                          String(k6), "].g");
    fpath := Concatenation(combo_dir, "/", fname);

    if IsExistingFile(fpath) then
        # Validate: must contain a # deduped: line
        _content := StringFile(fpath);
        _has_deduped := false;
        if _content <> fail then
            for _line in SplitString(_content, "\n") do
                if Length(_line) >= 12 and _line{[1..11]} = "# deduped: " then
                    _has_deduped := true;
                    break;
                fi;
            od;
        fi;
        if _has_deduped then
            Print("  SKIP ", fname, " (exists)\n");
            continue;
        fi;
    fi;

    Print("\n>> ", fname, "\n");
    t_combo := Runtime();

    f6 := TransitiveGroup(6, k6);
    f4a := TransitiveGroup(4, sorted_4s[1]);
    f4b := TransitiveGroup(4, sorted_4s[2]);
    f4c := TransitiveGroup(4, sorted_4s[3]);
    currentFactors := [f6, f4a, f4b, f4c];

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
    FPF_SUBDIRECT_CACHE := rec();
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

    raw := FindFPFClassesByLifting(P, shifted, offs, Npart);
    n_cand := Length(raw);
    Print("  raw: ", n_cand, " candidates, deduping...\n");

    # Per-combo dedup under Npart-conjugacy via HoltDedupUnderG
    # (uses HoltCheapSubgroupInvariant bucketing + RA within bucket)
    fpf := HoltDedupUnderG(raw, Npart);
    elapsed := Runtime() - t_combo;
    _total_t := _total_t + elapsed;
    _done := _done + 1;
    _total_classes := _total_classes + Length(fpf);

    Print("  -> deduped: ", Length(fpf), " classes (", elapsed/1000.0, "s)\n");

    # Atomic write: temp file then rename. Avoid mid-write reads.
    tmp_path := Concatenation(fpath, ".tmp");
    cacheKey := List(currentFactors, f -> [NrMovedPoints(f),
                                           TransitiveIdentification(f)]);
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

    # Move tmp -> final
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
