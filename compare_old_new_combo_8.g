###############################################################################
# Compare combo 8 ([4,1]_[4,2]_[4,2]_[6,15]) old (Apr 7, 12 groups) vs
# new (fresh, 41 groups). For each old group, check if it is Npart-conjugate
# to any new group. Quantifies overlap.
###############################################################################

LogTo("C:/Users/jeffr/Downloads/Lifting/compare_old_new_combo_8.log");
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

new_groups := LoadGroups(
  "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[6,4,4,4]/[4,1]_[4,2]_[4,2]_[6,15].g");
old_groups := LoadGroups(
  "C:/Users/jeffr/Downloads/Lifting/parallel_s18_82_backup/[6,4,4,4]_[4,1]_[4,2]_[4,2]_[6,15].g");

Print("New (fresh): ", Length(new_groups), " groups\n");
Print("Old (Apr 7): ", Length(old_groups), " groups\n");

factors := [TransitiveGroup(6,15), TransitiveGroup(4,1),
            TransitiveGroup(4,2), TransitiveGroup(4,2)];
Npart := BuildPerComboNormalizer([6,4,4,4], factors, 18);
Print("|Npart| = ", Size(Npart), "\n\n");

# For each old group, find which (if any) new group it matches under Npart.
matched := [];
unmatched_old := [];
for i in [1..Length(old_groups)] do
    H_old := old_groups[i];
    found := false;
    for j in [1..Length(new_groups)] do
        if RepresentativeAction(Npart, H_old, new_groups[j]) <> fail then
            Add(matched, [i, j]);
            Print("  old[", i, "] ~ new[", j, "]\n");
            found := true;
            break;
        fi;
    od;
    if not found then
        Add(unmatched_old, i);
        Print("  old[", i, "] -> NO MATCH in new\n");
    fi;
od;

Print("\n=== Summary ===\n");
Print("Old groups matched in new: ", Length(matched), "/", Length(old_groups), "\n");
Print("Old groups missing from new: ", Length(unmatched_old), "\n");
Print("New groups not in old: ",
      Length(new_groups) - Length(matched), "\n");

if Length(matched) = Length(old_groups) then
    Print("All Apr-7 groups appear in fresh. Fresh ⊇ old.\n");
    Print("Fresh found ", Length(new_groups) - Length(matched),
          " ADDITIONAL classes that Apr-7 missed.\n");
else
    Print("WARNING: ", Length(unmatched_old),
          " Apr-7 groups have no match in fresh. ",
          "Either lift code lost some, or old groups were spurious.\n");
fi;

LogTo();
QUIT;
