LogTo("C:/Users/jeffr/Downloads/Lifting/dedup_predictor_v3.log");

# Simple invariants only: Size + IdGroup
src := "C:/Users/jeffr/Downloads/Lifting/predict_s18_tmp/[8,4,4]_one/[4,3]_[4,3]_[8,26]/[2,1]_[4,3]_[4,3]_[8,26].g";
fs := StringFile(src);
text := ReplacedString(fs, "\\\n", "");
groups := [];
for line in SplitString(text, "\n") do
    if Length(line) > 0 and line[1] = '[' then
        Add(groups, Group(EvalString(line)));
    fi;
od;
Print("Loaded ", Length(groups), " groups\n");

# Bucket by (Size, IdGroup) - cheap and reliable
buckets := rec();
t0 := Runtime();
for i in [1..Length(groups)] do
    H := groups[i];
    s := Size(H);
    if s <= 256 then
        id := IdGroup(H);
        key := Concatenation(String(s), "_", String(id[2]));
    else
        # For larger groups, use abelian invariants + derived length as cheap canonical
        ai := AbelianInvariants(H/DerivedSubgroup(H));
        dl := DerivedLength(H);
        key := Concatenation(String(s), "_dl", String(dl), "_", String(ai));
    fi;
    if not IsBound(buckets.(key)) then buckets.(key) := 0; fi;
    buckets.(key) := buckets.(key) + 1;
    if i mod 5000 = 0 then
        Print("  i=", i, "/", Length(groups), " (", (Runtime()-t0)/1000.0, "s)\n");
    fi;
od;
Print("Bucketing done in ", (Runtime()-t0)/1000.0, "s\n");

# Bucket size histogram
counts := rec();
nb := 0;
for k in RecNames(buckets) do
    nb := nb + 1;
    sz := buckets.(k);
    sk := String(sz);
    if not IsBound(counts.(sk)) then counts.(sk) := 0; fi;
    counts.(sk) := counts.(sk) + 1;
od;
Print("\n# distinct (Size, IdGroup) buckets: ", nb, "\n");
Print("Bucket size histogram:\n");
sorted_counts := SortedList(List(RecNames(counts), x -> [Int(x), counts.(x)]));
for sc in sorted_counts do
    Print("  ", sc[2], " buckets of size ", sc[1], "\n");
od;

n_singles := 0;
multi_total := 0;
for k in RecNames(buckets) do
    if buckets.(k) = 1 then n_singles := n_singles + 1;
    else multi_total := multi_total + buckets.(k); fi;
od;
Print("\nSingleton buckets: ", n_singles, "\n");
Print("Total in multi-buckets: ", multi_total, "\n");
Print("Lower bound on dedup count: ", n_singles + (nb - n_singles), " (= total buckets, IF buckets are accurate canonical form)\n");
Print("Upper bound on dedup count: ", n_singles + multi_total, " (= 57369, IF all multi-bucket items are distinct under N)\n");

LogTo();
QUIT;
