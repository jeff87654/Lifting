###############################################################################
# Verify the S18 subgroup database loads correctly into GAP and that
# the line-alignment between cycles file and origins file is exact.
###############################################################################

LogTo("C:/Users/jeffr/Downloads/Lifting/verify_s18_db.log");
SetInfoLevel(InfoWarning, 0);

CACHE := "C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache";

Print("=== Loading s18_subgroups_cycles.g ===\n");
t0 := Runtime();
GROUPS := ReadAsFunction(Concatenation(CACHE, "/s18_subgroups_cycles.g"))();
Print("  Loaded ", Length(GROUPS), " group generator lists in ",
      (Runtime()-t0)/1000.0, "s\n");
if Length(GROUPS) <> 7274651 then
    Print("  *** ERROR: expected 7274651, got ", Length(GROUPS), "\n");
fi;

Print("\n=== Loading s18_origin_combos.g ===\n");
t1 := Runtime();
ORIGINS := ReadAsFunction(Concatenation(CACHE, "/s18_origin_combos.g"))();
Print("  Loaded ", Length(ORIGINS), " origin combos in ",
      (Runtime()-t1)/1000.0, "s\n");
if Length(ORIGINS) <> 7274651 then
    Print("  *** ERROR: expected 7274651, got ", Length(ORIGINS), "\n");
fi;

Print("\n=== Length agreement ===\n");
if Length(GROUPS) = Length(ORIGINS) then
    Print("  ", Length(GROUPS), " = ", Length(ORIGINS), "\n");
else
    Print("  *** MISMATCH: groups=", Length(GROUPS), " origins=", Length(ORIGINS), "\n");
fi;

Print("\n=== Spot-check a few entries (orbit structure agrees with origin) ===\n");
SpotCheck := function(idx)
    local gens, origin, H, orbs, partition, factors, sortedOrbs, o, len,
          actual_partition, actual_factors;
    gens := GROUPS[idx];
    origin := ORIGINS[idx];
    Print("  idx=", idx, ":\n");
    Print("    origin partition: ", origin[1], "\n");
    Print("    origin factors:   ", origin[2], "\n");
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
    actual_partition := List(sortedOrbs, Length);
    actual_factors := [];
    for o in sortedOrbs do
        len := Length(o);
        if len = 1 then Add(actual_factors, [1, 1]);
        elif len = 2 then Add(actual_factors, [2, 1]);
        else
            Add(actual_factors,
                [len, TransitiveIdentification(Action(H, o))]);
        fi;
    od;
    Print("    actual partition: ", actual_partition, "\n");
    Print("    actual factors:   ", actual_factors, "\n");
    if origin[1] = actual_partition and origin[2] = actual_factors then
        Print("    AGREE\n");
    else
        Print("    *** MISMATCH ***\n");
    fi;
end;

# Check trivial group, an early S17 entry, S17 boundary, several S18 FPFs
SpotCheck(1);                # trivial group
SpotCheck(2);                # second
SpotCheck(1466358);          # last S17
SpotCheck(1466359);          # first S18 FPF
SpotCheck(1466359 + 1000);   # mid-FPF
SpotCheck(7274651);          # last entry
# Random checks
checks := [Random([2..1466358]), Random([1466360..7274650])];
for c in checks do SpotCheck(c); od;

LogTo();
QUIT;
