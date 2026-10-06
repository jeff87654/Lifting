# b_power/adapters/d8.g — pure D_8^k enumeration.
#
# Delegates to b_d8.g.  WriteBD8File auto-loads b_d8_v2.g for the V2
# U-orbit engine and shares the on-disk U-orbit cache at
# database/bd8_u_orbits/k{k}.g with the existing bd8_fast path.

B2GPower_D8_Count := function(k)
    local setup, U_orbits, U_rec, C_orbits, C_rec, total, u_idx,
          u_cache_dir, u_cache_path;
    if not IsBound(BD8_EnumerateUorbitsV2) then
        Read("C:/Users/jeffr/Downloads/Lifting/b_d8_v2.g");
    fi;
    setup := BD8_Setup(k);
    BD8_ResetCCache();
    u_cache_dir := "C:/Users/jeffr/Downloads/Lifting/database/bd8_u_orbits";
    u_cache_path := Concatenation(u_cache_dir, "/k", String(k), ".g");
    if IsExistingFile(u_cache_path) then
        U_orbits := BD8_LoadUOrbits(setup, u_cache_path);
    else
        U_orbits := BD8_EnumerateUorbitsV2(setup);
        Exec(Concatenation("mkdir -p \"", u_cache_dir, "\""));
        BD8_SaveUOrbits(setup, U_orbits, u_cache_path);
    fi;
    total := 0;
    for u_idx in [1..Length(U_orbits)] do
        U_rec := U_orbits[u_idx];
        C_orbits := BD8_EnumerateCorbits(setup, U_rec);
        for C_rec in C_orbits do
            total := total + BD8_CountLiftOrbits(setup, U_rec, C_rec);
        od;
    od;
    return total;
end;

B2GPower_D8_Emit := function(k, out_path)
    return WriteBD8File(k, out_path);
end;

B2G_POWER_ADAPTERS.("4_3") := rec(
    key := "4_3",
    name := "D8",
    d := 4,
    t := 3,
    Count := B2GPower_D8_Count,
    Emit := B2GPower_D8_Emit
);
