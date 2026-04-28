###############################################################################
# Quick spot-check: extract specific entries by line number (avoiding full load)
###############################################################################

LogTo("C:/Users/jeffr/Downloads/Lifting/verify_spot_check.log");
SetInfoLevel(InfoWarning, 0);

CACHE := "C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache";

# Extract entry at given index from a streaming file
ExtractEntry := function(path, idx)
    local fin, line, lineno, expr;
    fin := InputTextFile(path);
    lineno := 0;
    line := ReadLine(fin);
    while line <> fail do
        if Length(line) >= 3 and line{[1..3]} = "  [" then
            lineno := lineno + 1;
            if lineno = idx then
                line := Chomp(line);
                if line[Length(line)] = ',' then
                    line := line{[1..Length(line)-1]};
                fi;
                expr := line{[3..Length(line)]};
                CloseStream(fin);
                return EvalString(expr);
            fi;
        fi;
        line := ReadLine(fin);
    od;
    CloseStream(fin);
    return fail;
end;

CYCLES := Concatenation(CACHE, "/s18_subgroups_cycles.g");
ORIGINS := Concatenation(CACHE, "/s18_origin_combos.g");

SpotCheck := function(idx)
    local gens, origin, H, orbs, sortedOrbs, partition, factors, o, len;
    gens := ExtractEntry(CYCLES, idx);
    origin := ExtractEntry(ORIGINS, idx);
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
    if origin[1] = partition then
        # Compare factor multisets (in case order differs)
        if Set(origin[2]) = Set(factors) then
            Print("  idx=", idx, " AGREE part=", partition, " factors=", origin[2], "\n");
        else
            Print("  idx=", idx, " ** factor multiset MISMATCH **\n");
            Print("    origin: ", origin[2], "\n");
            Print("    actual: ", factors, "\n");
        fi;
    else
        Print("  idx=", idx, " ** partition mismatch **\n");
        Print("    origin: ", origin, "\n");
        Print("    actual: [", partition, ", ", factors, "]\n");
    fi;
end;

Print("=== Spot-check (after factor reorder fix) ===\n");
SpotCheck(1);
SpotCheck(2);
SpotCheck(1466358);
SpotCheck(1466359);     # first FPF — was mismatched before
SpotCheck(3771753);     # was mismatched before
SpotCheck(7274651);
SpotCheck(Random([1466360..7274650]));
SpotCheck(Random([1466360..7274650]));

LogTo();
QUIT;
