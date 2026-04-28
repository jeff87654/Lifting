LogTo("C:/Users/jeffr/Downloads/Lifting/bench_order_large.log");

Print("\n=== Order histogram scaling at larger sizes ===\n\n");

# Test groups of various sizes
testGroups := [
    SymmetricGroup(6),    # 720
    SymmetricGroup(7),    # 5040
    SymmetricGroup(8),    # 40320
    SymmetricGroup(9),    # 362880
    SymmetricGroup(10),   # 3628800
    AlternatingGroup(8),  # 20160
    AlternatingGroup(9),  # 181440
    AlternatingGroup(10), # 1814400
];

for H in testGroups do
    # Rebuild to avoid cached iteration
    H2 := Group(GeneratorsOfGroup(H));
    sz := Size(H2);
    t0 := Runtime();
    hist := rec();
    for g in H2 do
        o := Order(g);
        key := Concatenation("o", String(o));
        if not IsBound(hist.(key)) then hist.(key) := 0; fi;
        hist.(key) := hist.(key) + 1;
    od;
    t := Runtime() - t0;
    Print("  |H|=", sz, ": ", t, "ms (", Float(t*1000)/Float(sz), " us/elem, ",
          Length(RecNames(hist)), " distinct orders)\n");
od;

LogTo();
QUIT;
