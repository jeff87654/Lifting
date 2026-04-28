LogTo("C:/Users/jeffr/Downloads/Lifting/investigate_333333.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_DISABLE_DEDUP := true;
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Test [3,3,3,3,3,3]/[T(3,1)^6] = (C_3)^6 in S_18
part := [3,3,3,3,3,3];
factors := List([1..6], i -> TransitiveGroup(3,1));
shifted := []; offs := []; off := 0;
for f in factors do
    Add(offs, off);
    Add(shifted, ShiftGroup(f, off));
    off := off + NrMovedPoints(f);
od;
P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
SetSize(P, Product(List(shifted, Size)));
Npart := BuildPerComboNormalizer(part, factors, 18);
CURRENT_BLOCK_RANGES := [[1,3],[4,6],[7,9],[10,12],[13,15],[16,18]];

Print("|P| = ", Size(P), " (expect 729 = 3^6)\n");
Print("|Npart| = ", Size(Npart), "\n");
Print("IsAbelian(P): ", IsAbelian(P), "\n");
Print("\n");

# 1. Count F_3-subspace subdirects analytically via direct enumeration
Print("\n=== Method 1: Direct enumeration of subdirect F_3 subspaces ===\n");
t0 := Runtime();
all_subs := AllSubgroups(P);
Print("Total subgroups of P=(C_3)^6: ", Length(all_subs), " (", (Runtime()-t0)/1000.0, "s)\n");
subdirect := Filtered(all_subs, H -> IsFPFSubdirect(H, shifted, offs));
Print("Subdirect (covers each C_3): ", Length(subdirect), "\n");

# 2. Dedup under Npart by RA
deduped := [];
t0 := Runtime();
for H in subdirect do
    found := false;
    for K in deduped do
        if Size(K) = Size(H) and
           RepresentativeAction(Npart, H, K) <> fail then
            found := true; break;
        fi;
    od;
    if not found then Add(deduped, H); fi;
od;
Print("After Npart-dedup: ", Length(deduped), " (", (Runtime()-t0)/1000.0, "s)\n");
Print("Disk count for this combo: 49\n");
Print("Delta vs disk: ", Length(deduped) - 49, "\n");

# 3. What does FindFPFClassesByLifting return?
Print("\n=== Method 2: FindFPFClassesByLifting (raw) ===\n");
FPF_SUBDIRECT_CACHE := rec();
t0 := Runtime();
raw := FindFPFClassesByLifting(P, shifted, offs, Npart);
Print("FindFPFClassesByLifting raw count: ", Length(raw), " (", (Runtime()-t0)/1000.0, "s)\n");

LogTo();
QUIT;
