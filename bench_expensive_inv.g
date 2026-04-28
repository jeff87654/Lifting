LogTo("C:/Users/jeffr/Downloads/Lifting/bench_expensive_inv.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n=== Benchmark expensive invariant on [4,3]x[6,11]x[8,22] ===\n\n");

# Set block ranges for the partition [8,6,4] -> blocks at [1..8], [9..14], [15..18]
CURRENT_BLOCK_RANGES := [[1,8], [9,14], [15,18]];

filepath := "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[8,6,4]/[4,3]_[6,11]_[8,22].g";

# Read groups from combo file (with backslash continuation join)
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

# Pick 20 random ones
Print("Sampling 20 random groups...\n\n");
indices := [];
while Length(indices) < 20 do
    i := Random(1, Length(groups));
    if not i in indices then Add(indices, i); fi;
od;

# Benchmark expensive invariant on each
totalCheap := 0;
totalExp := 0;
totalCC := 0;
totalPairs := 0;

for i in indices do
    H := groups[i];
    sizeH := Size(H);

    t0 := Runtime();
    cheapInv := CheapSubgroupInvariantFull(H);
    tCheap := Runtime() - t0;
    totalCheap := totalCheap + tCheap;

    # Time ConjugacyClasses separately
    t0 := Runtime();
    if sizeH <= 10000 then
        cc := ConjugacyClasses(H);
        nCC := Length(cc);
    else
        nCC := -1;
    fi;
    tCC := Runtime() - t0;
    totalCC := totalCC + tCC;

    # Time 2-subset orbits
    t0 := Runtime();
    moved := MovedPoints(H);
    if Length(moved) <= 20 then
        pairs := Combinations(moved, 2);
        pairOrbs := Orbits(H, pairs, OnSets);
        nPairOrbs := Length(pairOrbs);
    else
        nPairOrbs := -1;
    fi;
    tPairs := Runtime() - t0;
    totalPairs := totalPairs + tPairs;

    # Total expensive invariant time
    t0 := Runtime();
    expInv := ExpensiveSubgroupInvariant(H);
    tExp := Runtime() - t0;
    totalExp := totalExp + tExp;

    Print("  Group #", i, ": |H|=", sizeH,
          ", cheap=", tCheap, "ms",
          ", CC=", tCC, "ms (", nCC, " classes)",
          ", pairs=", tPairs, "ms (", nPairOrbs, " orbits)",
          ", total exp=", tExp, "ms\n");
od;

Print("\n=== Totals ===\n");
Print("Cheap invariant total: ", totalCheap, "ms (avg ", totalCheap/20, "ms)\n");
Print("ConjugacyClasses total: ", totalCC, "ms (avg ", totalCC/20, "ms)\n");
Print("2-subset orbits total: ", totalPairs, "ms (avg ", totalPairs/20, "ms)\n");
Print("Expensive invariant total: ", totalExp, "ms (avg ", totalExp/20, "ms)\n");

LogTo();
QUIT;
