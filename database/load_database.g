###############################################################################
#
# load_database.g - Master loader for precomputed database
#
# This file loads all precomputed database files to populate caches at startup.
# It provides significant speedups by avoiding redundant computation across runs.
#
# Database structure:
#   database/
#   ├── load_database.g           (this file)
#   ├── transitive_subgroups/
#   │   ├── degree_02.g through degree_12.g
#   ├── fpf_subdirects/
#   │   └── fpf_cache.g
#   └── ea_subdirects/
#       └── elementary_abelian.g
#
###############################################################################

DATABASE_PATH := "C:/Users/jeffr/Downloads/Lifting/database/";
DATABASE_LOADED := false;

# Track what was loaded
DATABASE_LOAD_STATS := rec(
    transitive_subgroups := 0,
    fpf_subdirects := 0,
    ea_subdirects := 0,
    tf_lattice := 0,
    load_time := 0
);

###############################################################################
# Data structures for precomputed data
###############################################################################

# TRANSITIVE_SUBGROUPS[n][k] = list of subgroup generating set lists
# Each generating set is a list of permutations (as lists)
if not IsBound(TRANSITIVE_SUBGROUPS) then
    TRANSITIVE_SUBGROUPS := rec();
fi;

# FPF_SUBDIRECT_DATA[cacheKey] = list of generating set lists
# This will be merged into FPF_SUBDIRECT_CACHE at load time
if not IsBound(FPF_SUBDIRECT_DATA) then
    FPF_SUBDIRECT_DATA := rec();
fi;

# EA_SUBDIRECTS_DATA["p_n"] = list of basis matrices
# This will be merged into ELEMENTARY_ABELIAN_SUBDIRECTS at load time
if not IsBound(EA_SUBDIRECTS_DATA) then
    EA_SUBDIRECTS_DATA := rec();
fi;

# TF_SUBGROUP_LATTICE_DATA.(iso_key) = rec(canonical_gens, subgroups)
# Each canonical_gens entry and each subgroup generator is a permutation list.
if not IsBound(TF_SUBGROUP_LATTICE_DATA) then
    TF_SUBGROUP_LATTICE_DATA := rec();
fi;

###############################################################################
# Helper: Convert stored permutation list back to permutation
###############################################################################

# ZeroPadString(n, width)
# Convert integer n to a string with zero-padding to given width
ZeroPadString := function(n, width)
    local s;
    s := String(n);
    while Length(s) < width do
        s := Concatenation("0", s);
    od;
    return s;
end;

# PermFromList(lst)
# Convert a list representation [1^g, 2^g, ...] back to a permutation
PermFromList := function(lst)
    if Length(lst) = 0 then
        return ();
    fi;
    return PermList(lst);
end;

# GroupFromGenLists(genLists)
# Convert list of generator lists back to a permutation group
GroupFromGenLists := function(genLists)
    local gens, lst;

    if Length(genLists) = 0 then
        return Group(());
    fi;

    gens := [];
    for lst in genLists do
        if Length(lst) > 0 then
            Add(gens, PermFromList(lst));
        fi;
    od;

    if Length(gens) = 0 then
        return Group(());
    fi;

    return Group(gens);
end;

###############################################################################
# Load Transitive Subgroups Database
###############################################################################

LoadTransitiveSubgroupsForDegree := function(n)
    local filename, key;

    filename := Concatenation(DATABASE_PATH, "transitive_subgroups/degree_",
                              ZeroPadString(n, 2), ".g");

    if IsReadableFile(filename) then
        Read(filename);
        key := String(n);
        if IsBound(TRANSITIVE_SUBGROUPS.(key)) then
            DATABASE_LOAD_STATS.transitive_subgroups :=
                DATABASE_LOAD_STATS.transitive_subgroups +
                Length(RecNames(TRANSITIVE_SUBGROUPS.(key)));
            return true;
        fi;
    fi;

    return false;
end;

