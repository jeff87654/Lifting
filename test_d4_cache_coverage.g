LogTo("C:/Users/jeffr/Downloads/Lifting/test_d4_cache_coverage.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n=== D_4^3 cache coverage test ===\n\n");

# Load D_4^3 cache
Read("C:/Users/jeffr/Downloads/Lifting/database/d4_cube_cache.g");
cache := List(D4_CUBE_CACHE, gens -> Group(gens));
Print("Loaded ", Length(cache), " D_4^3 subdirects from cache\n");

# Build N_[4,4,4] (on points {1..12})
shifted123 := [
    ShiftGroup(TransitiveGroup(4,3), 0),
    ShiftGroup(TransitiveGroup(4,3), 4),
    ShiftGroup(TransitiveGroup(4,3), 8)
];
N_d4 := BuildPerComboNormalizer([4,4,4], shifted123, 12);
Print("|N_[4,4,4]| = ", Size(N_d4), "\n\n");

# Load groups from the combo file
filepath := "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[4,4,4,3,3]/[3,2]_[3,2]_[4,3]_[4,3]_[4,3].g";
content := StringFile(filepath);
# Join backslash continuations
joined := "";
i := 1;
while i <= Length(content) do
    if i < Length(content) and content[i] = '\\' and content[i+1] = '\n' then
        i := i + 2;
    else
        Append(joined, [content[i]]);
        i := i + 1;
    fi;
od;
lines := SplitString(joined, "\n");
allGroups := [];
for line in lines do
    if Length(line) > 0 and line[1] = '[' then
        gens := EvalString(line);
        if Length(gens) > 0 then
            Add(allGroups, Group(gens));
        fi;
    fi;
od;
Print("Loaded ", Length(allGroups), " groups from combo file\n\n");

# For each group, compute its projection onto D_4^3 (points 1..12)
# and verify it's N_[4,4,4]-conjugate to some cache entry.
d4Pts := [1..12];
cacheUsed := rec();
notFound := 0;
t0 := Runtime();
Print("Testing coverage (this may take a while)...\n");
for i in [1..Length(allGroups)] do
    H := allGroups[i];
    gensProj := Filtered(List(GeneratorsOfGroup(H),
                              g -> RestrictedPerm(g, d4Pts)),
                         x -> x <> ());
    if Length(gensProj) = 0 then
        notFound := notFound + 1;
        continue;
    fi;
    Hproj := Group(gensProj);
    # Find which cache entry it matches
    found := false;
    for j in [1..Length(cache)] do
        if Size(Hproj) = Size(cache[j]) then
            if RepresentativeAction(N_d4, Hproj, cache[j]) <> fail then
                found := true;
                cacheUsed.(String(j)) := true;
                break;
            fi;
        fi;
    od;
    if not found then
        notFound := notFound + 1;
        if notFound <= 3 then
            Print("  NOT FOUND: group #", i, " with |Hproj|=", Size(Hproj), "\n");
        fi;
    fi;
    if i mod 500 = 0 then
        Print("  progress: ", i, "/", Length(allGroups), " (",
              Length(RecNames(cacheUsed)), " unique cache entries used, ",
              notFound, " not found, ", Int((Runtime()-t0)/1000), "s)\n");
    fi;
od;

Print("\n=== RESULTS ===\n");
Print("Total groups tested: ", Length(allGroups), "\n");
Print("Not found: ", notFound, "\n");
Print("Unique cache entries used: ", Length(RecNames(cacheUsed)), " / ", Length(cache), "\n");
Print("Total time: ", Int((Runtime()-t0)/1000), "s\n");

LogTo();
QUIT;
