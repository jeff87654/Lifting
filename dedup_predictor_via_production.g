LogTo("C:/Users/jeffr/Downloads/Lifting/dedup_predictor_via_production.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load predictor's groups
src := "C:/Users/jeffr/Downloads/Lifting/predict_s18_tmp/[8,4,4]_one/[4,3]_[4,3]_[8,26]/[2,1]_[4,3]_[4,3]_[8,26].g";
fs := StringFile(src);
text := ReplacedString(fs, "\\\n", "");
groups := [];
for line in SplitString(text, "\n") do
    if Length(line) > 0 and line[1] = '[' then
        Add(groups, Group(EvalString(line)));
    fi;
od;
Print("Loaded ", Length(groups), " predictor groups\n");

# Build the per-combo partition normalizer (same as production)
factors := [TransitiveGroup(8,26), TransitiveGroup(4,3),
            TransitiveGroup(4,3), TransitiveGroup(2,1)];
shifted := []; offs := []; off := 0;
for f in factors do
    Add(offs, off); Add(shifted, ShiftGroup(f, off));
    off := off + NrMovedPoints(f);
od;
P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
SetSize(P, Product(List(shifted, Size)));
currentN := BuildPerComboNormalizer([8,4,4,2], factors, 18);
CURRENT_BLOCK_RANGES := [[1,8],[9,12],[13,16],[17,18]];
Print("|P|=", Size(P), " |currentN|=", Size(currentN), "\n");

# Set up production-style state
byInvariant := rec();
all_fpf := [];
invFunc := CheapSubgroupInvariant;

# Some globals AddIfNotConjugateWithKey expects
_DEDUP_RA_COUNT := 0;
RICH_DEDUP_THRESHOLD := 50;
_richInvActive := false;

t0 := Runtime();
last_log := Runtime();
n_added := 0;
n_dup := 0;
for i in [1..Length(groups)] do
    H := groups[i];

    # Upgrade to rich invariants when bucket gets big (mimic production)
    if not _richInvActive and Length(all_fpf) > RICH_DEDUP_THRESHOLD then
        # Don't upgrade by default - keep CheapSubgroupInvariant for speed
    fi;

    res := AddIfNotConjugateWithKey(currentN, H, all_fpf, byInvariant, invFunc);
    if res.added then n_added := n_added + 1;
    else n_dup := n_dup + 1; fi;

    if Runtime() - last_log > 30000 then
        Print("  i=", i, "/", Length(groups),
              " added=", n_added, " dup=", n_dup,
              " RA=", _DEDUP_RA_COUNT,
              " elapsed=", Int((Runtime()-t0)/1000), "s\n");
        last_log := Runtime();
    fi;
od;
Print("\n=== Final ===\n");
Print("Predictor input: ", Length(groups), "\n");
Print("Added (distinct): ", n_added, "\n");
Print("Dropped (Npart-conjugate to existing): ", n_dup, "\n");
Print("Total RA calls: ", _DEDUP_RA_COUNT, "\n");
Print("Elapsed: ", (Runtime()-t0)/1000.0, "s\n");
Print("\nIf n_added=57369 -> predictor produced all distinct classes\n");
Print("If n_added<57369 -> predictor has duplicates (and bigger groups may have caused under-estimation in formula too)\n");

LogTo();
QUIT;
