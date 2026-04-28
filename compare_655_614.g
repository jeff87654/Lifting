# Compare current 7 subgroups in parallel_sn/16/[6,5,5]/[5,2]_[5,2]_[6,14].g
# to the 14 ref subgroups classified as [6,14]_[5,2]_[5,2].
# For each ref subgroup, check whether it's N-conjugate to any current subgroup,
# where N = per-combo normalizer for [6,5,5] x (6,14,5,2,5,2).

LogTo("/cygdrive/c/Users/jeffr/Downloads/Lifting/compare_655_614.log");
Read("/cygdrive/c/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Read the 7 current subgroups (from combo file)
CUR_FILE := "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_sn/16/[6,5,5]/[5,2]_[5,2]_[6,14].g";
cur_raw := StringFile(CUR_FILE);
cur_unwrapped := ReplacedString(cur_raw, "\\\n", "");
cur_groups := [];
for line in SplitString(cur_unwrapped, "\n") do
    if Length(line) > 0 and line[1] = '[' then
        # Line is "[perm1,perm2,...]" in GAP permutation notation
        gens := EvalString(line);
        if Length(gens) = 0 then
            Add(cur_groups, Group(()));
        else
            Add(cur_groups, Group(gens));
        fi;
    fi;
od;
Print("Current run: ", Length(cur_groups), " subgroups\n");

# Read the 14 ref subgroups (from gens_6_5_5.txt, only [6,14]_[5,2]_[5,2] ones)
REF_FILE := "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s16/gens/gens_6_5_5.txt";
ref_raw := StringFile(REF_FILE);
ref_unwrapped := ReplacedString(ref_raw, "\\\n", "");
ref_groups := [];
for line in SplitString(ref_unwrapped, "\n") do
    if Length(line) > 0 and line[1] = '[' then
        gens := EvalString(line);
        pgens := List(gens, g -> PermList(g));
        if Length(pgens) = 0 then
            Add(ref_groups, Group(()));
        else
            Add(ref_groups, Group(pgens));
        fi;
    fi;
od;

ClassifyCombo := function(H)
    local orbits, sorted_orbits, combo_parts, orb, d, proj_gens, g, img_perm,
          reorder, i, restr, id;
    orbits := OrbitsDomain(H, [1..16]);
    if SortedList(List(orbits, Length)) <> [5, 5, 6] then return fail; fi;
    sorted_orbits := ShallowCopy(orbits);
    Sort(sorted_orbits,
        function(a, b)
            if Length(a) <> Length(b) then return Length(a) > Length(b); fi;
            return Minimum(a) < Minimum(b);
        end);
    combo_parts := [];
    for orb in sorted_orbits do
        d := Length(orb);
        reorder := ShallowCopy(orb);
        Sort(reorder);
        proj_gens := [];
        for g in GeneratorsOfGroup(H) do
            img_perm := [];
            for i in [1..d] do
                Add(img_perm, Position(reorder, reorder[i]^g));
            od;
            Add(proj_gens, PermList(img_perm));
        od;
        restr := Group(proj_gens);
        id := TransitiveIdentification(restr);
        Add(combo_parts, [d, id]);
    od;
    return combo_parts;
end;

target_refs := Filtered(ref_groups,
    H -> ClassifyCombo(H) = [[6,14], [5,2], [5,2]]);
Print("Target ref subgroups: ", Length(target_refs), "\n");

# Build the per-combo normalizer N for partition [6,6,6] ... wait [6,5,5].
# The normalizer N to dedup under for this combo:
#   N_S16(T1 x T2 x T3) where T1=T(6,14), T2=T(5,2), T3=T(5,2).
# Since T2 = T3 = D_10, block-swap of positions [7..11] <-> [12..16] is in N.
# Plus N_S6(T1) x N_S5(T2) x N_S5(T3).

# Compute per-combo normalizer via existing builder
# Note: blocks are 1..6, 7..11, 12..16
T1 := TransitiveGroup(6, 14);
T2 := TransitiveGroup(5, 2);
# Shift to [7..11]
T2_shifted := Group(List(GeneratorsOfGroup(T2),
    g -> PermList(Concatenation([1..6], List([1..5], i -> i^g + 6)))));
T3_shifted := Group(List(GeneratorsOfGroup(T2),
    g -> PermList(Concatenation([1..11], List([1..5], i -> i^g + 11)))));
shifted_factors := [T1, T2_shifted, T3_shifted];

N := BuildPerComboNormalizer([6,5,5], shifted_factors, 16);
Print("Per-combo |N| = ", Size(N), "\n");

# For each ref subgroup, check: is it Q-conjugate (in N) to any current group?
hits := [];  # ref subgroup is N-conjugate to some current subgroup
misses := [];  # ref subgroup is NOT N-conjugate to any current subgroup
for i in [1..Length(target_refs)] do
    R := target_refs[i];
    found_match := false;
    for cur in cur_groups do
        if Size(cur) = Size(R) then
            if RepresentativeAction(N, R, cur) <> fail then
                found_match := true;
                break;
            fi;
        fi;
    od;
    if found_match then
        Add(hits, i);
    else
        Add(misses, i);
    fi;
od;

Print("\nRef subgroups found in current run: ", Length(hits), "/",
      Length(target_refs), "\n");
Print("MISSING ref indices: ", misses, "\n");
for i in misses do
    H := target_refs[i];
    Print("\n  Missing #", i, ": |H|=", Size(H),
          " struct=", StructureDescription(H), "\n");
    Print("    gens: ", GeneratorsOfGroup(H), "\n");
od;
LogTo();
QUIT;
