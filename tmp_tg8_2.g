
LogTo("C:/Users/jeffr/Downloads/Lifting/tg8_check2.log");
# Check what the anomalous 7 have in common
for Y in [12, 25, 32, 36, 37, 48, 49] do
    G := TransitiveGroup(8, Y);
    nNormals := Length(NormalSubgroups(G));
    isNaturalSym := IsNaturalSymmetricGroup(G);
    isNaturalAlt := IsNaturalAlternatingGroup(G);
    Print("TG(8,", Y, "): |G|=", Size(G),
          ", nNormals=", nNormals,
          ", NaturalSym=", isNaturalSym,
          ", NaturalAlt=", isNaturalAlt, "
");
od;
# Also check TG(8,22) and TG(8,35) which produce LARGE counts for comparison
Print("
Comparison (non-anomalous):
");
for Y in [22, 35, 9, 11, 15] do
    G := TransitiveGroup(8, Y);
    nNormals := Length(NormalSubgroups(G));
    Print("TG(8,", Y, "): |G|=", Size(G), ", nNormals=", nNormals, "
");
od;
LogTo();
QUIT;
