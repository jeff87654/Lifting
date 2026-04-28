LogTo("C:/Users/jeffr/Downloads/Lifting/rebuild_gens_3.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n=== Rebuilding [11, 2, 2, 2] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_50";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [11, 2, 2, 2]);
Print("  Got ", Length(_fpf), " classes (expected 56)\n");
if Length(_fpf) <> 56 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 56\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_11_2_2_2.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [7, 2, 2, 2, 2, 2] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_57";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [7, 2, 2, 2, 2, 2]);
Print("  Got ", Length(_fpf), " classes (expected 289)\n");
if Length(_fpf) <> 289 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 289\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_7_2_2_2_2_2.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [5, 4, 4, 4] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_142";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [5, 4, 4, 4]);
Print("  Got ", Length(_fpf), " classes (expected 25129)\n");
if Length(_fpf) <> 25129 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 25129\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_5_4_4_4.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [5, 3, 3, 3, 3] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_68";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [5, 3, 3, 3, 3]);
Print("  Got ", Length(_fpf), " classes (expected 481)\n");
if Length(_fpf) <> 481 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 481\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_5_3_3_3_3.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [3, 2, 2, 2, 2, 2, 2, 2] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_137";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [3, 2, 2, 2, 2, 2, 2, 2]);
Print("  Got ", Length(_fpf), " classes (expected 653)\n");
if Length(_fpf) <> 653 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 653\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_3_2_2_2_2_2_2_2.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

LogTo();
QUIT;