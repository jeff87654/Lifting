
LogTo("C:/Users/jeffr/Downloads/Lifting/test_ns_breakdown.log");
Print("=== NS breakdown on |H|=2048 subgroup of D_8^4 ===\n");

# Construct D_8^4
D8 := TransitiveGroup(4, 3);
LEFT := DirectProduct(D8, D8, D8, D8);
Print("|LEFT| = ", Size(LEFT), "\n");

# Pick an index-2 subgroup of LEFT — first thing of size 2048 in NORMALS_OF_D8_4
t := Runtime();
Read("C:/Users/jeffr/Downloads/Lifting/normalsubgroups_D8_4.g");
Print("[t+", Runtime()-t, "ms] loaded NORMALS_OF_D8_4 records\n");

t := Runtime();
H_record := First(NORMALS_OF_D8_4, e -> e.size = 2048);
H := Group(H_record.gens);
Print("[t+", Runtime()-t, "ms] picked H, |H|=", Size(H), "\n");

Print("HasPcgs(H): ", HasPcgs(H), "\n");
Print("IsSolvable(H): ", IsSolvableGroup(H), "\n");

# NS call
Print("\n--- NS itself ---\n");
t := Runtime();
NS := NormalSubgroups(H);
ns_t := Runtime() - t;
Print("[t+", ns_t, "ms] NormalSubgroups(H) returned ", Length(NS), " entries\n");

# Check if Size is cached on outputs
n_with_size := 0;
n_with_pcgs := 0;
for K in NS do
    if HasSize(K) then n_with_size := n_with_size + 1; fi;
    if HasPcgs(K) then n_with_pcgs := n_with_pcgs + 1; fi;
od;
Print("Of ", Length(NS), " output groups: ",
      n_with_size, " have Size cached, ", n_with_pcgs, " have Pcgs cached\n");

# Touch each (no real work)
t := Runtime();
for K in NS do
    # do nothing
od;
Print("[t+", Runtime()-t, "ms] empty iteration over NS\n");

# Compute Size on each
t := Runtime();
sizes := List(NS, Size);
Print("[t+", Runtime()-t, "ms] computed Size on each\n");

# After computing Size: now should be cached
n_with_size := Number(NS, K -> HasSize(K));
Print("After computing: ", n_with_size, " have Size cached\n");

# Compute IdGroup of quotient on each (qid)
t := Runtime();
qids := List(NS, function(K)
    local hom, Q;
    if Size(K) = Size(H) then return [1, 0]; fi;
    hom := NaturalHomomorphismByNormalSubgroup(H, K);
    Q := Range(hom);
    return Size(Q);   # just size to keep test simple
end);
Print("[t+", Runtime()-t, "ms] computed quotient sizes\n");

# Distribution of normal subgroup sizes
Print("\n--- distribution by |K| ---\n");
for s in Set(sizes) do
    Print("  |K|=", s, "  count=", Number(sizes, x -> x = s), "\n");
od;

LogTo();
QUIT;
