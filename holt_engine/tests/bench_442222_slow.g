LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/bench_442222_slow.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";

T1 := TransitiveGroup(4, 2);
T2 := ShiftGroup(TransitiveGroup(4, 3), 4);
T3 := ShiftGroup(TransitiveGroup(2, 1), 8);
T4 := ShiftGroup(TransitiveGroup(2, 1), 10);
T5 := ShiftGroup(TransitiveGroup(2, 1), 12);
P := Group(Concatenation(GeneratorsOfGroup(T1), GeneratorsOfGroup(T2),
                          GeneratorsOfGroup(T3), GeneratorsOfGroup(T4),
                          GeneratorsOfGroup(T5)));
shifted := [T1, T2, T3, T4, T5];
offsets := [0, 4, 8, 10, 12];
Npart := SymmetricGroup(14);
CURRENT_BLOCK_RANGES := [[1,4],[5,8],[9,10],[11,12],[13,14]];

Print("|P| = ", Size(P), " |Npart| = ", Size(Npart), "\n");

if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

_t0 := Runtime();
fpf := HoltFPFSubgroupClassesOfProduct(P, shifted, offsets, Npart);
_e := (Runtime() - _t0) / 1000.0;

Print("\n=== [4,4,2,2,2] slow combo = ", Length(fpf), " classes in ", _e, "s ===\n");
Print("Expected: 766 classes (from prior profile)\n");

LogTo();
QUIT;
