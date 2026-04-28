LogTo("C:/Users/jeffr/Downloads/Lifting/rebuild_gens_v2.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n=== Rebuilding missing gens files from checkpoints (v2) ===\n");
Print("Strategy: Load .g only, full dedup, write gens\n\n");

_PARTITIONS := [
    [17], [15,2], [14,3], [11,2,2,2], [9,5,3], [7,5,5],
    [7,4,4,2], [7,2,2,2,2,2], [6,6,5], [6,5,2,2,2],
    [6,3,2,2,2,2], [5,4,3,3,2], [5,3,3,3,3],
    [5,2,2,2,2,2,2], [4,3,2,2,2,2,2], [3,3,3,3,3,2],
    [3,2,2,2,2,2,2,2], [5,4,2,2,2,2]
];
# Large partitions done separately: [5,4,4,4]=25129, [5,4,4,2,2]=28310

_CKPT_DIRS := [
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_47",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_48",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_49",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_50",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_158",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_55",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_104",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_57",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_146",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_96",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_95",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_103",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_68",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_90",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_136",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_79",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_137",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_92"
];

_EXPECTED := [10, 232, 231, 56, 1449, 298, 5092, 289, 7251, 5959,
              8070, 5607, 481, 681, 9086, 424, 653, 6956];

for _ri in [1..Length(_PARTITIONS)] do
    _part := _PARTITIONS[_ri];
    _ckptDir := _CKPT_DIRS[_ri];
    _exp := _EXPECTED[_ri];
    _partStr := JoinStringsWithSeparator(List(_part, String), "_");

    Print("\n=== Rebuilding ", _part, " (expected ", _exp, ") ===\n");

    # Load ONLY the .g file (not .log to avoid overlap)
    _gFile := Concatenation(_ckptDir, "/ckpt_17_", _partStr, ".g");
    _CKPT_COMPLETED_KEYS := [];
    _CKPT_ALL_FPF_GENS := [];
    _CKPT_TOTAL_CANDIDATES := 0;
    _CKPT_ADDED_COUNT := 0;
    _CKPT_INV_KEYS := fail;
    Read(_gFile);

    _rawGens := _CKPT_ALL_FPF_GENS;
    Print("  Loaded ", Length(_rawGens), " generator sets from .g\n");
    Unbind(_CKPT_COMPLETED_KEYS);
    Unbind(_CKPT_ALL_FPF_GENS);
    Unbind(_CKPT_TOTAL_CANDIDATES);
    Unbind(_CKPT_ADDED_COUNT);
    Unbind(_CKPT_INV_KEYS);

    # Rebuild groups
    _groups := [];
    for _gi in [1..Length(_rawGens)] do
        if Length(_rawGens[_gi]) > 0 then
            Add(_groups, Group(_rawGens[_gi]));
        else
            Add(_groups, Group(()));
        fi;
    od;
    Print("  Built ", Length(_groups), " groups\n");
    Unbind(_rawGens);

    # Build partition normalizer for dedup
    _N := BuildConjugacyTestGroup(17, _part);
    Print("  |N| = ", Size(_N), "\n");

    # Compute invariants and bucket
    _invFunc := CheapSubgroupInvariantFull;
    _byInv := rec();
    for _gi in [1..Length(_groups)] do
        _inv := _invFunc(_groups[_gi]);
        _key := InvariantKey(_inv);
        if not IsBound(_byInv.(_key)) then
            _byInv.(_key) := [];
        fi;
        Add(_byInv.(_key), _gi);
    od;

    # Dedup within each bucket using RepresentativeAction(N, ...)
    _keep := BlistList([1..Length(_groups)], [1..Length(_groups)]);
    _dupes := 0;
    _bucketNames := RecNames(_byInv);
    for _bk in _bucketNames do
        _indices := _byInv.(_bk);
        if Length(_indices) <= 1 then continue; fi;
        for _i in [1..Length(_indices)] do
            if not _keep[_indices[_i]] then continue; fi;
            for _j in [_i+1..Length(_indices)] do
                if not _keep[_indices[_j]] then continue; fi;
                if RepresentativeAction(_N, _groups[_indices[_i]],
                                        _groups[_indices[_j]]) <> fail then
                    _keep[_indices[_j]] := false;
                    _dupes := _dupes + 1;
                fi;
            od;
        od;
    od;

    _deduped := Filtered([1..Length(_groups)], i -> _keep[i]);
    Print("  Dedup: ", Length(_groups), " -> ", Length(_deduped),
          " (", _dupes, " duplicates removed)\n");

    if Length(_deduped) <> _exp then
        Print("  WARNING: Got ", Length(_deduped), " expected ", _exp, "!\n");
    fi;

    # Write gens file
    _genFile := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_",
                              _partStr, ".txt");
    PrintTo(_genFile, "");
    for _gi in _deduped do
        _gens := List(GeneratorsOfGroup(_groups[_gi]), g -> ListPerm(g, 17));
        AppendTo(_genFile, String(_gens), "\n");
    od;
    Print("  Wrote ", Length(_deduped), " groups to ", _genFile, "\n");
od;

Print("\n=== All partitions processed ===\n");
LogTo();
QUIT;
