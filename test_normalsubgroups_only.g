
LogTo("C:/Users/jeffr/Downloads/Lifting/test_normalsubgroups_only.log");
Print("=== NormalSubgroups(D_8^4) timing ===\n");

# Construct D_8^4 = direct product of 4 copies of D_8 = TG(4,3),
# acting on 16 points as 4 disjoint 4-blocks.
t := Runtime();
D8 := TransitiveGroup(4, 3);
H := DirectProduct(D8, D8, D8, D8);
Print("[t+", Runtime()-t, "ms] constructed D_8^4, |H|=", Size(H), "\n");

# Just the one test
Print("\n--- NormalSubgroups(H) ---\n");
t := Runtime();
NS := NormalSubgroups(H);
Print("[t+", Runtime()-t, "ms] NormalSubgroups(H) DONE, count=", Length(NS), "\n");

# Distribution by index
sizes := SortedList(List(NS, Size));
Print("\nDistribution of |K| for K in NormalSubgroups(H):\n");
for s in Set(sizes) do
    Print("  |K|=", s, "  index=", 4096/s, "  count=", Number(sizes, x -> x = s), "\n");
od;

LogTo();
QUIT;
