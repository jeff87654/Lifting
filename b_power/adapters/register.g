# b_power/adapters/_register.g — load every pure-power adapter and populate
# B2G_POWER_ADAPTERS.  Adapter files add themselves to B2G_POWER_ADAPTERS at
# Read time, so order doesn't matter.

if not IsBound(B2G_POWER_ADAPTERS) then
    B2G_POWER_ADAPTERS := rec();
fi;

Read("C:/Users/jeffr/Downloads/Lifting/b_power/adapters/c3.g");
Read("C:/Users/jeffr/Downloads/Lifting/b_power/adapters/v4.g");
Read("C:/Users/jeffr/Downloads/Lifting/b_power/adapters/c4.g");
Read("C:/Users/jeffr/Downloads/Lifting/b_power/adapters/d8.g");
# S3 adapter (s3.g) disabled 2026-05-21: depends on
# b_2group_adapters/_semidirect_engine.g which was deleted with the v3
# cleanup and was never tracked in git.  (3,2) is no longer in B_POWER_TG,
# so this adapter is unreachable anyway.  Reinstate when S3 enumerator is
# reimplemented.
