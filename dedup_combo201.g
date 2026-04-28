LogTo("C:/Users/jeffr/Downloads/Lifting/dedup_combo201.log");
Print("Dedup combo 201 against existing [6,5,5] groups\n");

N := 16;
SN := SymmetricGroup(N);

# Load combo 201 generators
Print("Loading combo 201 generators...\n");
combo201_gens_raw := ReadAsFunction("C:/Users/jeffr/Downloads/Lifting/combo201_gens.txt");;
# Parse the file manually - each group is on potentially multiple lines
_content := StringFile("C:/Users/jeffr/Downloads/Lifting/combo201_gens.txt");
# Remove line continuations (backslash-newline)
_content := ReplacedString(_content, "\\\n", "");

combo201 := [];
_lines := SplitString(_content, "\n");
for _l in _lines do
    _l := NormalizedWhitespace(_l);
    if Length(_l) > 2 then
        _gensList := EvalString(_l);
        if IsList(_gensList) and Length(_gensList) > 0 then
            _perms := List(_gensList, PermList);
            Add(combo201, Group(_perms));
        fi;
    fi;
od;
Print("  Loaded ", Length(combo201), " groups from combo 201\n");

# Load existing [6,5,5] generators
Print("Loading existing [6,5,5] generators...\n");
_content2 := StringFile("C:/Users/jeffr/Downloads/Lifting/parallel_s16/gens/gens_6_5_5.txt");
_content2 := ReplacedString(_content2, "\\\n", "");
existing := [];
_lines2 := SplitString(_content2, "\n");
for _l in _lines2 do
    _l := NormalizedWhitespace(_l);
    if Length(_l) > 2 then
        _gensList := EvalString(_l);
        if IsList(_gensList) and Length(_gensList) > 0 then
            _perms := List(_gensList, PermList);
            Add(existing, Group(_perms));
        fi;
    fi;
od;
Print("  Loaded ", Length(existing), " existing groups\n");

# Dedup: check each combo201 group against existing
newGroups := [];
for i in [1..Length(combo201)] do
    H := combo201[i];
    isNew := true;
    for j in [1..Length(existing)] do
        ex := existing[j];
        if Size(H) = Size(ex) then
            if RepresentativeAction(SN, H, ex) <> fail then
                isNew := false;
                Print("  combo201[", i, "] (order ", Size(H), ") = existing[", j, "]\n");
                break;
            fi;
        fi;
    od;
    if isNew then
        Add(newGroups, H);
        Print("  combo201[", i, "] (order ", Size(H), ") is NEW\n");
    fi;
od;

Print("\n=== RESULT ===\n");
Print("Combo 201 groups: ", Length(combo201), "\n");
Print("New (not in existing): ", Length(newGroups), "\n");
Print("Corrected [6,5,5] count: ", Length(existing), " + ", Length(newGroups),
      " = ", Length(existing) + Length(newGroups), "\n");

LogTo();
QUIT;
