LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/verify_s17_slow_combo_count.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

USE_HOLT_ENGINE := true;
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_ENGINE_MODE := "clean";

if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
if IsBound(HOLT_TF_CACHE) then HOLT_TF_CACHE := rec(); fi;

f1 := TransitiveGroup(2,1);
f2 := TransitiveGroup(5,5);
f3 := TransitiveGroup(5,5);
f4 := TransitiveGroup(5,5);
currentFactors := [f1, f2, f3, f4];

shifted := [];
offs := [];
off := 0;
for k in [1..Length(currentFactors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(currentFactors[k], off));
    off := off + NrMovedPoints(currentFactors[k]);
od;
P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
SetSize(P, Product(List(shifted, Size)));
partition := [5,5,5,2];
Npart := BuildPerComboNormalizer(partition, currentFactors, 17);
CURRENT_BLOCK_RANGES := [[1,2],[3,7],[8,12],[13,17]];

Print("|Npart| = ", Size(Npart), "\n\n");

# Get Holt's groups
Print("Running Holt clean pipeline...\n");
t0 := Runtime();
holtGroups := HoltFPFSubgroupClassesOfProduct(P, shifted, offs, Npart);
t := (Runtime() - t0) / 1000.0;
Print("Holt: ", Length(holtGroups), " classes in ", t, "s\n\n");

# --- SELF-CHECK: Holt's 46 are pairwise Npart-inequivalent ---
Print("Checking: are Holt's ", Length(holtGroups), " classes pairwise Npart-inequivalent?\n");
dupCount := 0;
for i in [1..Length(holtGroups)] do
  for j in [i+1..Length(holtGroups)] do
    if Size(holtGroups[i]) = Size(holtGroups[j]) and
       RepresentativeAction(Npart, holtGroups[i], holtGroups[j]) <> fail then
      dupCount := dupCount + 1;
      Print("  DUP pair: ", i, " <-> ", j, " |G|=", Size(holtGroups[i]), "\n");
    fi;
  od;
od;
Print("  Duplicates: ", dupCount, " (expect 0)\n\n");

# --- SELF-CHECK: Holt's 46 are all FPF-subdirect ---
Print("Checking: are all ", Length(holtGroups), " groups IsFPFSubdirect?\n");
badCount := 0;
for i in [1..Length(holtGroups)] do
  if not IsFPFSubdirect(holtGroups[i], shifted, offs) then
    badCount := badCount + 1;
    Print("  NOT FPF: index ", i, ", |G|=", Size(holtGroups[i]), "\n");
  fi;
od;
Print("  Bad: ", badCount, " (expect 0)\n\n");

# --- Write Holt's gens to file for external comparison ---
holtGensFile := "C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/holt_s17_slow_combo_gens.txt";
PrintTo(holtGensFile, "");
for H in holtGroups do
  gens := List(GeneratorsOfGroup(H), g -> ListPerm(g, 17));
  AppendTo(holtGensFile, String(gens), "\n");
od;
Print("Holt gens saved to: ", holtGensFile, "\n");
Print("Legacy combo file: ", "C:/Users/jeffr/Downloads/Lifting/parallel_s17_m6m7/[5,5,5,2]/[2,1]_[5,5]_[5,5]_[5,5].g", "\n");

LogTo();
QUIT;
