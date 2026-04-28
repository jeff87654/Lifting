LogTo("C:/Users/jeffr/Downloads/Lifting/verify_s18_db_split.log");
SetInfoLevel(InfoWarning, 0);

t0 := Runtime();
Read("C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache/s18_load.g");
Print("\nTotal load time: ", (Runtime()-t0)/1000.0, "s\n\n");

# Sanity checks
if Length(GROUPS) <> 7274651 then
    Print("*** ERROR: GROUPS length ", Length(GROUPS), "\n");
fi;
if Length(ORIGINS) <> 7274651 then
    Print("*** ERROR: ORIGINS length ", Length(ORIGINS), "\n");
fi;

# Spot-check: orbit structure of GROUPS[idx] matches ORIGINS[idx]
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
        Print("  idx=", idx, " AGREE: ", origin[1], " factors=", origin[2], "\n");
    else
        Print("  idx=", idx, " *** MISMATCH ***\n");
        Print("    origin: ", origin, "\n");
        Print("    actual: [", partition, ", ", factors, "]\n");
    fi;
end;

Print("=== Spot-check ===\n");
SpotCheck(1);                      # trivial group
SpotCheck(2);                      # smallest non-trivial
SpotCheck(1466358);                # last S17
SpotCheck(1466359);                # first S18 FPF
SpotCheck(7274651);                # last entry
SpotCheck(Random([2..1466358]));   # random S17
SpotCheck(Random([1466360..7274650])); # random S18 FPF

LogTo();
QUIT;
