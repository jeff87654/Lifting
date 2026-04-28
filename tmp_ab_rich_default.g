
LogTo("C:/Users/jeffr/Downloads/Lifting/tmp_ab_rich_default.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
fileStr := StringFile("C:/Users/jeffr/Downloads/Lifting/parallel_s17_m6m7/[5,4,4,4]/[4,2]_[4,3]_[4,3]_[5,5].g");;
fileStr := ReplacedString(fileStr, "\\\n", "");;
fileStr := ReplacedString(fileStr, "\\\r\n", "");;
lines := SplitString(fileStr, "\n");;
PrintTo("C:/Users/jeffr/Downloads/Lifting/tmp_ab_groups_200.g", "_AB_GENS := [];;\n");;
_count := 0;;
for line in lines do
  while Length(line) > 0 and (line[Length(line)] = '\r' or line[Length(line)] = '\n' or line[Length(line)] = ' ') do
    line := line{[1..Length(line)-1]};
  od;
  if Length(line) > 2 and line[1] = '[' and _count < 200 then
    AppendTo("C:/Users/jeffr/Downloads/Lifting/tmp_ab_groups_200.g", "Add(_AB_GENS, ", line, ");\n");
    _count := _count + 1;
  fi;
od;
Read("C:/Users/jeffr/Downloads/Lifting/tmp_ab_groups_200.g");
groups := List(_AB_GENS, g -> Group(g));;
Nfull := BuildConjugacyTestGroup(17, [5,4,4,4]);;
CURRENT_BLOCK_RANGES := [[1,5],[6,9],[10,13],[14,17]];;
HOLT_ENABLE_UF_INDEX := true;;
HOLT_ENABLE_BLOCK_QUOTIENT_DEDUP := false;;
# default threshold
t0 := Runtime();;
reps := HoltDedupUnderG(groups, Nfull);;
t := (Runtime() - t0) / 1000.0;;
Print("RESULT label=default reps=", Length(reps), " time=", t, "s threshold=", _HOLT_RICH_BUCKET_THRESHOLD, "\n");
LogTo();
QUIT;
