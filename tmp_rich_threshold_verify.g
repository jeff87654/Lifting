
LogTo("C:/Users/jeffr/Downloads/Lifting/tmp_rich_threshold_verify.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
USE_HOLT_ENGINE := true;;
HOLT_ENGINE_MODE := "clean_first";;
CHECKPOINT_DIR := "";;
COMBO_OUTPUT_DIR := "";;
FPF_SUBDIRECT_CACHE := rec();;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
Print("threshold=", _HOLT_RICH_BUCKET_THRESHOLD, "\n");
t0 := Runtime();;
r := FindFPFClassesForPartition(12, [5,5,2]);;
t := (Runtime() - t0) / 1000.0;;
Print("s12_552 count=", Length(r), " time=", t, "s\n");
fileStr := StringFile("C:/Users/jeffr/Downloads/Lifting/parallel_s17_m6m7/[5,4,4,4]/[4,2]_[4,3]_[4,3]_[5,5].g");;
fileStr := ReplacedString(fileStr, "\\\n", "");;
fileStr := ReplacedString(fileStr, "\\\r\n", "");;
lines := SplitString(fileStr, "\n");;
PrintTo("C:/Users/jeffr/Downloads/Lifting/tmp_threshold_groups_200.g", "_THRESH_GENS := [];;\n");;
_count := 0;;
for line in lines do
  while Length(line) > 0 and (line[Length(line)] = '\r' or line[Length(line)] = '\n' or line[Length(line)] = ' ') do
    line := line{[1..Length(line)-1]};
  od;
  if Length(line) > 2 and line[1] = '[' and _count < 200 then
    AppendTo("C:/Users/jeffr/Downloads/Lifting/tmp_threshold_groups_200.g", "Add(_THRESH_GENS, ", line, ");\n");
    _count := _count + 1;
  fi;
od;
Read("C:/Users/jeffr/Downloads/Lifting/tmp_threshold_groups_200.g");
groups := List(_THRESH_GENS, g -> Group(g));;
Nfull := BuildConjugacyTestGroup(17, [5,4,4,4]);;
CURRENT_BLOCK_RANGES := [[1,5],[6,9],[10,13],[14,17]];;
HOLT_ENABLE_UF_INDEX := true;;
HOLT_ENABLE_BLOCK_QUOTIENT_DEDUP := false;;
t0 := Runtime();;
reps := HoltDedupUnderG(groups, Nfull);;
t := (Runtime() - t0) / 1000.0;;
Print("dedup200 reps=", Length(reps), " time=", t, "s\n");
LogTo();
QUIT;
