LogTo("C:/Users/jeffr/Downloads/Lifting/verify_6542.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Load the 80,076 groups from gens file
Print("Loading groups from gens file...\n");
_groups := [];
_f := InputTextFile("C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_6_5_4_2.txt");
_line := "";
_buf := "";
while not IsEndOfStream(_f) do
    _line := ReadLine(_f);
    if _line = fail then break; fi;
    # Lines may be continuation lines (ending with \)
    _line := Chomp(_line);
    if Length(_line) > 0 and _line[Length(_line)] = '\\' then
        _buf := Concatenation(_buf, _line{[1..Length(_line)-1]});
    else
        _buf := Concatenation(_buf, _line);
        if Length(_buf) > 2 then
            # Parse generator list
            _gens := EvalString(_buf);
            if _gens <> fail and IsList(_gens) and Length(_gens) > 0 then
                Add(_groups, Group(List(_gens, PermList)));
            fi;
        fi;
        _buf := "";
    fi;
    if Length(_groups) mod 10000 = 0 and _buf = "" then
        Print("  loaded ", Length(_groups), " groups\n");
    fi;
od;
CloseStream(_f);
Print("Loaded ", Length(_groups), " groups\n");

# Build full partition normalizer for [6,5,4,2]
Print("Building partition normalizer...\n");
N := BuildConjugacyTestGroup(17, [6,5,4,2]);
Print("|N| = ", Size(N), "\n");

# Compute invariants and bucket
Print("Computing invariants...\n");
_invFunc := CheapSubgroupInvariantFull;
_byInv := rec();
_invKeys := [];
for _i in [1..Length(_groups)] do
    _inv := _invFunc(_groups[_i]);
    _key := InvariantKey(_inv);
    Add(_invKeys, _key);
    if not IsBound(_byInv.(_key)) then
        _byInv.(_key) := [];
    fi;
    Add(_byInv.(_key), _i);
    if _i mod 10000 = 0 then
        Print("  invariants ", _i, "/", Length(_groups), "\n");
    fi;
od;

# Report bucket sizes
_bucketNames := RecNames(_byInv);
_sizes := List(_bucketNames, k -> Length(_byInv.(k)));
Sort(_sizes);
_sizes := Reversed(_sizes);
Print("\nBucket statistics:\n");
Print("  Total buckets: ", Length(_bucketNames), "\n");
Print("  Max bucket size: ", _sizes[1], "\n");
Print("  Buckets of size 1: ", Length(Filtered(_sizes, x -> x = 1)), "\n");
Print("  Buckets of size 2-5: ", Length(Filtered(_sizes, x -> x >= 2 and x <= 5)), "\n");
Print("  Buckets of size 6-10: ", Length(Filtered(_sizes, x -> x >= 6 and x <= 10)), "\n");
Print("  Buckets of size >10: ", Length(Filtered(_sizes, x -> x > 10)), "\n");
Print("  Top 20 bucket sizes: ", _sizes{[1..Minimum(20, Length(_sizes))]}, "\n");

# Pairwise conjugacy test in top buckets
Print("\n=== Conjugacy testing in largest buckets ===\n");
_totalChecked := 0;
_totalDupes := 0;
_bucketsToCheck := Filtered(_bucketNames, k -> Length(_byInv.(k)) >= 2);
# Sort by size descending
Sort(_bucketsToCheck, function(a,b) return Length(_byInv.(a)) > Length(_byInv.(b)); end);

# Check all buckets of size >= 2, but limit to first 200 buckets and max 50 per bucket
for _bIdx in [1..Minimum(200, Length(_bucketsToCheck))] do
    _key := _bucketsToCheck[_bIdx];
    _indices := _byInv.(_key);
    _n := Length(_indices);
    _dupes := 0;
    # For large buckets, sample
    if _n > 50 then
        _check := _indices{[1..50]};
    else
        _check := _indices;
    fi;
    for _i in [1..Length(_check)] do
        for _j in [_i+1..Length(_check)] do
            _totalChecked := _totalChecked + 1;
            if RepresentativeAction(N, _groups[_check[_i]], _groups[_check[_j]]) <> fail then
                _dupes := _dupes + 1;
                _totalDupes := _totalDupes + 1;
                Print("  DUPLICATE FOUND! bucket=", _key{[1..Minimum(60, Length(_key))]},
                      " i=", _check[_i], " j=", _check[_j], "\n");
            fi;
        od;
    od;
    if _bIdx mod 20 = 0 then
        Print("  checked ", _bIdx, "/", Minimum(200, Length(_bucketsToCheck)),
              " buckets, ", _totalChecked, " pairs, ", _totalDupes, " dupes\n");
    fi;
od;

Print("\n=== RESULT ===\n");
Print("Total pairs checked: ", _totalChecked, "\n");
Print("Duplicates found: ", _totalDupes, "\n");
if _totalDupes = 0 then
    Print("No duplicates found - count of 80076 appears correct.\n");
else
    Print("WARNING: ", _totalDupes, " duplicate pairs found!\n");
fi;

LogTo();
QUIT;
