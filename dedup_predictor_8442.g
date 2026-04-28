LogTo("C:/Users/jeffr/Downloads/Lifting/dedup_predictor_8442.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_DISABLE_DEDUP := false;  # ENABLE rich-bucket dedup
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Load predictor's groups from file
src := "C:/Users/jeffr/Downloads/Lifting/predict_s18_tmp/[8,4,4]_one/[4,3]_[4,3]_[8,26]/[2,1]_[4,3]_[4,3]_[8,26].g";
fs := StringFile(src);
text := ReplacedString(fs, "\\\n", "");
groups := [];
for line in SplitString(text, "\n") do
    if Length(line) > 0 and line[1] = '[' then
        Add(groups, Group(EvalString(line)));
    fi;
od;
Print("Loaded ", Length(groups), " predictor candidate groups\n");

# Build the right partition normalizer for [8,4,4,2]/[T(2,1),T(4,3)^2,T(8,26)]
part := [8,4,4,2];
factors := [TransitiveGroup(8,26), TransitiveGroup(4,3),
            TransitiveGroup(4,3), TransitiveGroup(2,1)];
shifted := []; offs := []; off := 0;
for f in factors do
    Add(offs, off); Add(shifted, ShiftGroup(f, off));
    off := off + NrMovedPoints(f);
od;
P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
SetSize(P, Product(List(shifted, Size)));
Npart := BuildPerComboNormalizer(part, factors, 18);
CURRENT_BLOCK_RANGES := [[1,8],[9,12],[13,16],[17,18]];
Print("|P|=", Size(P), " |Npart|=", Size(Npart), "\n");

# Dedup via HoltDedupUnderG (invariant-bucket + RA)
Print("Calling HoltDedupUnderG...\n");
t0 := Runtime();
deduped := HoltDedupUnderG(groups, Npart);
elapsed := (Runtime() - t0)/1000.0;
Print("=> ", Length(deduped), " unique reps in ", elapsed, "s\n");
Print("Predictor input: 57369\n");
Print("Delta after dedup: ", Length(deduped) - 57369, "\n");

LogTo();
QUIT;
