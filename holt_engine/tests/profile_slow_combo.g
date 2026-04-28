LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/profile_slow_combo.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
Print("HOLT_ENGINE_MODE = ", HOLT_ENGINE_MODE, "\n");

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

Print("|P| = ", Size(P), "  |Npart| = ", Size(Npart), "\n");

if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

ProfileGlobalFunctions(true);
ProfileOperationsAndMethods(true);

_START := Runtime();
_last := _START;
_tick := function(label)
  Print("  [T+", (Runtime() - _START)/1000.0, "s, +",
        (Runtime() - _last)/1000.0, "s] ", label, "\n");
  _last := Runtime();
end;

_tick("starting HoltFPFSubgroupClassesOfProduct");
fpf := HoltFPFSubgroupClassesOfProduct(P, shifted, offsets, Npart);
_tick(Concatenation("HoltFPF returned ", String(Length(fpf)), " classes"));

Print("\nTotal elapsed: ", (Runtime() - _START)/1000.0, "s\n");

Print("\n=== Profile: DisplayProfile() ===\n");
DisplayProfile();

LogTo();
QUIT;
