LogTo("C:/Users/jeffr/Downloads/Lifting/bucket_d4_target.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

Print("\n=== Bucket analysis: target file for D_4^3 x S_3^2 combo ===\n\n");

CURRENT_BLOCK_RANGES := [[1,4],[5,8],[9,12],[13,15],[16,18]];

# Load target groups
filepath := "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[4,4,4,3,3]/[3,2]_[3,2]_[4,3]_[4,3]_[4,3].g";
content := StringFile(filepath);
joined := "";
i := 1;
while i <= Length(content) do
    if i < Length(content) and content[i] = '\\' and content[i+1] = '\n' then
        i := i + 2;
    else Append(joined, [content[i]]); i := i + 1;
    fi;
od;
lines := SplitString(joined, "\n");
groups := [];
for line in lines do
    if Length(line) > 0 and line[1] = '[' then
        gens := EvalString(line);
        if Length(gens) > 0 then Add(groups, Group(gens)); fi;
    fi;
od;
Print("Loaded ", Length(groups), " groups\n\n");

ReportStats := function(label, sigs)
    local keys, counts, big, top5;
    keys := RecNames(sigs);
    counts := List(keys, k -> sigs.(k));
    Sort(counts);
    Print(label, ":\n");
    Print("  distinct buckets: ", Length(keys), "\n");
    Print("  max: ", Maximum(counts), "\n");
    Print("  avg: ", Float(Sum(counts))/Float(Length(counts)), "\n");
    Print("  singletons (size 1): ", Length(Filtered(counts, c -> c = 1)), "\n");
    Print("  buckets >= 10: ", Length(Filtered(counts, c -> c >= 10)), "\n");
    Print("  buckets >= 100: ", Length(Filtered(counts, c -> c >= 100)), "\n");
    Print("  buckets >= 1000: ", Length(Filtered(counts, c -> c >= 1000)), "\n");
    Print("  top 5 sizes: ", counts{[Maximum(1, Length(counts)-4)..Length(counts)]}, "\n");
end;

# Simple invariant (size + orbit structure on blocks)
SimpleSig := function(H)
    local orbs;
    orbs := List([[1..4],[5..8],[9..12],[13..15],[16..18]], b -> Orbits(H, b));
    return [Size(H), SortedList(List(orbs{[1,2,3]}, o -> SortedList(List(o, Length)))),
            SortedList(List(orbs{[4,5]}, o -> SortedList(List(o, Length))))];
end;

# 3-tier stats
Print("Computing signatures for each tier...\n");
simpleSigs := rec();
cheapSigs := rec();
richSigs := rec();

t0 := Runtime();
for i in [1..Length(groups)] do
    H := groups[i];
    sk := String(SimpleSig(H));
    if IsBound(simpleSigs.(sk)) then simpleSigs.(sk) := simpleSigs.(sk)+1;
    else simpleSigs.(sk) := 1; fi;
    ck := InvariantKey(CheapSubgroupInvariantFull(H));
    if IsBound(cheapSigs.(ck)) then cheapSigs.(ck) := cheapSigs.(ck)+1;
    else cheapSigs.(ck) := 1; fi;
    rk := InvariantKey(ComputeSubgroupInvariant(H));
    if IsBound(richSigs.(rk)) then richSigs.(rk) := richSigs.(rk)+1;
    else richSigs.(rk) := 1; fi;
    if i mod 2000 = 0 then
        Print("  ", i, "/", Length(groups), " (", Int((Runtime()-t0)/1000), "s)\n");
    fi;
od;

Print("\n");
ReportStats("SIMPLE (size + orbit sigs)", simpleSigs);
Print("\n");
ReportStats("CHEAP (cheap invariant full)", cheapSigs);
Print("\n");
ReportStats("RICH (cheap + CC histogram + 2-subset)", richSigs);

LogTo();
QUIT;
