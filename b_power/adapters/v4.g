# b_power/adapters/v4.g — pure V_4^k enumeration.
#
# Delegates to b_elemab.g.  V_4 = TG(4, 2) is elementary abelian of order
# 4 = 2^2, so the parameters are p = 2, m = 2.

B2GPower_V4_Count := function(k)
    local total, r, reps;
    total := 0;
    for r in [2..2*k] do
        reps := ELEMAB_EnumerateRankRReps(2, 2, k, r);
        total := total + Length(reps);
    od;
    return total;
end;

B2GPower_V4_Emit := function(k, out_path)
    return WriteBElemabFile(2, 2, k, 4, 2, out_path);
end;

B2G_POWER_ADAPTERS.("4_2") := rec(
    key := "4_2",
    name := "V4",
    d := 4,
    t := 2,
    Count := B2GPower_V4_Count,
    Emit := B2GPower_V4_Emit
);
