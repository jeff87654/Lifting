LogTo("C:/Users/jeffr/Downloads/Lifting/rebuild_gens_single.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n=== Starting rebuild of missing gens files ===\n");

_REBUILD_PARTITIONS := [
    [17], [15,2], [14,3], [11,2,2,2]
];

_REBUILD_CKPT_DIRS := [
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_47",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_48",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_49",
    "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_50"
];

_REBUILD_EXPECTED := [10, 232, 231, 56];

for _ri in [1..Length(_REBUILD_PARTITIONS)] do
    _part := _REBUILD_PARTITIONS[_ri];
    _ckptDir := _REBUILD_CKPT_DIRS[_ri];
    _exp := _REBUILD_EXPECTED[_ri];

    Print("\n--- Rebuilding ", _part, " ---\n");
    CHECKPOINT_DIR := _ckptDir;
    if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

    _fpf := FindFPFClassesForPartition(17, _part);
    Print("  Got ", Length(_fpf), " classes (expected ", _exp, ")\n");

    _partStr := JoinStringsWithSeparator(List(_part, String), "_");
    _genFile := Concatenation("C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_", _partStr, ".txt");
    PrintTo(_genFile, "");
    for _h_idx in [1..Length(_fpf)] do
        _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
        AppendTo(_genFile, String(_gens), "\n");
    od;
    Print("  Wrote ", Length(_fpf), " groups to gens file\n");
od;

Print("\n=== Batch 1 complete ===\n");
LogTo();
QUIT;