LoadAllTransitiveSubgroups := function()
    local n, loaded;

    loaded := 0;
    for n in [2..14] do
        if LoadTransitiveSubgroupsForDegree(n) then
            loaded := loaded + 1;
        fi;
    od;

    if loaded > 0 then
        Print("  Loaded transitive subgroups for ", loaded, " degrees\n");
    fi;

    return loaded > 0;
end;

###############################################################################
# Load FPF Subdirect Cache
###############################################################################

LoadFPFSubdirectCache := function()
    local filename, key, count;

    filename := Concatenation(DATABASE_PATH, "fpf_subdirects/fpf_cache.g");

    if not IsReadableFile(filename) then
        return false;
    fi;

    Read(filename);

    # Ensure FPF_SUBDIRECT_CACHE exists (it may not be defined yet)
    if not IsBound(FPF_SUBDIRECT_CACHE) then
        FPF_SUBDIRECT_CACHE := rec();
    fi;

    # Merge FPF_SUBDIRECT_DATA into FPF_SUBDIRECT_CACHE
    if IsBound(FPF_SUBDIRECT_DATA) then
        count := 0;
        for key in RecNames(FPF_SUBDIRECT_DATA) do
            if not IsBound(FPF_SUBDIRECT_CACHE.(key)) then
                # Convert stored data back to groups
                FPF_SUBDIRECT_CACHE.(key) := List(
                    FPF_SUBDIRECT_DATA.(key),
                    genLists -> GroupFromGenLists(genLists)
                );
                count := count + 1;
            fi;
        od;
        DATABASE_LOAD_STATS.fpf_subdirects := count;
        if count > 0 then
            Print("  Loaded ", count, " FPF subdirect cache entries\n");
        fi;
    fi;

    return true;
end;

###############################################################################
# Load Elementary Abelian Subdirects
###############################################################################

LoadEASubdirects := function()
    local filename, key, count;

    filename := Concatenation(DATABASE_PATH, "ea_subdirects/elementary_abelian.g");

    if not IsReadableFile(filename) then
        return false;
    fi;

    Read(filename);

    # Ensure ELEMENTARY_ABELIAN_SUBDIRECTS exists
    if not IsBound(ELEMENTARY_ABELIAN_SUBDIRECTS) then
        ELEMENTARY_ABELIAN_SUBDIRECTS := rec();
    fi;

    # Merge EA_SUBDIRECTS_DATA into ELEMENTARY_ABELIAN_SUBDIRECTS
    if IsBound(EA_SUBDIRECTS_DATA) then
        count := 0;
        for key in RecNames(EA_SUBDIRECTS_DATA) do
            if not IsBound(ELEMENTARY_ABELIAN_SUBDIRECTS.(key)) then
                ELEMENTARY_ABELIAN_SUBDIRECTS.(key) := EA_SUBDIRECTS_DATA.(key);
                count := count + 1;
            fi;
        od;
        DATABASE_LOAD_STATS.ea_subdirects := count;

        # Mark as initialized so PrecomputeEASubdirects doesn't recompute
        EA_SUBDIRECTS_INITIALIZED := true;

        if count > 0 then
            Print("  Loaded ", count, " elementary abelian subdirect entries\n");
        fi;
    fi;

    return true;
end;

###############################################################################
# Load TF Subgroup Lattice Cache
###############################################################################

LoadTFLattice := function()
    local filename, key, count, entry, canonical_gens_perms, subgroup_perms,
          lst, G_canonical;

    filename := Concatenation(DATABASE_PATH, "tf_groups/tf_subgroup_lattice.g");

    if not IsReadableFile(filename) then
        return false;
    fi;

    Read(filename);

    if not IsBound(TF_SUBGROUP_LATTICE) then
        TF_SUBGROUP_LATTICE := rec();
    fi;

    if not IsBound(TF_SUBGROUP_LATTICE_DATA) then
        return false;
    fi;

    count := 0;
    for key in RecNames(TF_SUBGROUP_LATTICE_DATA) do
        if IsBound(TF_SUBGROUP_LATTICE.(key)) then
            continue;
        fi;

        entry := TF_SUBGROUP_LATTICE_DATA.(key);

        canonical_gens_perms := [];
        for lst in entry.canonical_gens do
            if Length(lst) > 0 then
                Add(canonical_gens_perms, PermFromList(lst));
            fi;
        od;

        if Length(canonical_gens_perms) = 0 then
            G_canonical := Group(());
        else
            G_canonical := Group(canonical_gens_perms);
        fi;

        subgroup_perms := List(entry.subgroups, genLists -> GroupFromGenLists(genLists));

        TF_SUBGROUP_LATTICE.(key) := rec(
            canonical_group := G_canonical,
            canonical_gens := canonical_gens_perms,
            subgroups := subgroup_perms
        );

        count := count + 1;
    od;

    DATABASE_LOAD_STATS.tf_lattice := count;
    if count > 0 then
        Print("  Loaded ", count, " TF subgroup lattice entries\n");
    fi;

    return count > 0;
