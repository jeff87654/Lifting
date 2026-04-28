
LogTo("C:/Users/jeffr/Downloads/Lifting/normalsubgroups_D8_4.log");
Print("=== NormalSubgroups(D_8^4) — full lattice ===\n");

# Construct D_8^4 in standard 16-point embedding
t := Runtime();
D8 := TransitiveGroup(4, 3);
H := DirectProduct(D8, D8, D8, D8);
Print("[t+", Runtime()-t, "ms] |H| = ", Size(H), "\n");

# Time + run NormalSubgroups
Print("\n[t=0] beginning NormalSubgroups(H)...\n");
t := Runtime();
NS := NormalSubgroups(H);
Print("[t+", Runtime()-t, "ms] NormalSubgroups(H) DONE; count=", Length(NS), "\n");

# Distribution
sizes := SortedList(List(NS, Size));
Print("\n--- distribution by |K| ---\n");
for s in Set(sizes) do
    Print("  |K|=", s, "  index=", 4096/s, "  count=", Number(sizes, x -> x = s), "\n");
od;

# Save the lattice to disk: list of generator-lists, by index
Print("\nSaving to disk...\n");
PrintTo("C:/Users/jeffr/Downloads/Lifting/normalsubgroups_D8_4.g",
    "NORMALS_OF_D8_4 := [\n");
for K in NS do
    AppendTo("C:/Users/jeffr/Downloads/Lifting/normalsubgroups_D8_4.g",
        "  rec(size := ", Size(K), ", gens := ", GeneratorsOfGroup(K), "),\n");
od;
AppendTo("C:/Users/jeffr/Downloads/Lifting/normalsubgroups_D8_4.g", "];\n");
Print("saved to C:/Users/jeffr/Downloads/Lifting/normalsubgroups_D8_4.g\n");

LogTo();
QUIT;
