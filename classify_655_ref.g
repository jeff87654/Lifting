# Load the 1283 reference subgroups from parallel_s16/gens/gens_6_5_5.txt
# and classify each by factor combo (T_1, T_2, T_3). For each subgroup H <= S_16:
#   - Compute H's orbits on [1..16]; must be {6, 5, 5}
#   - Project H onto each orbit (as a transitive subgroup of S_d)
#   - Identify the transitive group TransitiveIdentification(proj_i) for each
#   - Sort the (d, k) tuples canonically (descending d, ascending k for ties)
#   - Emit a per-combo file at ref_655_by_combo/[combo].g listing the groups

LogTo("/cygdrive/c/Users/jeffr/Downloads/Lifting/classify_655_ref.log");
Read("/cygdrive/c/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

REF_FILE := "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s16/gens/gens_6_5_5.txt";
OUT_DIR := "/cygdrive/c/Users/jeffr/Downloads/Lifting/ref_655_by_combo";

# Parse the reference file. Each subgroup entry is a list-of-lists (each
# inner list being a permutation as a ListPerm array). GAP wraps long
# lines with '\<newline>' continuations, so we first join continuations
# then split on unescaped newlines.
Print("Reading ", REF_FILE, "\n");
_raw := StringFile(REF_FILE);
# Remove '\<newline>' continuations (literal backslash + newline)
_unwrapped := ReplacedString(_raw, "\\\n", "");
ref_lines := SplitString(_unwrapped, "\n");
ref_groups := [];
for line in ref_lines do
    if Length(line) > 0 and line[1] = '[' then
        # The line is "[ [p1..], [p2..], ... ]" where each inner list is
        # a perm encoded as image list.
        gens := EvalString(line);
        # Each gen is a list of integers: convert to permutation
        perm_gens := List(gens, g -> PermList(g));
        if Length(perm_gens) = 0 then
            Add(ref_groups, Group(()));
        else
            Add(ref_groups, Group(perm_gens));
        fi;
    fi;
od;
Print("Loaded ", Length(ref_groups), " reference subgroups\n");

# Classify each: compute orbits (of size 6, 5, 5 on [1..16]) then project.
ClassifyCombo := function(H)
    local orbits, orbit_sizes, sorted_orbits, combo_parts, orb,
          restr_gens, restr, id, d, proj_gens, g, img_perm, moved,
          shifted_moved, reorder, i;
    orbits := OrbitsDomain(H, [1..16]);
    orbit_sizes := SortedList(List(orbits, Length));
    if orbit_sizes <> [5, 5, 6] then
        return fail;  # unexpected orbit structure
    fi;
    # Sort orbits: (6-orbit first, then two 5-orbits by min-point ascending)
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
        # Build the restriction of H to this orbit, as a subgroup of S_d
        # acting on [1..d]. We project each generator onto orb and relabel.
        reorder := ShallowCopy(orb);
        # Map orb -> [1..d] by sorted order
        Sort(reorder);
        proj_gens := [];
        for g in GeneratorsOfGroup(H) do
            # Compute the permutation of [1..d] induced by g on orb.
            img_perm := [];
            for i in [1..d] do
                Add(img_perm, Position(reorder, reorder[i]^g));
            od;
            Add(proj_gens, PermList(img_perm));
        od;
        restr := Group(proj_gens);
        if not IsTransitive(restr, [1..d]) then
            return fail;  # projection must be transitive on its block
        fi;
        id := TransitiveIdentification(restr);
        Add(combo_parts, [d, id]);
    od;
    return combo_parts;
end;

# Emit per-combo breakdown
Exec(Concatenation("mkdir -p ", OUT_DIR));
combo_counts := rec();
unclassified := 0;

for i in [1..Length(ref_groups)] do
    H := ref_groups[i];
    combo := ClassifyCombo(H);
    if combo = fail then
        unclassified := unclassified + 1;
        Print("  UNCLASSIFIED #", i, "\n");
        continue;
    fi;
    # Build combo key like "[4,3]_[5,3]_[6,11]"
    combo_str := JoinStringsWithSeparator(
        List(combo, p -> Concatenation("[", String(p[1]), ",",
                                          String(p[2]), "]")),
        "_");
    if not IsBound(combo_counts.(combo_str)) then
        combo_counts.(combo_str) := 0;
    fi;
    combo_counts.(combo_str) := combo_counts.(combo_str) + 1;
od;

Print("\nClassified ", Length(ref_groups) - unclassified,
      " / ", Length(ref_groups), " groups\n");
Print("Unclassified: ", unclassified, "\n");
Print("\nPer-combo counts:\n");
combo_keys := ShallowCopy(RecNames(combo_counts));
Sort(combo_keys);
for key in combo_keys do
    Print("  ", key, " = ", combo_counts.(key), "\n");
od;
Print("Total across combos: ",
      Sum(List(combo_keys, k -> combo_counts.(k))), "\n");

# Save the counts to a file
outfile := Concatenation(OUT_DIR, "/ref_counts.txt");
PrintTo(outfile, "# Per-combo counts from parallel_s16/gens/gens_6_5_5.txt\n");
for key in combo_keys do
    AppendTo(outfile, key, " ", combo_counts.(key), "\n");
od;
Print("\nSaved to ", outfile, "\n");
LogTo();
QUIT;
