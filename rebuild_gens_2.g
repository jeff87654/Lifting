LogTo("C:/Users/jeffr/Downloads/Lifting/rebuild_gens_2.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n=== Rebuilding [14, 3] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_49";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [14, 3]);
Print("  Got ", Length(_fpf), " classes (expected 231)\n");
if Length(_fpf) <> 231 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 231\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_14_3.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [7, 4, 4, 2] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_104";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [7, 4, 4, 2]);
Print("  Got ", Length(_fpf), " classes (expected 5092)\n");
if Length(_fpf) <> 5092 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 5092\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_7_4_4_2.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [6, 3, 2, 2, 2, 2] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_95";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [6, 3, 2, 2, 2, 2]);
Print("  Got ", Length(_fpf), " classes (expected 8070)\n");
if Length(_fpf) <> 8070 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 8070\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_6_3_2_2_2_2.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [5, 4, 2, 2, 2, 2] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_92";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [5, 4, 2, 2, 2, 2]);
Print("  Got ", Length(_fpf), " classes (expected 6956)\n");
if Length(_fpf) <> 6956 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 6956\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_5_4_2_2_2_2.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [3, 3, 3, 3, 3, 2] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_79";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [3, 3, 3, 3, 3, 2]);
Print("  Got ", Length(_fpf), " classes (expected 424)\n");
if Length(_fpf) <> 424 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 424\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_3_3_3_3_3_2.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

LogTo();
QUIT;