LogTo("C:/Users/jeffr/Downloads/Lifting/bench_cc_real_groups.log");

Print("\n=== CC cost on real FPF subgroups of various sizes ===\n\n");

# Sample groups from multiple combo files covering different size ranges
files := [
    "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[8,6,4]/[4,3]_[6,11]_[8,22].g",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[8,4,4,2]/[2,1]_[4,3]_[4,3]_[8,35].g",
];

allGroups := [];
for filepath in files do
    content := StringFile(filepath);
    if content = fail then continue; fi;
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
    count := 0;
    for line in lines do
        if Length(line) > 0 and line[1] = '[' then
            gens := EvalString(line);
            if Length(gens) > 0 then
                Add(allGroups, Group(gens));
                count := count + 1;
                if count >= 200 then break; fi;  # cap per file
            fi;
        fi;
    od;
    Print("  ", filepath, ": loaded ", count, " groups\n");
od;
Print("\nTotal: ", Length(allGroups), " groups\n\n");

# Sort by size and sample across the range
Sort(allGroups, function(a, b) return Size(a) < Size(b); end);

# Take 30 groups spread across the size range
n := Length(allGroups);
indices := [];
for i in [1..30] do
    Add(indices, Int(1 + (i-1) * (n-1) / 29));
od;

Print("Size ranges: ");
Print("min=", Size(allGroups[1]), ", max=", Size(allGroups[n]), "\n\n");

Print("size      | CC time (ms) | #classes\n");
Print("----------+--------------+---------\n");
for i in indices do
    H := allGroups[i];
    sz := Size(H);
    t0 := Runtime();
    cc := ConjugacyClasses(H);
    tCC := Runtime() - t0;
    Print(String(sz, 10), "| ", String(tCC, 12), " | ", Length(cc), "\n");
od;

LogTo();
QUIT;
