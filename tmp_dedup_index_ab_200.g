
LogTo("C:/Users/jeffr/Downloads/Lifting/tmp_dedup_index_ab_200.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
fileStr := StringFile("C:/Users/jeffr/Downloads/Lifting/parallel_s17_m6m7/[5,4,4,4]/[4,2]_[4,3]_[4,3]_[5,5].g");;
fileStr := ReplacedString(fileStr, "\\\n", "");;
fileStr := ReplacedString(fileStr, "\\\r\n", "");;
lines := SplitString(fileStr, "\n");;
PrintTo("C:/Users/jeffr/Downloads/Lifting/tmp_dedup_index_groups_200.g", "_DEDUP_GENS := [];;\n");;
_count := 0;;
for line in lines do
  while Length(line) > 0 and (line[Length(line)] = '\r' or line[Length(line)] = '\n' or line[Length(line)] = ' ') do
    line := line{[1..Length(line)-1]};
  od;
  if Length(line) > 2 and line[1] = '[' and _count < 200 then
    AppendTo("C:/Users/jeffr/Downloads/Lifting/tmp_dedup_index_groups_200.g", "Add(_DEDUP_GENS, ", line, ");\n");
    _count := _count + 1;
  fi;
od;
Read("C:/Users/jeffr/Downloads/Lifting/tmp_dedup_index_groups_200.g");
groups := List(_DEDUP_GENS, g -> Group(g));;
partition := [5,4,4,4];;
Nfull := BuildConjugacyTestGroup(17, partition);;
CURRENT_BLOCK_RANGES := [[1,5],[6,9],[10,13],[14,17]];;
HOLT_ENABLE_BLOCK_QUOTIENT_DEDUP := false;;
Print("loaded groups=", Length(groups), " |Nfull|=", Size(Nfull), "\n");
RunOne := function(label, enableIndex)
  local t0, reps, t;
  HOLT_ENABLE_UF_INDEX := enableIndex;
  t0 := Runtime();
  reps := HoltDedupUnderG(groups, Nfull);
  t := (Runtime() - t0) / 1000.0;
  Print(label, " reps=", Length(reps), " time=", t, "s\n");
end;
RunOne("index_off", false);
RunOne("index_on", true);
LogTo();
QUIT;
