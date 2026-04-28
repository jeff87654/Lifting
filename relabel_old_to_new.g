###############################################################################
# Relabel OLD combo 8 groups through the layout permutation g, then test if
# they match any of the 41 NEW groups under N_part_new conjugation.
#
# OLD layout: TG(6,15) on 1-6, TG(4,1) on 7-10, TG(4,2) on 11-14 + 15-18
# NEW layout: TG(4,1) on 1-4, TG(4,2) on 5-8 + 9-12, TG(6,15) on 13-18
#
# Relabel g: OLD i -> NEW g(i)
#   1->13, 2->14, 3->15, 4->16, 5->17, 6->18
#   7->1, 8->2, 9->3, 10->4
#   11->5, 12->6, 13->7, 14->8
#   15->9, 16->10, 17->11, 18->12
###############################################################################

LogTo("C:/Users/jeffr/Downloads/Lifting/relabel_old_to_new.log");
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

# Build the relabel permutation g: OLD point -> NEW point
g_image := [13,14,15,16,17,18, 1,2,3,4, 5,6,7,8, 9,10,11,12];
g_perm := PermList(g_image);
Print("Relabel g: OLD -> NEW = ", g_perm, "\n");
Print("Cycle structure: ", CycleStructurePerm(g_perm), "\n\n");

# N_part of NEW layout (which is what worker A used)
factors_new := [TransitiveGroup(4,1), TransitiveGroup(4,2),
                TransitiveGroup(4,2), TransitiveGroup(6,15)];
shifted_new := []; off := 0;
for f in factors_new do
    Add(shifted_new, ShiftGroup(f, off));
    off := off + NrMovedPoints(f);
od;
# Order of factors in BuildPerComboNormalizer matches CURRENT_BLOCK_RANGES used by lifting
# In NEW (worker A) the partition arg passed was [6,4,4,4] but factor list was sorted-asc
# Replicate that:
Npart_new := BuildPerComboNormalizer([6,4,4,4], factors_new, 18);
Print("|Npart_new| = ", Size(Npart_new), "\n\n");

# Conjugate each OLD group by g, then test against NEW
Print("=== Relabel OLD -> NEW and match ===\n");
matched := 0;
unmatched := [];
match_targets := [];
for i in [1..Length(old_groups)] do
    H_old := old_groups[i];
    H_relabeled := H_old^g_perm;
    found_idx := 0;
    for j in [1..Length(new_groups)] do
        if RepresentativeAction(Npart_new, H_relabeled, new_groups[j]) <> fail then
            found_idx := j; break;
        fi;
    od;
    if found_idx > 0 then
        matched := matched + 1;
        Add(match_targets, found_idx);
        Print("  OLD[", i, "] -> NEW[", found_idx, "] (matched after relabel+RA)\n");
    else
        Add(unmatched, i);
        Print("  OLD[", i, "] -> NO MATCH in 41 new groups\n");
    fi;
od;
Print("\nMatched: ", matched, "/", Length(old_groups), "\n");
Print("Match targets (NEW indices): ", match_targets, "\n");

# Identify the 29 "extra" NEW groups (not matched by any OLD)
extra := Difference([1..Length(new_groups)], match_targets);
Print("\n=== ", Length(extra), " EXTRA new groups (no OLD match) ===\n");
Print("Indices: ", extra, "\n");

LogTo();
QUIT;