end;

###############################################################################
# Save TF Subgroup Lattice Cache
###############################################################################

# Helper: serialize a perm group's generators as ListPerm-style lists.
# Returns [] for trivial group (no generators to emit). Caller must guard
# against non-perm groups before calling.
_SerializeTFGroupGens := function(G)
    local gens, moved_max, g;
    gens := [];
    if not IsPermGroup(G) then
        return gens;
    fi;
    moved_max := LargestMovedPoint(G);
    if moved_max = 0 then
        return gens;
    fi;
    for g in GeneratorsOfGroup(G) do
        if g = () then
            Add(gens, []);
        else
            Add(gens, ListPerm(g, moved_max));
        fi;
    od;
    return gens;
end;

# Persist TF_SUBGROUP_LATTICE to disk. With dirtyOnly=true, only the keys
# in TF_SUBGROUP_LATTICE_DIRTY_KEYS are merged with the on-disk file.
SaveTFLattice := function(dirtyOnly)
    local filename, key, entry, outData, canonicalGenLists, subgroupGenLists,
          dirty_keys, G, count_written;

    filename := Concatenation(DATABASE_PATH, "tf_groups/tf_subgroup_lattice.g");

    outData := rec();

    if dirtyOnly = true and IsReadableFile(filename) then
        Read(filename);
        if IsBound(TF_SUBGROUP_LATTICE_DATA) then
            for key in RecNames(TF_SUBGROUP_LATTICE_DATA) do
                outData.(key) := TF_SUBGROUP_LATTICE_DATA.(key);
            od;
        fi;
    fi;

    if dirtyOnly = true and IsBound(TF_SUBGROUP_LATTICE_DIRTY_KEYS) then
        dirty_keys := RecNames(TF_SUBGROUP_LATTICE_DIRTY_KEYS);
    else
        dirty_keys := RecNames(TF_SUBGROUP_LATTICE);
    fi;

    count_written := 0;
    for key in dirty_keys do
        if not IsBound(TF_SUBGROUP_LATTICE.(key)) then
            continue;
        fi;

        entry := TF_SUBGROUP_LATTICE.(key);

        canonicalGenLists := [];
        if IsBound(entry.canonical_group) and IsPermGroup(entry.canonical_group) then
            canonicalGenLists := _SerializeTFGroupGens(entry.canonical_group);
        elif IsBound(entry.canonical_gens) then
            for G in entry.canonical_gens do
                if G = () then
                    Add(canonicalGenLists, []);
                else
                    Add(canonicalGenLists, ListPerm(G, LargestMovedPoint(G)));
                fi;
            od;
        fi;

        subgroupGenLists := List(entry.subgroups, _SerializeTFGroupGens);

        outData.(key) := rec(
            canonical_gens := canonicalGenLists,
            subgroups := subgroupGenLists
        );
        count_written := count_written + 1;
    od;

    PrintTo(filename, "###############################################################################\n");
    AppendTo(filename, "# tf_subgroup_lattice.g - Precomputed subgroup lattices for TF-groups\n");
    AppendTo(filename, "# Auto-generated - do not edit manually\n");
    AppendTo(filename, "###############################################################################\n\n");
    AppendTo(filename, "TF_SUBGROUP_LATTICE_DATA := ", outData, ";\n");

    Print("Saved TF subgroup lattice to ", filename, "\n");
    Print("  ", Length(RecNames(outData)), " entries total (",
          count_written, " new/updated this session)\n");

    if IsBound(TF_SUBGROUP_LATTICE_DIRTY_KEYS) then
        TF_SUBGROUP_LATTICE_DIRTY_KEYS := rec();
    fi;
