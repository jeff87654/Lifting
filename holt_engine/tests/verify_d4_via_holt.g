LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/verify_d4_via_holt.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

USE_HOLT_ENGINE := true;
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_DISABLE_DEDUP := true;
HOLT_ENGINE_MODE := "clean";  # bypass ALL legacy fast paths — no Goursat, no D_4^3

if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
if IsBound(HOLT_TF_CACHE) then HOLT_TF_CACHE := rec(); fi;

# [4,4,4,4,2] with 4x T(4,3) + T(2,1)
part := [4,4,4,4,2];
currentFactors := [TransitiveGroup(4,3), TransitiveGroup(4,3),
                   TransitiveGroup(4,3), TransitiveGroup(4,3),
                   TransitiveGroup(2,1)];

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
Npart := BuildPerComboNormalizer(part, currentFactors, 18);
CURRENT_BLOCK_RANGES := [[1,4],[5,8],[9,12],[13,16],[17,18]];

Print("Partition [4,4,4,4,2], combo [T(4,3)x4, T(2,1)]\n");
Print("|P|=", Size(P), ", |Npart|=", Size(Npart), "\n");

# Disk count
disk := fail;
f := "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[4,4,4,4,2]/[2,1]_[4,3]_[4,3]_[4,3]_[4,3].g";
if IsExistingFile(f) then
  fs := StringFile(f);
  for line in SplitString(fs, "\n") do
    if Length(line) >= 11 and line{[1..11]} = "# deduped: " then
      disk := Int(line{[12..Length(line)]});
      break;
    fi;
  od;
fi;
Print("Disk count (from Goursat/D_4^3 path): ", disk, "\n\n");

Print("Running HoltFPFSubgroupClassesOfProduct (HOLT_ENGINE_MODE=clean)...\n");
t0 := Runtime();
result := HoltFPFSubgroupClassesOfProduct(P, shifted, offs, Npart);
t := (Runtime() - t0)/1000.0;
Print("Holt clean count: ", Length(result), " in ", t, "s\n");
Print("Delta vs disk: ", Length(result) - disk, "\n");

LogTo();
QUIT;
