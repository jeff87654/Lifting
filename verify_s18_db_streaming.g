###############################################################################
# Stream-load S18 cycles + origins line-by-line, EvalString each entry
# (avoids GAP's giant-list-literal parser limit).
###############################################################################

LogTo("C:/Users/jeffr/Downloads/Lifting/verify_s18_db_streaming.log");
SetInfoLevel(InfoWarning, 0);

CACHE := "C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache";

# Load by streaming: each entry line starts with "  [" and ends with "],"
LoadStream := function(path)
    local fin, list, line, expr;
    list := [];
    fin := InputTextFile(path);
    line := ReadLine(fin);
    while line <> fail do
        # Skip header / footer / blank lines
        if Length(line) >= 3 and line{[1..3]} = "  [" then
            # Strip trailing newline (and trailing comma if present)
            line := Chomp(line);
            if line[Length(line)] = ',' then
                line := line{[1..Length(line)-1]};
            fi;
            # Skip leading "  "
            expr := line{[3..Length(line)]};
            Add(list, EvalString(expr));
        fi;
        line := ReadLine(fin);
    od;
    CloseStream(fin);
    return list;
end;

Print("Loading s18_subgroups_cycles.g (streaming)...\n");
t0 := Runtime();
GROUPS := LoadStream(Concatenation(CACHE, "/s18_subgroups_cycles.g"));
Print("  Loaded ", Length(GROUPS), " groups in ", (Runtime()-t0)/1000.0, "s\n");

Print("Loading s18_origin_combos.g (streaming)...\n");
t1 := Runtime();
ORIGINS := LoadStream(Concatenation(CACHE, "/s18_origin_combos.g"));
Print("  Loaded ", Length(ORIGINS), " origins in ", (Runtime()-t1)/1000.0, "s\n");

Print("\n=== Length agreement ===\n");
if Length(GROUPS) = Length(ORIGINS) and Length(GROUPS) = 7274651 then
    Print("  ", Length(GROUPS), " entries (matches expected 7274651)\n");
else
    Print("  *** MISMATCH: groups=", Length(GROUPS),
          " origins=", Length(ORIGINS), " (expected 7274651)\n");
fi;

# Spot-check
SpotCheck := function(idx)
    local gens, origin, H, orbs, sortedOrbs, partition, factors, o, len;
    gens := GROUPS[idx];
    origin := ORIGINS[idx];
    if Length(gens) = 0 or ForAll(gens, IsOne) then
        H := Group(());
    else
        H := Group(gens);
    fi;
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
        else Add(factors, [len, TransitiveIdentification(Action(H, o))]);
        fi;
    od;
    if origin[1] = partition and origin[2] = factors then
        Print("  idx=", idx, " AGREE part=", partition, "\n");
    else
        Print("  idx=", idx, " *** MISMATCH ***\n");
        Print("    origin: ", origin, "\n");
        Print("    actual: [", partition, ", ", factors, "]\n");
    fi;
end;

Print("\n=== Spot-check ===\n");
SpotCheck(1);                          # trivial
SpotCheck(2);                          # smallest non-trivial
SpotCheck(1466358);                    # last S17
SpotCheck(1466359);                    # first S18 FPF
SpotCheck(7274651);                    # last entry
SpotCheck(Random([2..1466358]));       # random S17
SpotCheck(Random([1466360..7274650])); # random FPF

LogTo();
QUIT;
