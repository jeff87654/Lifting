###############################################################################
# Resume: process S17 origins from index 889960 to end (1,466,358).
# Write to s17_origins_part2.g (no `return [` or `];` markers — just entries).
###############################################################################

LogTo("C:/Users/jeffr/Downloads/Lifting/compute_s17_origins_part2.log");
SetInfoLevel(InfoWarning, 0);
Read("C:/Users/jeffr/Downloads/Lifting/_load_s17.g");
Print("Loaded ", Length(ALL), " groups\n");

OUT_PATH := "C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache/s17_origins_part2.g";
out := OutputTextFile(OUT_PATH, false);
SetPrintFormattingStatus(out, false);

OriginOf := function(gens)
    local H, orbs, sortedOrbs, partition, factors, o, len, action;
    if Length(gens) = 0 or ForAll(gens, IsOne) then
        return [List([1..18], i -> 1), List([1..18], i -> [1, 1])];
    fi;
    H := Group(gens);
    orbs := Orbits(H, [1..18]);
    sortedOrbs := ShallowCopy(orbs);
    Sort(sortedOrbs, function(a, b)
        if Length(a) <> Length(b) then return Length(a) > Length(b); fi;
        return Minimum(a) < Minimum(b);
    end);
    partition := List(sortedOrbs, Length);
    factors := [];
    for o in sortedOrbs do
        len := Length(o);
        if len = 1 then Add(factors, [1, 1]);
        elif len = 2 then Add(factors, [2, 1]);
        else
            action := Action(H, o);
            Add(factors, [len, TransitiveIdentification(action)]);
        fi;
    od;
    return [partition, factors];
end;

START_IDX := 889960;
t0 := Runtime();
last_log := t0;
for i in [START_IDX..Length(ALL)] do
    res := OriginOf(ALL[i]);
    PrintTo(out, "  ", res, ",\n");
    if Runtime() - last_log > 30000 then
        Print("  i=", i, "/", Length(ALL), " elapsed=",
              Int((Runtime()-t0)/1000), "s rate=",
              Int((i - START_IDX + 1) / Maximum(1, Int((Runtime()-t0)/1000))),
              "/s\n");
        last_log := Runtime();
    fi;
od;
CloseStream(out);

Print("Wrote ", Length(ALL) - START_IDX + 1, " more origins in ", (Runtime()-t0)/1000.0, "s\n");
LogTo();
QUIT;
