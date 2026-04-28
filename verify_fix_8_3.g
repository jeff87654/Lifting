LogTo("C:/Users/jeffr/Downloads/Lifting/verify_fix_8_3.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

LoadGroups := function(fpath)
    local fs, text, groups, line;
    fs := StringFile(fpath);
    text := ReplacedString(fs, "\\\n", "");
    groups := [];
    for line in SplitString(text, "\n") do
        if Length(line) > 0 and line[1] = '[' then
            Add(groups, Group(EvalString(line)));
        fi;
    od;
    return groups;
end;

groups := LoadGroups(
  "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[8,5,5]/[5,5]_[5,5]_[8,3].g");
factors := [TransitiveGroup(8,3), TransitiveGroup(5,5), TransitiveGroup(5,5)];
Npart := BuildPerComboNormalizer([8,5,5], factors, 18);
CURRENT_BLOCK_RANGES := [[1,8],[9,13],[14,18]];

# Disable the buggy M9 union-find dedup. Force pairwise RA.
HOLT_DISABLE_UF_DEDUP := true;
HOLT_DISABLE_DEDUP := false;

result := HoltDedupUnderG(groups, Npart);
Print("Input: ", Length(groups), "  Output (M9 disabled): ", Length(result), "\n");

# Also try with canonical disabled too (force pure RA)
HOLT_DISABLE_CANON_DEDUP := true;
result2 := HoltDedupUnderG(groups, Npart);
Print("Output (M8+M9 disabled, pure RA): ", Length(result2), "\n");

LogTo();
QUIT;
