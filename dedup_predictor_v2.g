LogTo("C:/Users/jeffr/Downloads/Lifting/dedup_predictor_v2.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

src := "C:/Users/jeffr/Downloads/Lifting/predict_s18_tmp/[8,4,4]_one/[4,3]_[4,3]_[8,26]/[2,1]_[4,3]_[4,3]_[8,26].g";
fs := StringFile(src);
text := ReplacedString(fs, "\\\n", "");
groups := [];
for line in SplitString(text, "\n") do
    if Length(line) > 0 and line[1] = '[' then
        Add(groups, Group(EvalString(line)));
    fi;
od;
Print("Loaded ", Length(groups), " predictor groups\n");

# Quick check 1: are all sizes the same? Count by Size
sizes := rec();
for H in groups do
    s := String(Size(H));
    if not IsBound(sizes.(s)) then sizes.(s) := 0; fi;
    sizes.(s) := sizes.(s) + 1;
od;
Print("\nDistribution by Size:\n");
sizeKeys := SortedList(List(RecNames(sizes), x -> [Int(x), sizes.(x)]));
for sk in sizeKeys do
    Print("  size=", sk[1], ": ", sk[2], " groups\n");
od;

# Quick check 2: bucket by CheapSubgroupInvariant (cheap, partition-aware)
CURRENT_BLOCK_RANGES := [[1,8],[9,12],[13,16],[17,18]];
buckets := rec();
for H in groups do
    inv := CheapSubgroupInvariantFull(H);
    key := String(inv);
    if not IsBound(buckets.(key)) then buckets.(key) := 0; fi;
    buckets.(key) := buckets.(key) + 1;
od;
nb := Length(RecNames(buckets));
Print("\n# distinct CheapSubgroupInvariantFull buckets: ", nb, "\n");

# Show the largest buckets
bucket_sizes := List(RecNames(buckets), k -> [k, buckets.(k)]);
SortBy(bucket_sizes, x -> -x[2]);
Print("Top 10 largest buckets:\n");
for i in [1..Minimum(10, Length(bucket_sizes))] do
    Print("  bucket size = ", bucket_sizes[i][2], "\n");
od;

# If all buckets have size 1, predictor's 57369 groups are all distinct under cheap invariant.
# Buckets with size > 1 may or may not be Npart-conjugate (need RA to confirm).
n_singletons := Length(Filtered(bucket_sizes, x -> x[2] = 1));
n_multi := nb - n_singletons;
multi_total := Sum(Filtered(bucket_sizes, x -> x[2] > 1), x -> x[2]);
Print("\nSingleton buckets: ", n_singletons, "\n");
Print("Multi buckets: ", n_multi, ", containing ", multi_total, " groups\n");
Print("Lower bound on dedup count: ", n_singletons + n_multi, "\n");

LogTo();
QUIT;
