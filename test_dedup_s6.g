LogTo("C:/Users/jeffr/Downloads/Lifting/test_dedup_s6.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_DISABLE_DEDUP := true;
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# D_4^3 × S_6 = [6,4,4,4] / [T(6,16), T(4,3)^3]
part := [6,4,4,4];
factors := [TransitiveGroup(6,16), TransitiveGroup(4,3),
            TransitiveGroup(4,3), TransitiveGroup(4,3)];
shifted := []; offs := []; off := 0;
for f in factors do
    Add(offs, off);
    Add(shifted, ShiftGroup(f, off));
    off := off + NrMovedPoints(f);
od;
P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
SetSize(P, Product(List(shifted, Size)));
Npart := BuildPerComboNormalizer(part, factors, 18);
CURRENT_BLOCK_RANGES := [[1,6],[7,10],[11,14],[15,18]];

FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
raw := FindFPFClassesByLifting(P, shifted, offs, Npart);
Print("\n1. RAW: ", Length(raw), " in ", (Runtime()-t0)/1000.0, "s\n");

# Explicit dedup
deduped := []; t0 := Runtime();
for H in raw do
    found := false;
    for K in deduped do
        if Size(K) = Size(H) and
           RepresentativeAction(Npart, H, K) <> fail then
            found := true; break;
        fi;
    od;
    if not found then Add(deduped, H); fi;
od;
Print("2. After explicit Npart-dedup: ", Length(deduped), " in ", (Runtime()-t0)/1000.0, "s\n");
LogTo();
QUIT;
