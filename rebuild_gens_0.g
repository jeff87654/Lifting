LogTo("C:/Users/jeffr/Downloads/Lifting/rebuild_gens_0.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n=== Rebuilding [17] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_47";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [17]);
Print("  Got ", Length(_fpf), " classes (expected 10)\n");
if Length(_fpf) <> 10 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 10\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_17.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [9, 5, 3] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_158";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [9, 5, 3]);
Print("  Got ", Length(_fpf), " classes (expected 1449)\n");
if Length(_fpf) <> 1449 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 1449\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_9_5_3.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [6, 6, 5] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_146";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [6, 6, 5]);
Print("  Got ", Length(_fpf), " classes (expected 7251)\n");
if Length(_fpf) <> 7251 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 7251\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_6_6_5.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [5, 4, 4, 2, 2] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_140";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [5, 4, 4, 2, 2]);
Print("  Got ", Length(_fpf), " classes (expected 28310)\n");
if Length(_fpf) <> 28310 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 28310\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_5_4_4_2_2.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [5, 2, 2, 2, 2, 2, 2] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_90";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [5, 2, 2, 2, 2, 2, 2]);
Print("  Got ", Length(_fpf), " classes (expected 681)\n");
if Length(_fpf) <> 681 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 681\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_5_2_2_2_2_2_2.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

LogTo();
QUIT;