end;

###############################################################################
# Master Load Function
###############################################################################

LoadDatabaseIfExists := function()
    local startTime, anyLoaded;

    if DATABASE_LOADED then
        return true;
    fi;

    startTime := Runtime();
    anyLoaded := false;

    Print("\n");
    Print("Loading precomputed database...\n");
    Print("================================\n");

    # Load each component
    if LoadEASubdirects() then
        anyLoaded := true;
    fi;

    if LoadAllTransitiveSubgroups() then
        anyLoaded := true;
    fi;

    if LoadFPFSubdirectCache() then
        anyLoaded := true;
    fi;

    # Load D_4^3 cache for Goursat fast path
    if IsReadableFile(Concatenation(DATABASE_PATH, "d4_cube_cache.g")) then
        Read(Concatenation(DATABASE_PATH, "d4_cube_cache.g"));
        if IsBound(D4_CUBE_CACHE) then
            Print("  Loaded D_4^3 cache: ", Length(D4_CUBE_CACHE), " subdirects\n");
            anyLoaded := true;
        fi;
    fi;

    if LoadTFLattice() then
        anyLoaded := true;
    fi;

    DATABASE_LOAD_STATS.load_time := Runtime() - startTime;

    if anyLoaded then
        Print("Database loaded in ", DATABASE_LOAD_STATS.load_time / 1000.0, "s\n");
        Print("================================\n\n");
        DATABASE_LOADED := true;
    else
        Print("No database files found - will compute from scratch.\n");
        Print("================================\n\n");
    fi;

    return anyLoaded;
end;

###############################################################################
# Save Functions (for updating database after computation)
###############################################################################

# SaveFPFSubdirectCache()
# Save current FPF_SUBDIRECT_CACHE to disk
SaveFPFSubdirectCache := function()
    local filename, key, data, genSets, G, gens, g, moved;

    filename := Concatenation(DATABASE_PATH, "fpf_subdirects/fpf_cache.g");

    # Convert groups to storable format
    data := rec();
    for key in RecNames(FPF_SUBDIRECT_CACHE) do
        genSets := [];
        for G in FPF_SUBDIRECT_CACHE.(key) do
            gens := [];
            moved := MovedPoints(G);
            for g in GeneratorsOfGroup(G) do
                if g = () then
                    Add(gens, []);
                else
                    Add(gens, ListPerm(g, Maximum(moved)));
                fi;
            od;
            Add(genSets, gens);
        od;
        data.(key) := genSets;
    od;

    # Write to file
    PrintTo(filename, "###############################################################################\n");
    AppendTo(filename, "# fpf_cache.g - Precomputed FPF subdirect products\n");
    AppendTo(filename, "# Auto-generated - do not edit manually\n");
    AppendTo(filename, "###############################################################################\n\n");
    AppendTo(filename, "FPF_SUBDIRECT_DATA := ", data, ";\n");

    Print("Saved FPF subdirect cache to ", filename, "\n");
    Print("  ", Length(RecNames(data)), " entries\n");
end;

# SaveEASubdirects()
# Save elementary abelian subdirects to disk
SaveEASubdirects := function()
    local filename;

    filename := Concatenation(DATABASE_PATH, "ea_subdirects/elementary_abelian.g");

    # Write to file
    PrintTo(filename, "###############################################################################\n");
    AppendTo(filename, "# elementary_abelian.g - Precomputed elementary abelian subdirects\n");
    AppendTo(filename, "# Auto-generated - do not edit manually\n");
    AppendTo(filename, "###############################################################################\n\n");
    AppendTo(filename, "EA_SUBDIRECTS_DATA := ", ELEMENTARY_ABELIAN_SUBDIRECTS, ";\n");

    Print("Saved elementary abelian subdirects to ", filename, "\n");
    Print("  ", Length(RecNames(ELEMENTARY_ABELIAN_SUBDIRECTS)), " entries\n");
