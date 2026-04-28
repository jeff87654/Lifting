
LogTo("C:/Users/jeffr/Downloads/Lifting/s2_s10_with_fix.log");

USE_GENERAL_AUT_HOM := true;
DIAG_GAH_VS_NSCR := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear caches for clean run.
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Bypass pre-existing SaveFPFSubdirectCache bug (MovedPoints error) — not
# related to the GAH fix.  We just want S_n counts.
SaveFPFSubdirectCache := function() end;

Print("\n[s2-10] Starting S2-S10 with USE_GENERAL_AUT_HOM=true (with FIX)\n");
t0 := Runtime();
total := 0;
for n in [2..10] do
    cnt := CountAllConjugacyClassesFast(n);
    total := total + cnt;
    Print("[s2-10] S", n, " = ", cnt, "\n");
od;
elapsed := Runtime() - t0;

Print("\n=== S2-S10 RESULT ===\n");
Print("[s2-10] Total: ", total, " (expected 1593)\n");
Print("[s2-10] Elapsed: ", Float(elapsed/1000), "s\n");
if total = 1593 then
    Print("[s2-10] *** PASS: regression OK ***\n");
else
    Print("[s2-10] *** FAIL: total = ", total, " not 1593 ***\n");
fi;

LogTo();
QUIT;
