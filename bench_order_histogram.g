LogTo("C:/Users/jeffr/Downloads/Lifting/bench_order_histogram.log");

Print("\n=== Element order histogram benchmark ===\n\n");

# Load sample groups from combo file
filepath := "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[8,4,4,2]/[2,1]_[4,3]_[4,3]_[8,35].g";
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
allGroups := [];
for line in lines do
    if Length(line) > 0 and line[1] = '[' then
        gens := EvalString(line);
        if Length(gens) > 0 then
            Add(allGroups, Group(gens));
        fi;
    fi;
    if Length(allGroups) >= 500 then break; fi;
od;

# Sort and pick groups at each size level
Sort(allGroups, function(a, b) return Size(a) < Size(b); end);
Print("Loaded ", Length(allGroups), " groups, sizes from ",
      Size(allGroups[1]), " to ", Size(allGroups[Length(allGroups)]), "\n\n");

# Test 4 different approaches at each size level
# Pick 3 groups per size bucket
sizes := [];
for g in allGroups do
    if not Size(g) in sizes then Add(sizes, Size(g)); fi;
od;

Print("Unique sizes: ", sizes, "\n\n");
Print("method                  | time | discriminator\n");
Print("------------------------+------+---------------\n");

for sz in sizes do
    bucket := Filtered(allGroups, g -> Size(g) = sz);
    if Length(bucket) = 0 then continue; fi;
    H := bucket[1];

    # Rebuild to avoid cached attributes
    H2 := Group(GeneratorsOfGroup(H));

    # Method 1: Full ConjugacyClasses + order count via class reps
    H2 := Group(GeneratorsOfGroup(H));
    t0 := Runtime();
    cc := ConjugacyClasses(H2);
    orderHist := rec();
    for cl in cc do
        o := Order(Representative(cl));
        key := Concatenation("o", String(o));
        if not IsBound(orderHist.(key)) then
            orderHist.(key) := 0;
        fi;
        orderHist.(key) := orderHist.(key) + Size(cl);
    od;
    t1 := Runtime() - t0;
    nKeys1 := Length(RecNames(orderHist));

    # Method 2: Orders of class representatives (via CC, but just ordering)
    H2 := Group(GeneratorsOfGroup(H));
    t0 := Runtime();
    cc2 := ConjugacyClasses(H2);
    ocr := List(cc2, cl -> Order(Representative(cl)));
    t2 := Runtime() - t0;
    nKeys2 := Length(Set(ocr));

    # Method 3: Direct element iteration (element order histogram)
    H2 := Group(GeneratorsOfGroup(H));
    t0 := Runtime();
    orderHist3 := rec();
    for g in H2 do
        o := Order(g);
        key := Concatenation("o", String(o));
        if not IsBound(orderHist3.(key)) then
            orderHist3.(key) := 0;
        fi;
        orderHist3.(key) := orderHist3.(key) + 1;
    od;
    t3 := Runtime() - t0;
    nKeys3 := Length(RecNames(orderHist3));

    # Method 4: AsList + orders (batch)
    H2 := Group(GeneratorsOfGroup(H));
    t0 := Runtime();
    elts := AsList(H2);
    orderSet := Set(List(elts, Order));
    t4 := Runtime() - t0;

    Print("|H|=", sz, "\n");
    Print("  CC + counts         | ", String(t1, 4), "ms | ", nKeys1, " distinct orders\n");
    Print("  OrdersClassReps     | ", String(t2, 4), "ms | ", nKeys2, " distinct orders\n");
    Print("  Element iteration   | ", String(t3, 4), "ms | ", nKeys3, " distinct orders\n");
    Print("  AsList+Set          | ", String(t4, 4), "ms\n");
od;

LogTo();
QUIT;