end;

###############################################################################
# Utility: Get Precomputed Transitive Subgroups
###############################################################################

# GetPrecomputedSubgroups(n, k)
# Get precomputed subgroup class reps for transitive group T(n,k)
# Returns list of subgroups, or fail if not precomputed
GetPrecomputedSubgroups := function(n, k)
    local degKey, idKey, genSetsList, result, genSets;

    degKey := String(n);
    idKey := String(k);

    if not IsBound(TRANSITIVE_SUBGROUPS.(degKey)) then
        return fail;
    fi;

    if not IsBound(TRANSITIVE_SUBGROUPS.(degKey).(idKey)) then
        return fail;
    fi;

    genSetsList := TRANSITIVE_SUBGROUPS.(degKey).(idKey);

    # Convert stored generator lists back to groups
    result := [];
    for genSets in genSetsList do
        Add(result, GroupFromGenLists(genSets));
    od;

    return result;
end;

###############################################################################
# GetSubgroupClassReps(G)
#
# Get conjugacy class representatives of subgroups of G.
# Uses precomputed data for transitive groups when available.
# Falls back to GAP's ConjugacyClassesSubgroups otherwise.
###############################################################################

GetSubgroupClassReps := function(G)
    local n, k, precomputed, shifted, moved, offset, result, H;

    # Check if G is a transitive group (acts transitively on its moved points)
    moved := MovedPoints(G);
    if Length(moved) = 0 then
        # Trivial group
        return [G];
    fi;

    n := Maximum(moved);

    # Check if moved points are exactly [1..n] (standard transitive action)
    if moved = [1..n] and IsTransitive(G, moved) then
        # Try to identify as a transitive group
        k := TransitiveIdentification(G);
        if k <> fail then
            precomputed := GetPrecomputedSubgroups(n, k);
            if precomputed <> fail then
                return precomputed;
            fi;
        fi;
    fi;

    # Check if it's a shifted transitive group (e.g., acts on [5..8])
    if IsTransitive(G, moved) then
        offset := Minimum(moved) - 1;
        n := Length(moved);

        # Shift G back to [1..n] to identify
        if offset > 0 then
            shifted := Group(List(GeneratorsOfGroup(G),
                g -> PermList(List([1..n], i -> (i + offset)^g - offset))));
            k := TransitiveIdentification(shifted);
            if k <> fail then
                precomputed := GetPrecomputedSubgroups(n, k);
                if precomputed <> fail then
                    # Shift precomputed subgroups back to original domain
                    result := [];
                    for H in precomputed do
                        if Size(H) = 1 then
                            Add(result, Group(()));
                        else
                            Add(result, Group(List(GeneratorsOfGroup(H),
                                g -> PermList(Concatenation(
                                    [1..offset],
                                    List([1..n], i -> i^g + offset))))));
                        fi;
                    od;
                    return result;
                fi;
            fi;
        fi;
    fi;

    # Fallback to GAP's built-in enumeration
    return List(ConjugacyClassesSubgroups(G), Representative);
end;

###############################################################################
# Database Statistics
###############################################################################

PrintDatabaseStats := function()
    Print("\n");
    Print("Database Statistics:\n");
    Print("====================\n");
    Print("Transitive subgroup entries: ", DATABASE_LOAD_STATS.transitive_subgroups, "\n");
    Print("FPF subdirect entries:       ", DATABASE_LOAD_STATS.fpf_subdirects, "\n");
    Print("EA subdirect entries:        ", DATABASE_LOAD_STATS.ea_subdirects, "\n");
    Print("TF lattice entries:          ", DATABASE_LOAD_STATS.tf_lattice, "\n");
    Print("Load time:                   ", DATABASE_LOAD_STATS.load_time / 1000.0, "s\n");
    Print("\n");
end;

###############################################################################

Print("Database loader ready.\n");
Print("Call LoadDatabaseIfExists() to load precomputed data.\n\n");
