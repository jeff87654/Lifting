# b_power/power_dispatch.g — pure-power B2G engine entry point.
#
# Supports pure powers TG(d,t)^k for k >= 2 and (d,t) in:
#   (3,1) C_3, (3,2) S_3, (4,1) C_4, (4,2) V_4, (4,3) D_8.
#
# Each adapter owns end-to-end enumeration of its TG; no cross-cluster gluing,
# no towers, no ports.  Pure-power C_2 is NOT in scope (use run_c2_fast_path).
#
# Public entry point:
#   B2GPowerRun(d, t, k, mode, out_path)
#     mode = "count"  -> returns Int (no file write).
#     mode = "emit"   -> writes legacy combo-file to out_path, returns Int.

# Load enumeration kernels and emit helpers.
Read("C:/Users/jeffr/Downloads/Lifting/b_elemab.g");      # C3, V4
Read("C:/Users/jeffr/Downloads/Lifting/b_c4.g");          # C4
Read("C:/Users/jeffr/Downloads/Lifting/b_d8.g");          # D8 (auto-loads b_d8_v2.g on demand)
# S3 kernel (b_2group_adapters/_semidirect_engine.g) removed 2026-05-21
# along with the v3 cleanup; was never tracked.  S3 adapter not registered.

Read("C:/Users/jeffr/Downloads/Lifting/b_power/power_utils_emit.g");

if not IsBound(B2G_POWER_ADAPTERS) then
    B2G_POWER_ADAPTERS := rec();
fi;
Read("C:/Users/jeffr/Downloads/Lifting/b_power/adapters/register.g");

B2GPowerRun := function(d, t, k, mode, out_path)
    local key, adapter;
    key := Concatenation(String(d), "_", String(t));
    if not IsBound(B2G_POWER_ADAPTERS.(key)) then
        Error("b_power: no adapter for (d,t) = (", d, ",", t, ")");
    fi;
    adapter := B2G_POWER_ADAPTERS.(key);
    if mode = "count" then
        return adapter.Count(k);
    elif mode = "emit" then
        return adapter.Emit(k, out_path);
    else
        Error("b_power: unknown mode '", mode, "' (expected 'count' or 'emit')");
    fi;
end;
