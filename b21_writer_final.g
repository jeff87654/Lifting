################################################################################
# b21_writer_final.g
#
# Build the [2,1]^10 result file using support-first orbit enumeration.
################################################################################

Read("C:/Users/jeffr/Downloads/Lifting/b21_canonical.g");
Read("C:/Users/jeffr/Downloads/Lifting/b21_support_first.g");

# Build r x 10 matrix for one (support S, multiplicities mults) tuple.
SupportMultsToMatrix := function(S, mults, r, k)
    local mat, j, i, copies, vec;
    mat := List([1..r], i -> []);
    j := 0;
    for i in [1..Length(S)] do
        vec := DecodingOf(S[i], r);
        for copies in [1..mults[i]] do
            j := j + 1;
            for ii in [1..r] do mat[ii][j] := vec[ii]; od;
        od;
    od;
    if j <> k then Error("col count mismatch ", j, " vs ", k); fi;
    return mat;
end;

# Convert row in F_2^k -> permutation in S_(2k): product of (2j-1, 2j) for j with row[j]=1.
RowToInvolutionProduct := function(row, k)
    local p, j;
    p := ();
    for j in [1..k] do
        if not IsZero(row[j]) then p := p * (2*j - 1, 2*j); fi;
    od;
    return p;
end;

# Format list of permutations as [g1,g2,...] string.
FormatGenList := function(gens)
    local strs, g;
    strs := List(gens, g -> String(g));
    return Concatenation("[", JoinStringsWithSeparator(strs, ","), "]");
end;

# Main: enumerate all r=1..k orbits, build subgroup gens, write .g file.
WriteB21File := function(k, output_path)
    local r, all_reps, R, gens, mat, i, line, lines, fout, total, t0,
          combo;
    t0 := Runtime();
    all_reps := [];
    for r in [1..k] do
        Print("r=", r, "...\n");
        Append(all_reps, EnumerateRankRReps_SupportFirst(r, k));
    od;
    total := Length(all_reps);
    Print("Total reps: ", total, "\n");

    lines := [];
    for R in all_reps do
        mat := SupportMultsToMatrix(R.S, R.mults, R.r, k);
        gens := List([1..R.r], i -> RowToInvolutionProduct(mat[i], k));
        Add(lines, FormatGenList(gens));
    od;

    combo := List([1..k], i -> [2, 1]);
    fout := OutputTextFile(output_path, false);
    SetPrintFormattingStatus(fout, false);
    PrintTo(fout, "# combo: ", combo, "\n");
    PrintTo(fout, "# candidates: ", total, "\n");
    PrintTo(fout, "# deduped: ", total, "\n");
    PrintTo(fout, "# elapsed_ms: ", Runtime() - t0, "\n");
    for line in lines do
        PrintTo(fout, line, "\n");
    od;
    CloseStream(fout);
    Print("Wrote ", output_path, "\n");
    return total;
end;
