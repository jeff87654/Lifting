
LogTo("C:/Users/jeffr/Downloads/Lifting/verify_154.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/tmp_154_groups.g");

T5 := TransitiveGroup(5, 5);;
T2 := TransitiveGroup(2, 1);;
partition := [5, 5, 2, 2, 2, 2];;
factors := [T5, T5, T2, T2, T2, T2];;
N := BuildPerComboNormalizer(partition, factors, 18);
Print("[verify] |N| = ", Size(N), "\n");
Print("[verify] loaded ", Length(PREBUG_GROUPS), " prebug groups\n");

inv := function(H)
    return [Size(H), AbelianInvariants(H),
            SortedList(List(Orbits(H, [1..18]), Length))];
end;

byInv := rec();
for i in [1..Length(PREBUG_GROUPS)] do
    k := String(inv(PREBUG_GROUPS[i]));
    if not IsBound(byInv.(k)) then byInv.(k) := []; fi;
    Add(byInv.(k), i);
od;
Print("[verify] ", Length(RecNames(byInv)), " distinct invariant buckets\n");

t0 := Runtime();
dups := [];
n_ra := 0;
for k in RecNames(byInv) do
    bucket := byInv.(k);
    if Length(bucket) <= 1 then continue; fi;
    for i in [1..Length(bucket)-1] do
        for j in [i+1..Length(bucket)] do
            n_ra := n_ra + 1;
            r := RepresentativeAction(N,
                                      PREBUG_GROUPS[bucket[i]],
                                      PREBUG_GROUPS[bucket[j]]);
            if r <> fail then
                Add(dups, [bucket[i], bucket[j]]);
                Print("[verify] DUPLICATE: ", bucket[i], " ~ ", bucket[j],
                      " (bucket size ", Length(bucket), ")\n");
            fi;
        od;
    od;
od;
elapsed := Runtime() - t0;

Print("\n=== VERIFY RESULT ===\n");
Print("[verify] groups loaded: ", Length(PREBUG_GROUPS), "\n");
Print("[verify] RA calls: ", n_ra, "\n");
Print("[verify] duplicates found: ", Length(dups), "\n");
Print("[verify] elapsed: ", Float(elapsed/1000), "s\n");
if Length(dups) = 0 then
    Print("[verify] CONFIRMED: 154 prebug groups are pairwise non-N-conjugate.\n");
else
    Print("[verify] WARNING: 154 prebug count is over by ", Length(dups), "\n");
fi;

LogTo();
QUIT;
