
LogTo("C:/Users/jeffr/Downloads/Lifting/test_allhom_det.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/diag_combo6_diffs.g");

r := DIAG_GAH_DIFFERS_LOADED[1];
Q := Group(r.Q_gens);
M_bar := Group(r.M_bar_gens);
SetSize(Q, r.Q_size);
SetSize(M_bar, r.M_bar_size);
C := Centralizer(Q, M_bar);

Print("[det] |Q|=", Size(Q), " |M_bar|=", Size(M_bar),
      " |C|=", Size(C), "\n");
Print("[det] gens(C) = ", GeneratorsOfGroup(C), "\n");
Print("[det] |gens(C)| = ", Length(GeneratorsOfGroup(C)), "\n\n");

# Call AllHomomorphismClasses 10 times with reset random seed, see if count varies.
counts := [];
for trial in [1..10] do
    Reset(GlobalMersenneTwister, trial * 17);
    h := AllHomomorphismClasses(C, M_bar);
    Add(counts, Length(h));
    Print("[det] trial ", trial, " (seed ", trial*17, "): ",
          Length(h), " hom classes\n");
od;
Print("[det] count summary: ", counts, "\n");
Print("[det] all same? ", Length(Set(counts)) = 1, "\n\n");

# Also try with different generating sets of C.
Print("[det] === testing with different gens of C ===\n");
sg := SmallGeneratingSet(C);
Print("[det] SmallGeneratingSet(C) = ", sg, " (len ", Length(sg), ")\n");
mg := MinimalGeneratingSet(C);
Print("[det] MinimalGeneratingSet(C) = ", mg, " (len ", Length(mg), ")\n");
C_sm := Group(sg);
SetSize(C_sm, Size(C));
C_mg := Group(mg);
SetSize(C_mg, Size(C));
Print("[det] AllHomClasses(C_sm, M_bar) = ", Length(AllHomomorphismClasses(C_sm, M_bar)), "\n");
Print("[det] AllHomClasses(C_mg, M_bar) = ", Length(AllHomomorphismClasses(C_mg, M_bar)), "\n");

LogTo();
QUIT;
