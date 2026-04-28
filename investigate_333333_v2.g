LogTo("C:/Users/jeffr/Downloads/Lifting/investigate_333333_v2.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# (C_3)^6 in S_18, partition [3,3,3,3,3,3]
part := [3,3,3,3,3,3];
factors := List([1..6], i -> TransitiveGroup(3,1));
shifted := []; offs := []; off := 0;
for f in factors do
    Add(offs, off); Add(shifted, ShiftGroup(f, off));
    off := off + NrMovedPoints(f);
od;
P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
SetSize(P, Product(List(shifted, Size)));
Npart := BuildPerComboNormalizer(part, factors, 18);

Print("|P|=", Size(P), " |Npart|=", Size(Npart), "\n");

# Enumerate all subdirect subgroups
t0 := Runtime();
all_subs := AllSubgroups(P);
subdirect := Filtered(all_subs, H -> IsFPFSubdirect(H, shifted, offs));
Print("Subdirect: ", Length(subdirect), " (", (Runtime()-t0)/1000.0, "s)\n");

# Bucket by Size first
sizeBuckets := rec();
for H in subdirect do
    s := String(Size(H));
    if not IsBound(sizeBuckets.(s)) then sizeBuckets.(s) := []; fi;
    Add(sizeBuckets.(s), H);
od;
Print("Buckets by size:\n");
for s in RecNames(sizeBuckets) do
    Print("  size=", s, ": ", Length(sizeBuckets.(s)), " elements\n");
od;

# For each size bucket, run OrbitsDomain
Print("\nDeduping via OrbitsDomain per size bucket:\n");
total_reps := 0;
for s in RecNames(sizeBuckets) do
    bucket := sizeBuckets.(s);
    t0 := Runtime();
    orbs := OrbitsDomain(Npart, bucket, function(H, n) return H^n; end);
    elapsed := (Runtime()-t0)/1000.0;
    Print("  size=", s, ": ", Length(bucket), " -> ", Length(orbs),
          " orbits (", elapsed, "s)\n");
    total_reps := total_reps + Length(orbs);
od;
Print("\nTotal N-orbit reps: ", total_reps, "\n");
Print("Disk says: 49\n");
Print("Delta: ", total_reps - 49, "\n");

LogTo();
QUIT;
