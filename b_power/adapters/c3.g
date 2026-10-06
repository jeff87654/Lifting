# b_power/adapters/c3.g — pure C_3^k enumeration.
#
# Delegates to b_elemab.g, which already enumerates GL_m(F_p) wr S_k orbits on
# rank-r F_p^k-subspaces and writes the legacy combo-file format directly.
# For C_3 = TG(3, 1) the parameters are p = 3, m = 1.

B2GPower_C3_Count := function(k)
    local total, r, reps;
    total := 0;
    for r in [1..k] do
        reps := ELEMAB_EnumerateRankRReps(3, 1, k, r);
        total := total + Length(reps);
    od;
    return total;
end;

B2GPower_C3_Emit := function(k, out_path)
    return WriteBElemabFile(3, 1, k, 3, 1, out_path);
end;

B2G_POWER_ADAPTERS.("3_1") := rec(
    key := "3_1",
    name := "C3",
    d := 3,
    t := 1,
    Count := B2GPower_C3_Count,
    Emit := B2GPower_C3_Emit
);
