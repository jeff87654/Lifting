LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/diff_844_buggy_vs_correct.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

# Build the same P for conjugacy checks
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
Npart := BuildPerComboNormalizer(partition, currentFactors, 16);
Print("|Npart| = ", Size(Npart), "\n");

# Parse combo file groups
ParseGroups := function(filepath)
  local fileStr, lines, groups, line, perms, wrapperFile;
  fileStr := StringFile(filepath);
  fileStr := ReplacedString(fileStr, "\\\n", "");
  fileStr := ReplacedString(fileStr, "\\\r\n", "");
  lines := SplitString(fileStr, "\n");
  wrapperFile := "C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/_diff_wrapper.g";
  PrintTo(wrapperFile, "_WRAP := [];;\n");
  for line in lines do
    while Length(line) > 0 and (line[Length(line)] = '\r' or
          line[Length(line)] = '\n' or line[Length(line)] = ' ') do
      line := line{[1..Length(line)-1]};
    od;
    if Length(line) > 2 and line[1] = '[' then
      AppendTo(wrapperFile, "Add(_WRAP, ", line, ");\n");
    fi;
  od;
  Read(wrapperFile);
  return List(_WRAP, g -> Group(g));
end;

correctGroups := ParseGroups("C:/Users/jeffr/Downloads/Lifting/parallel_s16_m6m7/[8,4,4]/[4,1]_[4,2]_[8,17].g");
buggyGroups := ParseGroups("C:/Users/jeffr/Downloads/Lifting/parallel_s16_m6m7/[8,4,4]_buggy_iso/[4,1]_[4,2]_[8,17].g");

Print("correct = ", Length(correctGroups), " classes\n");
Print("buggy = ", Length(buggyGroups), " classes\n\n");

# For each correct class, find it in buggy
Print("=== Which correct classes are MISSING from buggy? ===\n");
missing := [];
for i in [1..Length(correctGroups)] do
  C := correctGroups[i];
  found := false;
  for B in buggyGroups do
    if Size(C) = Size(B) and
       RepresentativeAction(Npart, C, B) <> fail then
      found := true;
      break;
    fi;
  od;
  if not found then
    Add(missing, i);
    Print("  MISSING correct[", i, "] |G|=", Size(C),
          " structure=", StructureDescription(C), "\n");
    Print("    gens: ", GeneratorsOfGroup(C), "\n");
  fi;
od;
Print("Missing: ", Length(missing), " classes\n\n");

# Reverse check: classes in buggy but not correct
Print("=== Which buggy classes are NOT in correct? ===\n");
extra := [];
for i in [1..Length(buggyGroups)] do
  B := buggyGroups[i];
  found := false;
  for C in correctGroups do
    if Size(B) = Size(C) and
       RepresentativeAction(Npart, B, C) <> fail then
      found := true;
      break;
    fi;
  od;
  if not found then
    Add(extra, i);
    Print("  EXTRA buggy[", i, "] |G|=", Size(B),
          " structure=", StructureDescription(B), "\n");
  fi;
od;
Print("Extra: ", Length(extra), " classes\n");

LogTo();
QUIT;
