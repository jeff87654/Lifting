LogTo("C:/Users/jeffr/Downloads/Lifting/bench_cc_scaling.log");

Print("\n=== ConjugacyClasses cost scaling ===\n\n");

# Test on well-known groups of increasing size
testGroups := [
    ["C_4",            CyclicGroup(IsPermGroup, 4)],
    ["S_3",            SymmetricGroup(3)],
    ["D_4",            DihedralGroup(IsPermGroup, 8)],
    ["Q_8",            QuaternionGroup(IsPermGroup, 8)],
    ["S_4",            SymmetricGroup(4)],
    ["A_5",            AlternatingGroup(5)],
    ["S_5",            SymmetricGroup(5)],
    ["A_6",            AlternatingGroup(6)],
    ["S_6",            SymmetricGroup(6)],
    ["A_7",            AlternatingGroup(7)],
    ["S_7",            SymmetricGroup(7)],
    ["A_8",            AlternatingGroup(8)],
    ["S_8",            SymmetricGroup(8)],
    ["A_9",            AlternatingGroup(9)],
    ["S_9",            SymmetricGroup(9)],
    ["A_10",           AlternatingGroup(10)],
    ["S_10",           SymmetricGroup(10)],
    ["A_11",           AlternatingGroup(11)],
    ["S_11",           SymmetricGroup(11)],
    ["A_12",           AlternatingGroup(12)],
    ["S_12",           SymmetricGroup(12)],
];

# Fresh groups each run to avoid caching artifacts
for entry in testGroups do
    name := entry[1];
    # Build a fresh group (otherwise CC gets cached between tests)
    if name = "C_4" then H := CyclicGroup(IsPermGroup, 4);
    elif name = "S_3" then H := SymmetricGroup(3);
    elif name = "D_4" then H := DihedralGroup(IsPermGroup, 8);
    elif name = "Q_8" then H := QuaternionGroup(IsPermGroup, 8);
    elif name = "S_4" then H := SymmetricGroup(4);
    elif name = "A_5" then H := AlternatingGroup(5);
    elif name = "S_5" then H := SymmetricGroup(5);
    elif name = "A_6" then H := AlternatingGroup(6);
    elif name = "S_6" then H := SymmetricGroup(6);
    elif name = "A_7" then H := AlternatingGroup(7);
    elif name = "S_7" then H := SymmetricGroup(7);
    elif name = "A_8" then H := AlternatingGroup(8);
    elif name = "S_8" then H := SymmetricGroup(8);
    elif name = "A_9" then H := AlternatingGroup(9);
    elif name = "S_9" then H := SymmetricGroup(9);
    elif name = "A_10" then H := AlternatingGroup(10);
    elif name = "S_10" then H := SymmetricGroup(10);
    elif name = "A_11" then H := AlternatingGroup(11);
    elif name = "S_11" then H := SymmetricGroup(11);
    elif name = "A_12" then H := AlternatingGroup(12);
    elif name = "S_12" then H := SymmetricGroup(12);
    fi;

    sz := Size(H);
    t0 := Runtime();
    cc := ConjugacyClasses(H);
    tCC := Runtime() - t0;
    Print("  ", name, " (|H|=", sz, "): ConjugacyClasses took ", tCC, "ms (",
          Length(cc), " classes)\n");
od;

LogTo();
QUIT;
