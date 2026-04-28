LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/verify_d4_cubed.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

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

# Verify a combo via ConjugacyClassesSubgroups(P) + FPF filter + Npart dedup.
_Verify := function(part, factors_kidx, partName, comboFile)
  local shifted, offs, off, k, P, factors, ccs, fpf, cc, H, partN, reps, r, found, d, i;
  # Build factors from partition + indices
  factors := [];
  for i in [1..Length(part)] do
    Add(factors, TransitiveGroup(part[i], factors_kidx[i]));
  od;

  shifted := [];
  offs := [];
  off := 0;
  for k in [1..Length(factors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
  od;
  P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
  SetSize(P, Product(List(shifted, Size)));
  if Size(P) > 20000 then
    Print("  |P|=", Size(P), " - too big, skipping\n");
    return fail;
  fi;
  Print("  |P|=", Size(P), ", running CCS...\n");
  ccs := ConjugacyClassesSubgroups(P);
  Print("  |ccs|=", Length(ccs), "\n");
  fpf := [];
  for cc in ccs do
    H := Representative(cc);
    if IsFPFSubdirect(H, shifted, offs) then
      Add(fpf, H);
    fi;
  od;
  Print("  fpf-filtered count: ", Length(fpf), "\n");
  partN := BuildPerComboNormalizer(part, factors, Sum(part));
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
  Print("  brute-force (Npart-deduped): ", Length(reps), "\n");
  disk := _DiskDeduped(partName, comboFile);
  Print("  disk file count: ", disk, "\n");
  if disk = Length(reps) then
    Print("  MATCH\n");
  else
    Print("  MISMATCH delta = ", Length(reps) - disk, "\n");
  fi;
  return Length(reps);
end;

# Test D_4^3 combos: [4,4,4,4,2] with 4×T(4,3) + T(2,1)
Print("\n=== D_4^4 combo in [4,4,4,4,2] ===\n");
_Verify([4,4,4,4,2], [3,3,3,3,1], "[4,4,4,4,2]", "[2,1]_[4,3]_[4,3]_[4,3]_[4,3].g");

# Test: [6,4,4,4] with D_4^3 + T(6,1)
Print("\n=== D_4^3 + T(6,1) in [6,4,4,4] ===\n");
_Verify([6,4,4,4], [1,3,3,3], "[6,4,4,4]", "[4,3]_[4,3]_[4,3]_[6,1].g");

# Test: [4,4,4,3,3] with 3×T(4,3) + 2×T(3,1)
Print("\n=== D_4^3 + 2xS_3 in [4,4,4,3,3] ===\n");
_Verify([4,4,4,3,3], [1,1,3,3,3], "[4,4,4,3,3]", "[3,1]_[3,1]_[4,3]_[4,3]_[4,3].g");

LogTo();
QUIT;
