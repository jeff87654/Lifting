# Diagnostic script for orbital H^1 bug
# Tests whether the H^1 action is truly linear (as the code assumes)
# or affine (with a non-zero translation component).
#
# Theory: The action of outer normalizer element n on H^1 is:
#   n * [f] = [A * f + delta]
# where A is a matrix (linear part) and delta is the cocycle of the
# conjugated base complement (affine translation).
# The current code only computes A, assuming delta = 0.
# If the base complement C_0 is NOT preserved by n, then delta != 0,
# and the orbits are wrong.

TestAffineOffset := function(Q, M_bar, outerNormGens, S, L, homSL, P)
    local module, H1, complementInfo, allComplements,
          gen, nInv, j, gi_Q, gi_S, gi_S_conj, gi_Q_conj,
          C0, C0_gens_lifted, C0_conj_gens_Q,
          field, dimH1, inC0, delta_nonzero;

    # Create module (same as GetH1OrbitRepresentatives)
    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
    if not IsRecord(module) or IsBound(module.isNonSplit) or IsBound(module.isModuleConstructionFailed) then
        Print("Module construction failed\n");
        return false;
    fi;

    H1 := CachedComputeH1(module);
    dimH1 := H1.H1Dimension;
    field := module.field;

    if dimH1 = 0 then
        return false;  # Unique complement, no issue
    fi;

    C0 := Group(module.preimageGens);

    for gen in outerNormGens do
        nInv := gen^(-1);
        delta_nonzero := false;

        # For each preimage generator, conjugate by n and check if result is in C_0
        for j in [1..Length(module.preimageGens)] do
            gi_Q := module.preimageGens[j];

            # Lift to S, conjugate by n, map back to Q
            gi_S := PreImagesRepresentative(homSL, gi_Q);
            gi_S_conj := gi_S^nInv;  # = n * gi_S * n^{-1}
            gi_Q_conj := Image(homSL, gi_S_conj);

            # Check if gi_Q_conj is in C_0
            if not (gi_Q_conj in C0) then
                delta_nonzero := true;
            fi;
        od;

        if delta_nonzero then
            Print("  *** AFFINE OFFSET DETECTED for outer norm gen (order ",
                  Order(gen), ") ***\n");
            Print("  dim H^1 = ", dimH1, ", |H^1| = ", Characteristic(field)^dimH1,
                  ", |Q| = ", Size(Q), "\n");
            return true;
        fi;
    od;

    return false;
end;

# Instrument LiftThroughLayer to detect affine offsets
# Call this from the main code at the point where orbital is about to be used
DiagnoseOrbitalInLift := function(Q, M_bar, outerNormGens, S, L, homSL, P,
                                   fpfFilterForComplement)
    local module, H1, complementInfo, allComplements, orbitalComplements,
          nAll, nOrbital, hasAffine;

    Print("\n=== ORBITAL DIAGNOSTIC ===\n");
    Print("|Q|=", Size(Q), " |M_bar|=", Size(M_bar), " |S|=", Size(S),
          " |L|=", Size(L), " #outerNormGens=", Length(outerNormGens), "\n");

    # Test for affine offset
    hasAffine := TestAffineOffset(Q, M_bar, outerNormGens, S, L, homSL, P);

    # Compute complements BOTH ways
    # Way 1: All complements (no orbital)
    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
    if not IsRecord(module) or IsBound(module.isNonSplit) or IsBound(module.isModuleConstructionFailed) then
        Print("Module construction failed\n");
        return;
    fi;

    H1 := CachedComputeH1(module);
    if H1.H1Dimension = 0 then
        Print("dim H^1 = 0, unique complement\n");
        return;
    fi;

    complementInfo := BuildComplementInfo(Q, M_bar, module);
    allComplements := EnumerateComplementsFromH1(H1, complementInfo);
    nAll := Length(allComplements);

    # Way 2: Orbital method
    orbitalComplements := GetH1OrbitRepresentatives(Q, M_bar, outerNormGens, S, L, homSL, P, fpfFilterForComplement);
    nOrbital := Length(orbitalComplements);

    # Way 3: All complements, filtered by FPF
    if fpfFilterForComplement <> fail then
        allComplements := Filtered(allComplements, fpfFilterForComplement);
        nAll := Length(allComplements);
        Print("After FPF filter: ", nAll, " complements\n");
    fi;

    Print("All complements: ", nAll, "\n");
    Print("Orbital complements: ", nOrbital, "\n");

    if nOrbital < nAll then
        Print("ORBITAL REDUCED BY ", nAll - nOrbital, "\n");
        if hasAffine then
            Print(">>> LIKELY BUG: Affine offset + reduction = incorrect merging <<<\n");
        fi;
    fi;
    Print("=== END DIAGNOSTIC ===\n\n");
end;
