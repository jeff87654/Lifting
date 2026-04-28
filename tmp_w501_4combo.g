
LogTo("C:/Users/jeffr/Downloads/Lifting/w501_4combo.log");
GENERAL_AUT_HOM_VERBOSE := true;
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\nUSE_GENERAL_AUT_HOM = ", USE_GENERAL_AUT_HOM, "\n");
Print("GENERAL_AUT_HOM_VERBOSE = ", GENERAL_AUT_HOM_VERBOSE, "\n\n");

RunCombo := function(factors_desc, factors, offsets, total_deg)
    local P, N, t0, fpf, elapsed, shifted, i;
    Print("\n================================================================\n");
    Print("COMBO: ", factors_desc, "\n");
    Print("  factor sizes: ", List(factors, Size), "\n");

    shifted := List([1..Length(factors)],
                    i -> ShiftGroup(factors[i], offsets[i]));
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
    Print("  |P| = ", Size(P), "\n");

    N := BuildPerComboNormalizer(
        List(factors, f -> Length(MovedPoints(f))),
        factors, total_deg);
    Print("  |N_per_combo| = ", Size(N), "\n\n");

    t0 := Runtime();
    fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
    elapsed := Runtime() - t0;

    Print("\n  RESULT: ", Length(fpf), " raw FPF candidates, ",
          Float(elapsed/1000), "s\n");
end;

# Combo 1: W501's stuck combo.
RunCombo("TG(6,16) x TG(12,242)",
         [TransitiveGroup(6, 16), TransitiveGroup(12, 242)],
         [0, 6], 18);

# Combo 2: partition [2,4,6,6].
RunCombo("TG(2,1) x TG(4,3) x TG(6,3) x TG(6,14)",
         [TransitiveGroup(2, 1), TransitiveGroup(4, 3),
          TransitiveGroup(6, 3), TransitiveGroup(6, 14)],
         [0, 2, 6, 12], 18);

LogTo();
QUIT;
