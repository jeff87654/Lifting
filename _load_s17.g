###############################################################################
# Helper: load s17_subgroups_cycles.g into a global ALL.
# That file uses `return [...]`; we wrap it via ReadAsFunction.
###############################################################################
ALL := ReadAsFunction("C:/Users/jeffr/Downloads/Symmetric Groups/conjugacy_cache/s17_subgroups_cycles.g")();
