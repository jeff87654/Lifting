LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/verify_162_bigger.log");

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

_BruteForce162 := function(k, maxP)
  local T16, shifted, offs, P, ccs, fpf, cc, H, partN, reps, r, found, sz;
  T16 := TransitiveGroup(16, k);
  sz := Size(T16);
  if 2*sz > maxP then return [fail, sz]; fi;
  shifted := [T16, ShiftGroup(TransitiveGroup(2,1), 16)];
  offs := [0, 16];
  P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
  SetSize(P, Product(List(shifted, Size)));
  ccs := ConjugacyClassesSubgroups(P);
  fpf := [];
  for cc in ccs do
    H := Representative(cc);
    if IsFPFSubdirect(H, shifted, offs) then
      Add(fpf, H);
    fi;
  od;
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
  return [Length(reps), sz];
end;

Print(" k    |T(16,k)| |P|      disk  brute  delta\n");
Print("------+---------+--------+------+------+-----\n");

# Sample a range of k values, skip if |P| > 8000 (CCS gets slow)
ks := [30, 50, 100, 150, 200, 300, 400, 500, 700, 900, 1000, 1200, 1500, 1700, 1800, 1900, 1940, 1950];
for k in ks do
  r := _BruteForce162(k, 8000);
  sz := r[2];
  if r[1] = fail then
    Print(String(k,5), " | ", String(sz,8), " | ", String(sz*2,7), " | SKIP (too big)\n");
  else
    fname := Concatenation("[2,1]_[16,", String(k), "].g");
    disk := _DiskDeduped("[16,2]", fname);
    delta := r[1] - disk;
    mark := "";
    if delta <> 0 then mark := "  <--- MISMATCH"; fi;
    Print(String(k,5), " | ", String(sz,8), " | ", String(sz*2,7), " | ",
          String(disk,4), " | ", String(r[1],4), " | ", String(delta, 4), mark, "\n");
  fi;
od;

LogTo();
QUIT;
