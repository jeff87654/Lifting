LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/verify_162_combos.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Verify several [16,2] combos by brute-force CCS + FPF filter + Npart dedup.
# For each T(16,k), compare disk value to true count.

# Read disk combo file's # deduped value.
_DiskDeduped := function(partName, comboFile)
  local path, fileStr, lines, line;
  path := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_s18/",
                        partName, "/", comboFile);
  if not IsExistingFile(path) then return fail; fi;
  fileStr := StringFile(path);
  lines := SplitString(fileStr, "\n");
  for line in lines do
    if Length(line) >= 11 and line{[1..11]} = "# deduped: " then
      return Int(line{[12..Length(line)]});
    fi;
  od;
  return fail;
end;

# Compute true FPF class count via CCS.
_BruteForce162 := function(k)
  local T16, shifted, offs, P, ccs, fpf, cc, H, partN, reps, r, found;
  T16 := TransitiveGroup(16, k);
  shifted := [T16, ShiftGroup(TransitiveGroup(2,1), 16)];
  offs := [0, 16];
  P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
  SetSize(P, Product(List(shifted, Size)));
  if Size(P) > 50000 then
    Print("  T(16,", k, ") |P|=", Size(P), " - too big, skipping\n");
    return fail;
  fi;
  ccs := ConjugacyClassesSubgroups(P);
  fpf := [];
  for cc in ccs do
    H := Representative(cc);
    if IsFPFSubdirect(H, shifted, offs) then
      Add(fpf, H);
    fi;
  od;
  # Dedup under partition normalizer
  partN := BuildPerComboNormalizer([16,2], [T16, TransitiveGroup(2,1)], 18);
  reps := [];
  for H in fpf do
    found := false;
    for r in reps do
      if Size(H) = Size(r) and RepresentativeAction(partN, H, r) <> fail then
        found := true; break;
      fi;
    od;
    if not found then Add(reps, H); fi;
  od;
  return Length(reps);
end;

_ComboFileName := function(k)
  # Combo file is [2,1]_[16,k].g since factors sort ascending in filename
  return Concatenation("[2,1]_[16,", String(k), "].g");
end;

Print("Verifying [16,2] combos for k = 1..20\n");
Print(_ComboFileName(1), " etc.\n\n");
Print(" k | |T(16,k)| |P|     disk  brute  delta\n");
Print("---+----------+-------+------+------+-----\n");
for k in [1..20] do
  fname := _ComboFileName(k);
  disk := _DiskDeduped("[16,2]", fname);
  sz := Size(TransitiveGroup(16, k));
  bruteN := _BruteForce162(k);
  if bruteN = fail then
    Print("  skip k=", k, "\n");
  else
    delta := bruteN - disk;
    mark := "";
    if delta <> 0 then mark := "  <--- MISMATCH"; fi;
    Print(String(k,3), " | ", String(sz,8), " | ",
          String(sz*2,5), " | ", String(disk,4), " | ", String(bruteN,4),
          " | ", String(delta, 4), mark, "\n");
  fi;
od;

LogTo();
QUIT;
