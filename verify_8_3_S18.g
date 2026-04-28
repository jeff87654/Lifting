###############################################################################
# Verify [5,5]_[5,5]_[8,3] dedup under S_18 (the OEIS-relevant ambient).
# Pick 10 random of the 20 fresh groups, run all 45 pairs under RA(S_18, ., .)
# Also run pairwise under Npart for direct comparison.
###############################################################################

LogTo("C:/Users/jeffr/Downloads/Lifting/verify_8_3_S18.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

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
Print("Loaded ", Length(groups), " groups\n");

S18 := SymmetricGroup(18);
factors := [TransitiveGroup(8,3), TransitiveGroup(5,5), TransitiveGroup(5,5)];
Npart := BuildPerComboNormalizer([8,5,5], factors, 18);
Print("|S_18| = ", Size(S18), "\n");
Print("|Npart| = ", Size(Npart), "\n\n");

n := Length(groups);
chosen_idxs := [];
while Length(chosen_idxs) < 10 do
    i := Random([1..n]);
    if not i in chosen_idxs then Add(chosen_idxs, i); fi;
od;
Print("Random indices: ", chosen_idxs, "\n\n");
picks := List(chosen_idxs, i -> groups[i]);

# Pairwise under Npart
n_match_N := 0;
t0 := Runtime();
Print("=== Pairwise under Npart ===\n");
for i in [1..Length(picks)] do
    for j in [i+1..Length(picks)] do
        if RepresentativeAction(Npart, picks[i], picks[j]) <> fail then
            n_match_N := n_match_N + 1;
            Print("  Npart match: groups[", chosen_idxs[i], "] ~ groups[",
                  chosen_idxs[j], "]\n");
        fi;
    od;
od;
Print("Npart matches: ", n_match_N, "/45 (", (Runtime()-t0)/1000.0, "s)\n\n");

# Pairwise under S_18
n_match_S := 0;
matched_S18 := [];
t1 := Runtime();
Print("=== Pairwise under S_18 ===\n");
for i in [1..Length(picks)] do
    for j in [i+1..Length(picks)] do
        if RepresentativeAction(S18, picks[i], picks[j]) <> fail then
            n_match_S := n_match_S + 1;
            Add(matched_S18, [chosen_idxs[i], chosen_idxs[j]]);
            Print("  S18 match: groups[", chosen_idxs[i], "] ~ groups[",
                  chosen_idxs[j], "]\n");
        fi;
    od;
od;
Print("S_18 matches: ", n_match_S, "/45 (", (Runtime()-t1)/1000.0, "s)\n\n");

Print("=== Verdict ===\n");
Print("Npart matches: ", n_match_N, "\n");
Print("S_18 matches:  ", n_match_S, "\n");
if n_match_S = n_match_N then
    Print("Same dedup at both levels. 20 = the OEIS-relevant count.\n");
else
    Print("S_18 finds MORE conjugacies than Npart. Npart over-counts.\n");
fi;

LogTo();
QUIT;
