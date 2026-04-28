LogTo("C:/Users/jeffr/Downloads/Lifting/bench_order_disc.log");

Print("\n=== Order histogram discriminator test ===\n\n");

# Load all 9208 groups from [4,3]x[6,11]x[8,22]
filepath := "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[8,6,4]/[4,3]_[6,11]_[8,22].g";
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

# Compute order histogram for each group
ComputeOrderHist := function(H)
    local hist, g, o, i;
    hist := [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0];  # up to order 20
    for g in H do
        o := Order(g);
        if o <= 20 then
            hist[o] := hist[o] + 1;
        else
            hist[20] := hist[20] + 1;
        fi;
    od;
    return hist;
end;

t0 := Runtime();
histSigs := rec();
for i in [1..Length(groups)] do
    H := groups[i];
    sig := String(ComputeOrderHist(H));
    if not IsBound(histSigs.(sig)) then
        histSigs.(sig) := 0;
    fi;
    histSigs.(sig) := histSigs.(sig) + 1;
    if i mod 1000 = 0 then
        Print("  progress: ", i, "/", Length(groups), " (", Runtime()-t0, "ms)\n");
    fi;
od;
tTotal := Runtime() - t0;
Print("\nTotal time: ", tTotal, "ms (", Float(tTotal)/Float(Length(groups)), "ms/group)\n");

keys := RecNames(histSigs);
counts := List(keys, k -> histSigs.(k));
Sort(counts);
Print("\nDistinct order histograms: ", Length(keys), "\n");
Print("Max bucket size: ", Maximum(counts), "\n");
Print("Avg bucket size: ", Float(Sum(counts))/Float(Length(counts)), "\n");
Print("Buckets with 1 group: ", Length(Filtered(counts, c -> c = 1)), "\n");
Print("Top 5 bucket sizes: ",
      counts{[Maximum(1, Length(counts)-4)..Length(counts)]}, "\n");

LogTo();
QUIT;
