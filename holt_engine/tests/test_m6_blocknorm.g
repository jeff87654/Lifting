LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/test_m6_blocknorm.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
Print("HOLT_ENGINE_MODE = ", HOLT_ENGINE_MODE, "\n");

# Slow combo: partition [4,4,2,2,2] with T(4,2) x T(4,3) x C_2^3.
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

# Inspect block-factored normalizer size.
blockNorm := _HoltBlockFactoredNormalizer(shifted, offsets, 14);
Print("|blockNorm| = ", Size(blockNorm), "  (vs |Npart|=", Size(Npart), ")\n");
Print("ratio Npart/blockNorm = ", Size(Npart) / Size(blockNorm), "\n");
Print("blockNorm subgroup of Npart? ", IsSubgroup(Npart, blockNorm), "\n");

if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

_t0 := Runtime();
fpf := HoltFPFSubgroupClassesOfProduct(P, shifted, offsets, Npart);
_elapsed := (Runtime() - _t0) / 1000.0;

Print("\nHoltFPF returned ", Length(fpf), " classes\n");
Print("Elapsed: ", _elapsed, "s\n");

# Correctness: previous run returned 766 classes in 6085s.
Print("\n=== M6 result: ", Length(fpf), " classes in ", _elapsed,
      "s (expected 766 from prior profile) ===\n");

LogTo();
QUIT;
