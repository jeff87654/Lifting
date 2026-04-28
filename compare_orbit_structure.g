###############################################################################
# Compare orbit structure of old vs new combo 8 groups.
# If they have the same multiset of (orbit length, TG-id-of-action) but on
# DIFFERENT point sets, then they're "the same family" up to relabeling and
# my hypothesis (different block layout) is confirmed.
###############################################################################

LogTo("C:/Users/jeffr/Downloads/Lifting/compare_orbit_structure.log");
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

# Compute the multiset signature: for each orbit of H, return (length, TI-of-action).
OrbitSignature := function(H)
    local orbs, sig, o, restricted, ti;
    orbs := Orbits(H, [1..18]);
    sig := [];
    for o in orbs do
        if Length(o) = 1 then
            Add(sig, [1, 1]);
        else
            restricted := Action(H, o);
            ti := TransitiveIdentification(restricted);
            Add(sig, [Length(o), ti]);
        fi;
    od;
    Sort(sig);
    return sig;
end;

new_groups := LoadGroups(
  "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[6,4,4,4]/[4,1]_[4,2]_[4,2]_[6,15].g");
old_groups := LoadGroups(
  "C:/Users/jeffr/Downloads/Lifting/parallel_s18_82_backup/[6,4,4,4]_[4,1]_[4,2]_[4,2]_[6,15].g");

Print("New: ", Length(new_groups), " groups\n");
Print("Old: ", Length(old_groups), " groups\n\n");

new_sigs := List(new_groups, OrbitSignature);
old_sigs := List(old_groups, OrbitSignature);

# Multiset comparison
new_sig_counts := rec();
for s in new_sigs do
    k := String(s);
    if not IsBound(new_sig_counts.(k)) then new_sig_counts.(k) := 0; fi;
    new_sig_counts.(k) := new_sig_counts.(k) + 1;
od;

old_sig_counts := rec();
for s in old_sigs do
    k := String(s);
    if not IsBound(old_sig_counts.(k)) then old_sig_counts.(k) := 0; fi;
    old_sig_counts.(k) := old_sig_counts.(k) + 1;
od;

Print("=== Distinct orbit signatures ===\n");
Print("New: ", Length(RecNames(new_sig_counts)), " distinct signatures\n");
Print("Old: ", Length(RecNames(old_sig_counts)), " distinct signatures\n\n");

# Show old signatures (since there are only 12)
Print("=== All Old (Apr 7) signatures ===\n");
for s in old_sigs do
    Print("  ", s, "\n");
od;

Print("\n=== New (fresh) signature multiset ===\n");
all_keys := Set(Concatenation(RecNames(new_sig_counts), RecNames(old_sig_counts)));
for k in all_keys do
    n_new := 0;
    n_old := 0;
    if IsBound(new_sig_counts.(k)) then n_new := new_sig_counts.(k); fi;
    if IsBound(old_sig_counts.(k)) then n_old := old_sig_counts.(k); fi;
    Print("  ", k, "  new=", n_new, " old=", n_old, "\n");
od;

LogTo();
QUIT;
