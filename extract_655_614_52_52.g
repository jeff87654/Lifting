# List the 14 ref subgroups classified as [6,14]_[5,2]_[5,2] and show their
# structure for inspection.

LogTo("/cygdrive/c/Users/jeffr/Downloads/Lifting/extract_655_614_52_52.log");

REF_FILE := "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s16/gens/gens_6_5_5.txt";

_raw := StringFile(REF_FILE);
_unwrapped := ReplacedString(_raw, "\\\n", "");
ref_lines := SplitString(_unwrapped, "\n");
ref_groups := [];
for line in ref_lines do
    if Length(line) > 0 and line[1] = '[' then
        gens := EvalString(line);
        perm_gens := List(gens, g -> PermList(g));
        if Length(perm_gens) = 0 then
            Add(ref_groups, Group(()));
        else
            Add(ref_groups, Group(perm_gens));
        fi;
    fi;
od;
Print("Loaded ", Length(ref_groups), " ref subgroups\n");

# Classify and collect only the [6,14]_[5,2]_[5,2] ones
TARGET_COMBO := "[6,14]_[5,2]_[5,2]";

ClassifyCombo := function(H)
    local orbits, orbit_sizes, sorted_orbits, combo_parts, orb,
          restr_gens, restr, id, d, proj_gens, g, img_perm, moved,
          shifted_moved, reorder, i;
    orbits := OrbitsDomain(H, [1..16]);
    orbit_sizes := SortedList(List(orbits, Length));
    if orbit_sizes <> [5, 5, 6] then
        return fail;
    fi;
    sorted_orbits := ShallowCopy(orbits);
    Sort(sorted_orbits,
        function(a, b)
            if Length(a) <> Length(b) then
                return Length(a) > Length(b);
            fi;
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
        if not IsTransitive(restr, [1..d]) then
            return fail;
        fi;
        id := TransitiveIdentification(restr);
        Add(combo_parts, [d, id]);
    od;
    return combo_parts;
end;

target_groups := [];
for H in ref_groups do
    combo := ClassifyCombo(H);
    if combo = fail then continue; fi;
    combo_str := JoinStringsWithSeparator(
        List(combo, p -> Concatenation("[", String(p[1]), ",",
                                          String(p[2]), "]")),
        "_");
    if combo_str = TARGET_COMBO then
        Add(target_groups, H);
    fi;
od;

Print("Target combo ", TARGET_COMBO, ": ", Length(target_groups),
      " subgroups\n\n");
for i in [1..Length(target_groups)] do
    H := target_groups[i];
    Print("---- #", i, " ----\n");
    Print("  |H| = ", Size(H), "\n");
    Print("  Gens: ", GeneratorsOfGroup(H), "\n");
    Print("  Structure: ", StructureDescription(H), "\n");
od;

LogTo();
QUIT;
