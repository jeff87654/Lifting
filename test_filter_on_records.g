
LogTo("C:/Users/jeffr/Downloads/Lifting/test_filter_on_records.log");
Print("=== filter on records vs filter on Groups ===\n");

t := Runtime();
Read("C:/Users/jeffr/Downloads/Lifting/normalsubgroups_D8_4.g");
Print("[t+", Runtime()-t, "ms] loaded NORMALS_OF_D8_4 (",
      Length(NORMALS_OF_D8_4), " records)\n\n");

q_size_filter := [1, 2, 3, 6];
H_size := 4096;

# --- Strategy A: filter on records (precomputed size) ---
Print("--- A: filter on records ---\n");
t := Runtime();
records_filt := Filtered(NORMALS_OF_D8_4,
    e -> e.size <> H_size and (H_size / e.size) in q_size_filter);
Print("[t+", Runtime()-t, "ms] filtered to ", Length(records_filt), " records\n");
t := Runtime();
groups_A := List(records_filt, function(e)
    if Length(e.gens) = 0 then return TrivialGroup(IsPermGroup); fi;
    return Group(e.gens);
end);
Print("[t+", Runtime()-t, "ms] built ", Length(groups_A), " Group objects\n\n");

# --- Strategy B: build all Groups, then filter on Size ---
Print("--- B: build all Groups, filter on Size ---\n");
t := Runtime();
all_groups := List(NORMALS_OF_D8_4, function(e)
    if Length(e.gens) = 0 then return TrivialGroup(IsPermGroup); fi;
    return Group(e.gens);
end);
Print("[t+", Runtime()-t, "ms] built ", Length(all_groups), " Group objects\n");
t := Runtime();
groups_B := Filtered(all_groups,
    K -> Size(K) <> H_size and (H_size / Size(K)) in q_size_filter);
Print("[t+", Runtime()-t, "ms] filtered to ", Length(groups_B), " Groups\n\n");

Print("Both strategies surface ", Length(groups_A), " survivors.\n");
LogTo();
QUIT;
