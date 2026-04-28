
LogTo("C:/Users/jeffr/Downloads/Lifting/tmp_profile_dedup_phases.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
LoadGroupsFromCombo := function(path, maxCount)
  local fileStr, lines, outFile, line, count;
  fileStr := StringFile(path);
  fileStr := ReplacedString(fileStr, "\\\n", "");
  fileStr := ReplacedString(fileStr, "\\\r\n", "");
  lines := SplitString(fileStr, "\n");
  outFile := "C:/Users/jeffr/Downloads/Lifting/tmp_profile_dedup_groups.g";
  PrintTo(outFile, "_PROFILE_GENS := [];;\n");
  count := 0;
  for line in lines do
    while Length(line) > 0 and (line[Length(line)] = '\r' or line[Length(line)] = '\n' or line[Length(line)] = ' ') do
      line := line{[1..Length(line)-1]};
    od;
    if Length(line) > 2 and line[1] = '[' then
      if maxCount = 0 or count < maxCount then
        AppendTo(outFile, "Add(_PROFILE_GENS, ", line, ");\n");
        count := count + 1;
      fi;
    fi;
  od;
  Read(outFile);
  return List(_PROFILE_GENS, g -> Group(g));
end;
BucketStats := function(sizes)
  local sorted, n, ge2, ge6, ge20, ge100, max;
  if Length(sizes) = 0 then return [0,0,0,0,0,0,0]; fi;
  sorted := SortedList(sizes);
  n := Length(sorted);
  ge2 := Number(sorted, x -> x >= 2);
  ge6 := Number(sorted, x -> x >= 6);
  ge20 := Number(sorted, x -> x >= 20);
  ge100 := Number(sorted, x -> x >= 100);
  max := sorted[n];
  return [n, max, ge2, ge6, ge20, ge100, Sum(sorted)];
end;
ProfileDedupPhases := function(groups, label)
  local t0, tCheap, tExp, buckets, key, H, sizes, bigKeys, subBuckets,
        subKey, expensiveCalls, subSizes, st, st2, orderSizes;
  Print("PROFILE ", label, " groups=", Length(groups), "\n");
  CURRENT_BLOCK_RANGES := [[1,5],[6,9],[10,13],[14,17]];
  t0 := Runtime();
  buckets := rec();
  for H in groups do
    key := _HoltShortHashOf(String(HoltCheapSubgroupInvariant(H)));
    if not IsBound(buckets.(key)) then buckets.(key) := []; fi;
    Add(buckets.(key), H);
  od;
  tCheap := (Runtime() - t0) / 1000.0;
  sizes := List(RecNames(buckets), k -> Length(buckets.(k)));
  st := BucketStats(sizes);
  Print("  cheap_time=", tCheap, "s buckets=", st[1], " max=", st[2],
        " ge2=", st[3], " ge6=", st[4], " ge20=", st[5], " ge100=", st[6], "\n");
  bigKeys := Filtered(RecNames(buckets), k -> Length(buckets.(k)) > _HOLT_RICH_BUCKET_THRESHOLD);
  Print("  rich_threshold=", _HOLT_RICH_BUCKET_THRESHOLD, " big_cheap_buckets=", Length(bigKeys), "\n");
  t0 := Runtime();
  subSizes := [];
  expensiveCalls := 0;
  orderSizes := [];
  for key in bigKeys do
    subBuckets := rec();
    for H in buckets.(key) do
      expensiveCalls := expensiveCalls + 1;
      Add(orderSizes, Size(H));
      subKey := _HoltShortHashOf(String(ExpensiveSubgroupInvariant(H)));
      if not IsBound(subBuckets.(subKey)) then subBuckets.(subKey) := []; fi;
      Add(subBuckets.(subKey), H);
    od;
    Append(subSizes, List(RecNames(subBuckets), sk -> Length(subBuckets.(sk))));
  od;
  tExp := (Runtime() - t0) / 1000.0;
  st2 := BucketStats(subSizes);
  Print("  expensive_time=", tExp, "s expensive_calls=", expensiveCalls,
        " subbuckets=", st2[1], " max=", st2[2], " ge2=", st2[3],
        " ge6=", st2[4], " ge20=", st2[5], " ge100=", st2[6], "\n");
  if Length(orderSizes) > 0 then
    Print("  expensive_order_stats min=", Minimum(orderSizes), " max=", Maximum(orderSizes),
          " avg=", Float(Sum(orderSizes))/Length(orderSizes), "\n");
  fi;
end;
path := "C:/Users/jeffr/Downloads/Lifting/parallel_s17_m6m7/[5,4,4,4]/[4,2]_[4,3]_[4,3]_[5,5].g";
groups200 := LoadGroupsFromCombo(path, 200);
ProfileDedupPhases(groups200, "first200");
groupsAll := LoadGroupsFromCombo(path, 0);
ProfileDedupPhases(groupsAll, "all");
LogTo();
QUIT;
