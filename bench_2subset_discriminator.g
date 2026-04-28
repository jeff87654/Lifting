LogTo("C:/Users/jeffr/Downloads/Lifting/bench_2subset_discriminator.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n=== 2-subset orbit discriminator test ===\n\n");

CURRENT_BLOCK_RANGES := [[1,8], [9,14], [15,18]];
filepath := "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[8,6,4]/[4,3]_[6,11]_[8,22].g";

# Load groups
content := StringFile(filepath);
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
groups := [];
for line in lines do
    if Length(line) > 0 and line[1] = '[' then
        gens := EvalString(line);
        if Length(gens) > 0 then
            Add(groups, Group(gens));
        fi;
    fi;
od;
Print("Loaded ", Length(groups), " groups\n\n");

# Compute 2-subset orbit signature for each group
Compute2SubsetSig := function(H)
    local moved, pairs, orbs;
    moved := MovedPoints(H);
    pairs := Combinations(moved, 2);
    orbs := Orbits(H, pairs, OnSets);
    return SortedList(List(orbs, Length));
end;

Compute2SubsetSigDetailed := function(H)
    local moved, pairs, orbs, orb, pts;
    moved := MovedPoints(H);
    pairs := Combinations(moved, 2);
    orbs := Orbits(H, pairs, OnSets);
    # Include the orbit partition structure, not just lengths
    return SortedList(List(orbs, o -> SortedList(o)));
end;

# Compute for all groups and bucket by signature
t0 := Runtime();
pairSigs := rec();
cheapSigs := rec();
combinedSigs := rec();
for i in [1..Length(groups)] do
    H := groups[i];
    # Just 2-subset orbit lengths
    sigPair := String(Compute2SubsetSig(H));
    if not IsBound(pairSigs.(sigPair)) then
        pairSigs.(sigPair) := 0;
    fi;
    pairSigs.(sigPair) := pairSigs.(sigPair) + 1;

    # Just cheap invariant
    sigCheap := String(CheapSubgroupInvariantFull(H));
    if not IsBound(cheapSigs.(sigCheap)) then
        cheapSigs.(sigCheap) := 0;
    fi;
    cheapSigs.(sigCheap) := cheapSigs.(sigCheap) + 1;

    # Cheap + 2-subset orbit lengths (combined)
    sigCombined := Concatenation(sigCheap, "|", sigPair);
    if not IsBound(combinedSigs.(sigCombined)) then
        combinedSigs.(sigCombined) := 0;
    fi;
    combinedSigs.(sigCombined) := combinedSigs.(sigCombined) + 1;
od;
t1 := Runtime();
Print("Computation time: ", t1 - t0, "ms for ", Length(groups), " groups\n");
Print("(", Float(t1-t0)/Float(Length(groups)), "ms per group for all 3 invariants)\n\n");

# Report bucket stats for each
ReportStats := function(label, sigs)
    local keys, counts, k, maxB, avgB, sumB, distinct;
    keys := RecNames(sigs);
    counts := List(keys, k -> sigs.(k));
    Sort(counts);
    distinct := Length(keys);
    sumB := Sum(counts);
    maxB := Maximum(counts);
    avgB := Float(sumB) / Float(distinct);
    Print(label, ":\n");
    Print("  Distinct buckets: ", distinct, "\n");
    Print("  Max bucket size: ", maxB, "\n");
    Print("  Avg bucket size: ", avgB, "\n");
    Print("  Top 5 bucket sizes: ",
          counts{[Maximum(1, Length(counts)-4)..Length(counts)]}, "\n");
    Print("  Buckets with 1 group: ", Length(Filtered(counts, c -> c = 1)), "\n");
    Print("  Buckets with >= 100: ", Length(Filtered(counts, c -> c >= 100)), "\n");
end;

ReportStats("2-subset orbit lengths alone", pairSigs);
Print("\n");
ReportStats("Cheap invariant alone", cheapSigs);
Print("\n");
ReportStats("Cheap + 2-subset combined", combinedSigs);

LogTo();
QUIT;
