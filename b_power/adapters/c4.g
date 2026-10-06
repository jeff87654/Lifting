# b_power/adapters/c4.g — pure C_4^k enumeration.
#
# Delegates to b_c4.g.  C_4 is abelian but not elementary abelian; the local
# C_2 inversion automorphism on each block lives inside BC4_EnumerateUorbits /
# BC4_LiftOrbitReps.

B2GPower_C4_Count := function(k)
    local setup, U_orbits, U_rec, C_orbits, C_rec, total, u_idx;
    setup := BC4_Setup(k);
    U_orbits := BC4_EnumerateUorbits(setup);
    total := 0;
    for u_idx in [1..Length(U_orbits)] do
        U_rec := U_orbits[u_idx];
        C_orbits := BC4_EnumerateCorbits(setup, U_rec);
        for C_rec in C_orbits do
            total := total + BC4_CountLiftOrbits(setup, U_rec, C_rec);
        od;
    od;
    return total;
end;

B2GPower_C4_Emit := function(k, out_path)
    return WriteBC4File(k, out_path);
end;

B2G_POWER_ADAPTERS.("4_1") := rec(
    key := "4_1",
    name := "C4",
    d := 4,
    t := 1,
    Count := B2GPower_C4_Count,
    Emit := B2GPower_C4_Emit
);
