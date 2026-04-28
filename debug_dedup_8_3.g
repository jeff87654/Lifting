###############################################################################
# Run HoltDedupUnderG on the 20 groups manually with FULL diagnostics.
# Expect: should reduce 20 to fewer (since at least 7~8~9 and 15~17 are conjugate).
###############################################################################

LogTo("C:/Users/jeffr/Downloads/Lifting/debug_dedup_8_3.log");
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

Print("Input: ", Length(groups), " groups, |Npart|=", Size(Npart), "\n");

# Run dedup
HOLT_DISABLE_DEDUP := false;
result := HoltDedupUnderG(groups, Npart);
Print("\nHoltDedupUnderG output: ", Length(result), " reps\n");

# Direct comparison: how many should there be (manual all-pairs RA)?
Print("\n=== Manual all-pairs RA test (slow but definitive) ===\n");
n := Length(groups);
parent := [1..n];
ufFind := function(x)
    while parent[x] <> x do parent[x] := parent[parent[x]]; x := parent[x]; od;
    return x;
end;

t0 := Runtime();
for i in [1..n] do
    for j in [i+1..n] do
        if ufFind(i) <> ufFind(j) then  # only test if not already united
            if RepresentativeAction(Npart, groups[i], groups[j]) <> fail then
                parent[ufFind(j)] := ufFind(i);
                Print("  ", i, " ~ ", j, "\n");
            fi;
        fi;
    od;
od;
roots := Set(List([1..n], i -> ufFind(i)));
Print("\nManual count: ", Length(roots), " classes from ", n, " inputs\n");
Print("Roots: ", roots, "\n");
Print("Time: ", (Runtime()-t0)/1000.0, "s\n");

LogTo();
QUIT;
