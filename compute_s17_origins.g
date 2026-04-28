###############################################################################
# Compute origin combos for the 1,466,358 S17 subgroups.
# Output one line per group: [partition, [factor_pairs]]
# Partition = sorted-descending orbit lengths on [1..18] (with point 18 fixed)
# factor_pairs[i] = [orbit_length, transitive_id] for orbit i
###############################################################################

LogTo("C:/Users/jeffr/Downloads/Lifting/compute_s17_origins.log");
SetInfoLevel(InfoWarning, 0);

# Read S17 cycles file (a `return [...]` expression)
Read("C:/Users/jeffr/Downloads/Lifting/_load_s17.g");
# After Read, ALL is bound globally to the list of S17 subgroups
# (gens lists). Length(ALL) should be 1466358.
Print("Loaded ", Length(ALL), " S17 generator lists\n");

OUT_PATH := "C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache/s17_origins.g";
out := OutputTextFile(OUT_PATH, false);
SetPrintFormattingStatus(out, false);

PrintTo(out, "# Origin combos for S17 subgroups, viewed as S18 subgroups (point 18 fixed)\n");
PrintTo(out, "# Format: [partition, [factor_pairs]]\n");
PrintTo(out, "# Total entries: ", Length(ALL), "\n");
PrintTo(out, "return [\n");

OriginOf := function(gens)
    local H, orbs, sortedOrbs, partition, factors, o, len, action, ti, mvd;
    if Length(gens) = 0 or ForAll(gens, IsOne) then
        # Trivial group: 18 fixed points
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
        if len = 1 then
            Add(factors, [1, 1]);
        elif len = 2 then
            Add(factors, [2, 1]);
        else
            action := Action(H, o);
            ti := TransitiveIdentification(action);
            Add(factors, [len, ti]);
        fi;
    od;
    return [partition, factors];
end;

t0 := Runtime();
last_log := t0;
for i in [1..Length(ALL)] do
    res := OriginOf(ALL[i]);
    PrintTo(out, "  ", res, ",\n");
    if Runtime() - last_log > 30000 then
        Print("  i=", i, "/", Length(ALL), " elapsed=",
              Int((Runtime()-t0)/1000), "s rate=",
              Int(i / Maximum(1, Int((Runtime()-t0)/1000))), "/s\n");
        last_log := Runtime();
    fi;
od;
PrintTo(out, "];\n");
CloseStream(out);

Print("Wrote ", Length(ALL), " origins in ", (Runtime()-t0)/1000.0, "s\n");
LogTo();
QUIT;
