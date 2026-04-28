LogTo("C:/Users/jeffr/Downloads/Lifting/rebuild_gens_1.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n=== Rebuilding [15, 2] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_48";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [15, 2]);
Print("  Got ", Length(_fpf), " classes (expected 232)\n");
if Length(_fpf) <> 232 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 232\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_15_2.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [7, 5, 5] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_55";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [7, 5, 5]);
Print("  Got ", Length(_fpf), " classes (expected 298)\n");
if Length(_fpf) <> 298 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 298\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_7_5_5.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [6, 5, 2, 2, 2] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_96";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [6, 5, 2, 2, 2]);
Print("  Got ", Length(_fpf), " classes (expected 5959)\n");
if Length(_fpf) <> 5959 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 5959\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_6_5_2_2_2.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [5, 4, 3, 3, 2] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_103";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [5, 4, 3, 3, 2]);
Print("  Got ", Length(_fpf), " classes (expected 5607)\n");
if Length(_fpf) <> 5607 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 5607\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_5_4_3_3_2.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

Print("\n=== Rebuilding [4, 3, 2, 2, 2, 2, 2] ===\n");
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/checkpoints/worker_136";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
_fpf := FindFPFClassesForPartition(17, [4, 3, 2, 2, 2, 2, 2]);
Print("  Got ", Length(_fpf), " classes (expected 9086)\n");
if Length(_fpf) <> 9086 then
    Print("  WARNING: Count mismatch! Got ", Length(_fpf), " expected 9086\n");
fi;
_genFile := "C:/Users/jeffr/Downloads/Lifting/parallel_s17/gens/gens_4_3_2_2_2_2_2.txt";
PrintTo(_genFile, "");
for _h_idx in [1..Length(_fpf)] do
    _gens := List(GeneratorsOfGroup(_fpf[_h_idx]), g -> ListPerm(g, 17));
    AppendTo(_genFile, String(_gens), "\n");
od;
Print("  Wrote ", Length(_fpf), " groups to ", _genFile, "\n");

LogTo();
QUIT;