
LogTo("C:/Users/jeffr/Downloads/Lifting/test_gquotients_timing.log");
Print("=== GQuotients vs NormalSubgroups timing ===\n\n");

# Target quotients of interest for S19/S20
C2 := CyclicGroup(IsPermGroup, 2);
S3 := SymmetricGroup(3);
C4 := CyclicGroup(IsPermGroup, 4);
V4 := DirectProduct(CyclicGroup(IsPermGroup, 2), CyclicGroup(IsPermGroup, 2));
D8 := TransitiveGroup(4, 3);
A4 := AlternatingGroup(4);
S4 := SymmetricGroup(4);

TARGETS := [
    rec(name := "C_2", G := C2),
    rec(name := "S_3", G := S3),
    rec(name := "S_4", G := S4)
];

# Time helper: returns (elapsed_ms, kernel_count)
TimeGQuotients := function(H, Q)
    local t, gqs, kers;
    t := Runtime();
    gqs := GQuotients(H, Q);
    kers := Set(List(gqs, Kernel));
    return [Runtime() - t, Length(kers), Length(gqs)];
end;

TimeNormalSubgroups := function(H)
    local t, NS;
    t := Runtime();
    NS := NormalSubgroups(H);
    return [Runtime() - t, Length(NS)];
end;

Print("\n--- D_8 = TG(4,3) ---\n");
H := TransitiveGroup(4, 3);
Print("|H| = ", Size(H), "\n");
for tgt in TARGETS do
    res := TimeGQuotients(H, tgt.G);
    Print("  GQuotients(H, ", tgt.name, "): ",
          res[1], "ms  kernels=", res[2], " homs=", res[3], "\n");
od;
if true then
    res := TimeNormalSubgroups(H);
    Print("  NormalSubgroups(H):  ", res[1], "ms  count=", res[2], "\n");
else
    Print("  NormalSubgroups(H):  (skipped — would take many minutes)\n");
fi;


Print("\n--- S_4 = TG(4,5) ---\n");
H := TransitiveGroup(4, 5);
Print("|H| = ", Size(H), "\n");
for tgt in TARGETS do
    res := TimeGQuotients(H, tgt.G);
    Print("  GQuotients(H, ", tgt.name, "): ",
          res[1], "ms  kernels=", res[2], " homs=", res[3], "\n");
od;
if true then
    res := TimeNormalSubgroups(H);
    Print("  NormalSubgroups(H):  ", res[1], "ms  count=", res[2], "\n");
else
    Print("  NormalSubgroups(H):  (skipped — would take many minutes)\n");
fi;


Print("\n--- C_3^2 ---\n");
H := DirectProduct(CyclicGroup(IsPermGroup, 3), CyclicGroup(IsPermGroup, 3));
Print("|H| = ", Size(H), "\n");
for tgt in TARGETS do
    res := TimeGQuotients(H, tgt.G);
    Print("  GQuotients(H, ", tgt.name, "): ",
          res[1], "ms  kernels=", res[2], " homs=", res[3], "\n");
od;
if true then
    res := TimeNormalSubgroups(H);
    Print("  NormalSubgroups(H):  ", res[1], "ms  count=", res[2], "\n");
else
    Print("  NormalSubgroups(H):  (skipped — would take many minutes)\n");
fi;


Print("\n--- D_8^2 ---\n");
H := DirectProduct(TransitiveGroup(4,3), TransitiveGroup(4,3));
Print("|H| = ", Size(H), "\n");
for tgt in TARGETS do
    res := TimeGQuotients(H, tgt.G);
    Print("  GQuotients(H, ", tgt.name, "): ",
          res[1], "ms  kernels=", res[2], " homs=", res[3], "\n");
od;
if true then
    res := TimeNormalSubgroups(H);
    Print("  NormalSubgroups(H):  ", res[1], "ms  count=", res[2], "\n");
else
    Print("  NormalSubgroups(H):  (skipped — would take many minutes)\n");
fi;


Print("\n--- S_3^2 ---\n");
H := DirectProduct(SymmetricGroup(3), SymmetricGroup(3));
Print("|H| = ", Size(H), "\n");
for tgt in TARGETS do
    res := TimeGQuotients(H, tgt.G);
    Print("  GQuotients(H, ", tgt.name, "): ",
          res[1], "ms  kernels=", res[2], " homs=", res[3], "\n");
od;
if true then
    res := TimeNormalSubgroups(H);
    Print("  NormalSubgroups(H):  ", res[1], "ms  count=", res[2], "\n");
else
    Print("  NormalSubgroups(H):  (skipped — would take many minutes)\n");
fi;


Print("\n--- D_8^3 (S12 [4,3]^3 LEFT) ---\n");
H := DirectProduct(TransitiveGroup(4,3), TransitiveGroup(4,3), TransitiveGroup(4,3));
Print("|H| = ", Size(H), "\n");
for tgt in TARGETS do
    res := TimeGQuotients(H, tgt.G);
    Print("  GQuotients(H, ", tgt.name, "): ",
          res[1], "ms  kernels=", res[2], " homs=", res[3], "\n");
od;
if true then
    res := TimeNormalSubgroups(H);
    Print("  NormalSubgroups(H):  ", res[1], "ms  count=", res[2], "\n");
else
    Print("  NormalSubgroups(H):  (skipped — would take many minutes)\n");
fi;


Print("\n--- S_4^3 (S12 [4,5]^3) ---\n");
H := DirectProduct(TransitiveGroup(4,5), TransitiveGroup(4,5), TransitiveGroup(4,5));
Print("|H| = ", Size(H), "\n");
for tgt in TARGETS do
    res := TimeGQuotients(H, tgt.G);
    Print("  GQuotients(H, ", tgt.name, "): ",
          res[1], "ms  kernels=", res[2], " homs=", res[3], "\n");
od;
if true then
    res := TimeNormalSubgroups(H);
    Print("  NormalSubgroups(H):  ", res[1], "ms  count=", res[2], "\n");
else
    Print("  NormalSubgroups(H):  (skipped — would take many minutes)\n");
fi;


Print("\n--- S_3^3 (S9 [3,2]^3) ---\n");
H := DirectProduct(SymmetricGroup(3), SymmetricGroup(3), SymmetricGroup(3));
Print("|H| = ", Size(H), "\n");
for tgt in TARGETS do
    res := TimeGQuotients(H, tgt.G);
    Print("  GQuotients(H, ", tgt.name, "): ",
          res[1], "ms  kernels=", res[2], " homs=", res[3], "\n");
od;
if true then
    res := TimeNormalSubgroups(H);
    Print("  NormalSubgroups(H):  ", res[1], "ms  count=", res[2], "\n");
else
    Print("  NormalSubgroups(H):  (skipped — would take many minutes)\n");
fi;


Print("\n--- D_8^4 (S16 [4,3]^4 LEFT) ---\n");
H := DirectProduct(TransitiveGroup(4,3), TransitiveGroup(4,3), TransitiveGroup(4,3), TransitiveGroup(4,3));
Print("|H| = ", Size(H), "\n");
for tgt in TARGETS do
    res := TimeGQuotients(H, tgt.G);
    Print("  GQuotients(H, ", tgt.name, "): ",
          res[1], "ms  kernels=", res[2], " homs=", res[3], "\n");
od;
if false then
    res := TimeNormalSubgroups(H);
    Print("  NormalSubgroups(H):  ", res[1], "ms  count=", res[2], "\n");
else
    Print("  NormalSubgroups(H):  (skipped — would take many minutes)\n");
fi;

Print("\n=== done ===\n");
LogTo();
QUIT;
