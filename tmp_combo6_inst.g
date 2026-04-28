
LogTo("C:/Users/jeffr/Downloads/Lifting/combo6_inst.log");

USE_GENERAL_AUT_HOM := true;
DIAG_GAH_VS_NSCR := false;
GENERAL_AUT_HOM_VERBOSE := true;

# Bypass cache save bug.
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
SaveFPFSubdirectCache := function() end;

# Force per-parent stdout flush by hooking inside the lifting code via
# a global progress counter.  We override at the layer level.
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

T5 := TransitiveGroup(5, 5);;
T2 := TransitiveGroup(2, 1);;
partition := [5, 5, 2, 2, 2, 2];;
factors := [T5, T5, T2, T2, T2, T2];;

shifted := [];
offsets := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offsets, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
N := BuildPerComboNormalizer(partition, factors, 18);

FPF_SUBDIRECT_CACHE := rec();

Print("\n[inst] |P|=", Size(P), " |N|=", Size(N), "\n\n");

t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

CURRENT_BLOCK_RANGES := [];
off := 0;
for k in [1..Length(partition)] do
    Add(CURRENT_BLOCK_RANGES, [off + 1, off + partition[k]]);
    off := off + partition[k];
od;
deduped := [];
byInv := rec();
for H in fpf do
    AddIfNotConjugate(N, H, deduped, byInv, ComputeSubgroupInvariant);
od;

Print("\n=== RESULT ===\n");
Print("[inst] Raw FPF: ", Length(fpf), "\n");
Print("[inst] Deduped: ", Length(deduped), " classes\n");
Print("[inst] Elapsed: ", Float(elapsed/1000), "s\n");
if Length(deduped) = 154 then
    Print("[inst] *** MATCH: bug fixed! ***\n");
else
    Print("[inst] *** count = ", Length(deduped), " (expected 154) ***\n");
fi;

LogTo();
QUIT;
