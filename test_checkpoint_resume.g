
LogTo("C:/Users/jeffr/Downloads/Lifting/test_checkpoint_resume.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Enable checkpointing (existing files from previous run)
CHECKPOINT_DIR := "C:/Users/jeffr/Downloads/Lifting/checkpoints";

# Clear caches but DON'T clear checkpoint files
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Run S1-S8 (S8 has interesting partitions with checkpoint files)
expected := [1, 2, 4, 11, 19, 56, 96, 296];
allPass := true;

for n in [1..8] do
    t0 := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - t0) / 1000.0;
    if result = expected[n] then
        Print("S", n, " = ", result, " PASS (", elapsed, "s)\n");
    else
        Print("S", n, " = ", result, " FAIL (expected ", expected[n], ")\n");
        allPass := false;
    fi;
od;

if allPass then
    Print("\nALL PASS (checkpoint resume)\n");
else
    Print("\nSOME FAILED\n");
fi;

LogTo();
QUIT;
