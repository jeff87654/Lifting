LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/compare_s17_slow_combo.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

USE_HOLT_ENGINE := true;
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_ENGINE_MODE := "clean";

if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
if IsBound(HOLT_TF_CACHE) then HOLT_TF_CACHE := rec(); fi;

# Match legacy's factor ordering: descending block size (partition [5,5,5,2]).
# Blocks: [1-5], [6-10], [11-15], [16-17]; T(5,5) in first three, T(2,1) in last.
f2 := TransitiveGroup(5,5);
f3 := TransitiveGroup(5,5);
f4 := TransitiveGroup(5,5);
f1 := TransitiveGroup(2,1);
currentFactors := [f2, f3, f4, f1];
partition := [5,5,5,2];

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
Npart := BuildPerComboNormalizer(partition, currentFactors, 17);
CURRENT_BLOCK_RANGES := [[1,5],[6,10],[11,15],[16,17]];

# --- Run Holt ---
Print("Running Holt clean pipeline...\n");
holtGroups := HoltFPFSubgroupClassesOfProduct(P, shifted, offs, Npart);
Print("Holt: ", Length(holtGroups), " classes\n\n");

# --- Load legacy's classes via READ of wrapper file ---
# The combo file has lines like: [(1,2,3,4,5),(1,2),...]
# Wrap into a GAP script that pushes each list into a global variable.
legacyFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17_m6m7/[5,5,5,2]/[2,1]_[5,5]_[5,5]_[5,5].g";
wrapperFile := "C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/_legacy_wrapper.g";
fileStr := StringFile(legacyFile);
# GAP's AppendTo wraps long lines with `\` + newline.
# Strip all `\` followed by newline (continuation) before splitting.
fileStr := ReplacedString(fileStr, "\\\n", "");
fileStr := ReplacedString(fileStr, "\\\r\n", "");
lines := SplitString(fileStr, "\n");
PrintTo(wrapperFile, "_LEGACY_GENS := [];;\n");
for line in lines do
  while Length(line) > 0 and (line[Length(line)] = '\r' or
        line[Length(line)] = '\n' or line[Length(line)] = ' ') do
    line := line{[1..Length(line)-1]};
  od;
  if Length(line) > 2 and line[1] = '[' then
    AppendTo(wrapperFile, "Add(_LEGACY_GENS, ", line, ");\n");
  fi;
od;
Read(wrapperFile);
legacyGroups := List(_LEGACY_GENS, g -> Group(g));
Print("Legacy: ", Length(legacyGroups), " classes from disk\n\n");

# --- For each legacy group, find its match in Holt set under Npart-conjugacy ---
Print("Checking each legacy rep against Holt's set under Npart-conjugacy:\n");
matched := 0;
matchIdxs := [];
unmatchedLegacy := [];
for i in [1..Length(legacyGroups)] do
  L := legacyGroups[i];
  found := false;
  for j in [1..Length(holtGroups)] do
    if Size(L) = Size(holtGroups[j]) and
       RepresentativeAction(Npart, L, holtGroups[j]) <> fail then
      matched := matched + 1;
      Add(matchIdxs, j);
      found := true;
      break;
    fi;
  od;
  if not found then
    Add(unmatchedLegacy, [i, Size(L)]);
  fi;
od;
Print("  Legacy classes matched in Holt: ", matched, " / ", Length(legacyGroups), "\n");
if Length(unmatchedLegacy) > 0 then
  Print("  UNMATCHED (legacy not found in Holt): ", unmatchedLegacy, "\n");
fi;

# --- Which of Holt's 46 are NOT covered by legacy's 20? ---
holtUnique := Difference([1..Length(holtGroups)], Set(matchIdxs));
Print("\n  Holt classes NOT matched to any legacy rep: ", Length(holtUnique), "\n");
if Length(holtUnique) > 0 then
  Print("  Sizes of extra Holt classes: ",
        Collected(List(holtUnique, j -> Size(holtGroups[j]))), "\n");
fi;

# --- Verdict ---
Print("\n=== VERDICT ===\n");
if Length(unmatchedLegacy) = 0 and Length(holtUnique) = 0 then
  Print("Holt = Legacy (exact match)\n");
elif Length(unmatchedLegacy) = 0 and Length(holtUnique) > 0 then
  Print("Holt STRICTLY CONTAINS Legacy -- legacy under-counts by ",
        Length(holtUnique), "\n");
elif Length(unmatchedLegacy) > 0 and Length(holtUnique) = 0 then
  Print("Legacy STRICTLY CONTAINS Holt -- Holt under-counts by ",
        Length(unmatchedLegacy), "\n");
else
  Print("MIXED DIFFERENCE: each has classes the other doesn't\n");
fi;

LogTo();
QUIT;
