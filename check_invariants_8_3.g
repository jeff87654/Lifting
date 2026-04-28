###############################################################################
# Check why dedup missed conjugacies in [5,5]_[5,5]_[8,3].
# Specifically the matched pairs: 7~8~9 and 15~17.
# Compute CheapSubgroupInvariantFull for each and see if they collide.
###############################################################################

LogTo("C:/Users/jeffr/Downloads/Lifting/check_invariants_8_3.log");
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

# Set CURRENT_BLOCK_RANGES like the worker did
CURRENT_BLOCK_RANGES := [[1,8],[9,13],[14,18]];

Print("=== Cheap invariants for 20 groups ===\n");
invs := [];
for i in [1..Length(groups)] do
    inv := CheapSubgroupInvariantFull(groups[i]);
    Add(invs, inv);
    Print("  group ", i, ": |H|=", Size(groups[i]),
          " inv=", inv, "\n");
od;

# Bucket them
Print("\n=== Buckets (groups with same invariant key) ===\n");
buckets := rec();
for i in [1..Length(invs)] do
    k := String(invs[i]);
    if not IsBound(buckets.(k)) then buckets.(k) := []; fi;
    Add(buckets.(k), i);
od;
for k in RecNames(buckets) do
    if Length(buckets.(k)) > 1 then
        Print("  Multi-bucket: indices ", buckets.(k), "\n");
    else
        Print("  Singleton: index ", buckets.(k)[1], "\n");
    fi;
od;

# Specifically check the matched pairs
factors := [TransitiveGroup(8,3), TransitiveGroup(5,5), TransitiveGroup(5,5)];
Npart := BuildPerComboNormalizer([8,5,5], factors, 18);
Print("\n=== Verification: known conjugate pairs/triples ===\n");
Print("groups[7] ~ groups[8]: RA(Npart) = ",
      RepresentativeAction(Npart, groups[7], groups[8]) <> fail, "\n");
Print("Same invariant? ", invs[7] = invs[8], "\n");

Print("groups[15] ~ groups[17]: RA(Npart) = ",
      RepresentativeAction(Npart, groups[15], groups[17]) <> fail, "\n");
Print("Same invariant? ", invs[15] = invs[17], "\n");

LogTo();
QUIT;
