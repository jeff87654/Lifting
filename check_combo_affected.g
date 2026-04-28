###############################################################################
# check_combo_affected.g
#
# For each combo, determine whether the "unique centralizer complement" fast
# path at lifting_algorithm.g:1162 WOULD have fired (pre-fix) with non-trivial
# gcd — i.e., whether the combo is actually affected by the bug and needs
# re-running.
#
# Condition for the bug to fire at some layer:
#   - P has a non-abelian simple chief factor M/L at that layer.
#   - For some parent S (normal subgroup of P containing M), the quotient
#     Q = S/L has Size(C_Q(M/L)) = [S:M] and C_Q(M/L) ∩ M/L = 1.
#   - gcd(|C_Q(M/L)|, |M/L|) > 1.
#
# We do a fast approximate check: iterate all chief factors, identify
# non-abelian simple ones, then check the MAXIMAL parent S = P first (gives
# the "biggest" centralizer, most likely to match idx). If S=P triggers,
# the combo is definitely affected. If not, we iterate over smaller parents
# via NormalSubgroupsBetween(P, M), up to a cap, to find any triggering S.
#
# Output: affected_combos_confirmed.txt with "partition\tcombo_file\tverdict"
# lines where verdict in {AFFECTED, UNAFFECTED, UNKNOWN}.
###############################################################################

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Cap on parent enumeration per chief factor to keep per-combo cost bounded
PARENT_CHECK_LIMIT := 200;

# For a single combo, return "AFFECTED", "UNAFFECTED", or "UNKNOWN".
CheckComboAffected := function(factors_list)
    local shifted, offs, off, k, P, series, i, M, L, M_bar, hom, Q, C,
          idx, parents, sp, verdict, parent_count, factor, t0;

    t0 := Runtime();

    # Build shifted factors and P
    shifted := [];
    offs := [];
    off := 0;
    for factor in factors_list do
        Add(offs, off);
        Add(shifted, ShiftGroup(factor, off));
        off := off + NrMovedPoints(factor);
    od;
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));

    # Chief series
    series := ChiefSeries(P);

    # Iterate non-abelian simple chief factors
    for i in [1..Length(series) - 1] do
        M := series[i];
        L := series[i + 1];
        # Chief factor M/L; build abstract quotient
        hom := NaturalHomomorphismByNormalSubgroup(M, L);
        M_bar := ImagesSource(hom);
        if not (IsSimpleGroup(M_bar) and not IsAbelian(M_bar)) then
            continue;
        fi;
        # Non-abelian simple chief factor found.
        # Check parents: start with P itself, then iterate normals containing M.
        parents := Filtered(NormalSubgroups(P), S -> IsSubgroup(S, M));
        parent_count := 0;
        for sp in parents do
            parent_count := parent_count + 1;
            if parent_count > PARENT_CHECK_LIMIT then
                return rec(verdict := "UNKNOWN",
                           reason := "parent limit exceeded",
                           elapsed := Runtime() - t0);
            fi;
            # Q = sp / L
            hom := NaturalHomomorphismByNormalSubgroup(sp, L);
            Q := ImagesSource(hom);
            M_bar := Image(hom, M);
            C := Centralizer(Q, M_bar);
            idx := Size(sp) / Size(M);
            if Size(C) = idx and Size(Intersection(C, M_bar)) = 1 then
                if Gcd(Size(C), Size(M_bar)) > 1 then
                    return rec(verdict := "AFFECTED",
                               reason := Concatenation("|S|=", String(Size(sp)),
                                         " |M|=", String(Size(M)),
                                         " |L|=", String(Size(L)),
                                         " |C|=", String(Size(C)),
                                         " |M_bar|=", String(Size(M_bar)),
                                         " gcd=", String(Gcd(Size(C), Size(M_bar)))),
                               elapsed := Runtime() - t0);
                fi;
            fi;
        od;
    od;
    return rec(verdict := "UNAFFECTED",
               reason := "no simple-factor fast path triggers",
               elapsed := Runtime() - t0);
end;

# Parse a combo filename like "[2,1]_[4,3]_[4,3]_[8,37].g" into factor list
ParseComboFile := function(name)
    local parts, result, p, deg, ti, G;
    # Strip ".g"
    if EndsWith(name, ".g") then
        name := name{[1..Length(name)-2]};
    fi;
    # Split on "_" — but only at top level ([d,t]_[d,t] style)
    result := [];
    parts := SplitString(name, "_");
    for p in parts do
        # p is like "[2,1]"
        # Strip brackets
        if Length(p) >= 2 and p[1] = '[' and p[Length(p)] = ']' then
            p := p{[2..Length(p)-1]};
            # p is like "2,1"
            deg := Int(SplitString(p, ",")[1]);
            ti := Int(SplitString(p, ",")[2]);
            G := TransitiveGroup(deg, ti);
            Add(result, G);
        fi;
    od;
    return result;
end;

# Main: read affected_combos.txt and check each
ProcessAffectedList := function(inputFile, outputFile)
    local input, lines, line, parts, part, fname, deduped, factors,
          result, line_num, t_start, n_total, n_affected, n_unaffected,
          n_unknown, out;

    t_start := Runtime();
    n_total := 0;
    n_affected := 0;
    n_unaffected := 0;
    n_unknown := 0;

    PrintTo(outputFile, "# partition\tcombo_file\tverdict\telapsed_ms\tdetails\n");

    input := InputTextFile(inputFile);
    line_num := 0;
    while not IsEndOfStream(input) do
        line := ReadLine(input);
        if line = fail then break; fi;
        line_num := line_num + 1;
        if Length(line) = 0 or line[1] = '#' then continue; fi;
        # Remove trailing newline
        if line[Length(line)] = '\n' then
            line := line{[1..Length(line)-1]};
        fi;
        parts := SplitString(line, "\t");
        if Length(parts) < 2 then continue; fi;
        part := parts[1];
        fname := parts[2];
        factors := ParseComboFile(fname);
        if Length(factors) = 0 then continue; fi;
        n_total := n_total + 1;
        result := CheckComboAffected(factors);
        AppendTo(outputFile, part, "\t", fname, "\t",
                 result.verdict, "\t", result.elapsed, "\t",
                 result.reason, "\n");
        if result.verdict = "AFFECTED" then
            n_affected := n_affected + 1;
        elif result.verdict = "UNAFFECTED" then
            n_unaffected := n_unaffected + 1;
        else
            n_unknown := n_unknown + 1;
        fi;
        if n_total mod 100 = 0 then
            Print("Progress: ", n_total, " combos checked (",
                  n_affected, " affected, ", n_unaffected, " unaffected, ",
                  n_unknown, " unknown) — ",
                  Int((Runtime() - t_start) / 1000), "s\n");
        fi;
    od;
    CloseStream(input);
    Print("\nFinal: ", n_total, " combos, ", n_affected, " affected, ",
          n_unaffected, " unaffected, ", n_unknown, " unknown\n");
    Print("Total elapsed: ", Int((Runtime() - t_start) / 1000), "s\n");
end;
