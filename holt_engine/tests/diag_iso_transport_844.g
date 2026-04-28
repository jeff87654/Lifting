LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/diag_iso_transport_844.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
USE_HOLT_ENGINE := true;

# Build the bad combo: [T(4,1), T(4,2), T(8,17)] in S_16 partition [8,4,4].
# Legacy factor order descending by block size:
f1 := TransitiveGroup(8,17);
f2 := TransitiveGroup(4,2);
f3 := TransitiveGroup(4,1);
currentFactors := [f1, f2, f3];
partition := [8,4,4];

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

Print("P = T(8,17) x T(4,2) x T(4,1), |P| = ", Size(P), "\n");

Pt := RadicalGroup(P);
Print("|Pt| = ", Size(Pt), "\n");
Print("|Q| = ", Size(P)/Size(Pt), " (Q = P/Pt)\n");

# Compute Q directly to inspect
hom := NaturalHomomorphismByNormalSubgroup(P, Pt);
Q := ImagesSource(hom);
Print("Q structure: ", StructureDescription(Q), "\n");
Print("Q IdGroup: ", IdGroup(Q), "\n");

# Per-combo normalizer for dedup
Npart := BuildPerComboNormalizer(partition, currentFactors, 16);
CURRENT_BLOCK_RANGES := [[1,8],[9,12],[13,16]];
Print("|Npart| = ", Size(Npart), "\n\n");

# --- PART 1: run with iso-transport DISABLED ---
Print("=== ISO OFF ===\n");
HOLT_DISABLE_ISO_TRANSPORT := true;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
HOLT_TF_CACHE := rec();
HOLT_ENGINE_MODE := "clean";

t0 := Runtime();
resOff := HoltFPFSubgroupClassesOfProduct(P, shifted, offs, Npart);
tOff := (Runtime() - t0)/1000.0;
Print("ISO OFF: ", Length(resOff), " classes in ", tOff, "s\n\n");

# --- PART 2: run with iso-transport ENABLED ---
Print("=== ISO ON ===\n");
HOLT_DISABLE_ISO_TRANSPORT := false;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
HOLT_TF_CACHE := rec();

t0 := Runtime();
resOn := HoltFPFSubgroupClassesOfProduct(P, shifted, offs, Npart);
tOn := (Runtime() - t0)/1000.0;
Print("ISO ON: ", Length(resOn), " classes in ", tOn, "s\n\n");

# --- Diff ---
Print("=== DIFF ===\n");
# Which groups from resOff are missing in resOn?
missingSizes := [];
for H in resOff do
  found := false;
  for K in resOn do
    if Size(H) = Size(K) and
       RepresentativeAction(Npart, H, K) <> fail then
      found := true;
      break;
    fi;
  od;
  if not found then
    Add(missingSizes, Size(H));
    Print("  MISSING from ISO ON: |H| = ", Size(H), "\n");
    Print("    gens: ", GeneratorsOfGroup(H), "\n");
  fi;
od;

Print("\nMissing count: ", Length(missingSizes), "\n");
Print("Summary: ISO OFF = ", Length(resOff), ", ISO ON = ", Length(resOn),
      ", diff = ", Length(resOff) - Length(resOn), "\n");

LogTo();
QUIT;
