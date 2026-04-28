
LogTo("C:/Users/jeffr/Downloads/Lifting/analyze_gah_diff.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/diag_combo6_diffs.g");

records := DIAG_GAH_DIFFERS_LOADED;
SortBy(records, r -> r.Q_size);
Print("[ana] ", Length(records), " divergent records loaded\n");
for i in [1..Length(records)] do
    r := records[i];
    Print("  [", i-1, "] |Q|=", r.Q_size, " |M_bar|=", r.M_bar_size,
          " |C|=", r.C_size, " idx=", r.idx,
          " GAH=", r.gah_count, " NSCR=", r.nscr_count, "\n");
od;
Print("\n");

rec_idx := 0 + 1;
if rec_idx > Length(records) then
    Error("[ana] no record at index ", 0);
fi;
r := records[rec_idx];
Print("[ana] analyzing record ", 0, ": |Q|=", r.Q_size, "\n");

Q := Group(r.Q_gens);
M_bar := Group(r.M_bar_gens);
SetSize(Q, r.Q_size);
SetSize(M_bar, r.M_bar_size);
C := Centralizer(Q, M_bar);
Print("[ana] |Q|=", Size(Q), " |M_bar|=", Size(M_bar),
      " |C|=", Size(C), " idx=", Size(Q)/Size(M_bar), "\n\n");

GENERAL_AUT_HOM_VERBOSE := true;

Print("[ana] === Running GAH ===\n");
t0 := Runtime();
gah := GeneralAutHomComplements(Q, M_bar, C);
Print("[ana] GAH: ", Length(gah), " classes in ", Runtime()-t0, "ms\n\n");

Print("[ana] === Running NSCR ===\n");
t0 := Runtime();
nscr := NonSolvableComplementClassReps(Q, M_bar);
Print("[ana] NSCR: ", Length(nscr), " classes in ", Runtime()-t0, "ms\n\n");

Print("[ana] === Cross-mapping ===\n");
matched_gah := [];
unmatched_nscr := [];
for n_idx in [1..Length(nscr)] do
    matched := false;
    for g_idx in [1..Length(gah)] do
        if Size(nscr[n_idx]) <> Size(gah[g_idx]) then continue; fi;
        if RepresentativeAction(Q, nscr[n_idx], gah[g_idx]) <> fail then
            AddSet(matched_gah, g_idx);
            matched := true;
            break;
        fi;
    od;
    if not matched then Add(unmatched_nscr, n_idx); fi;
od;

Print("[ana] NSCR reps with no GAH match: ", Length(unmatched_nscr),
      " of ", Length(nscr), "\n");
Print("[ana] GAH reps matched by some NSCR: ", Length(matched_gah),
      " of ", Length(gah), "\n");

Print("\n[ana] === Missing complements (in NSCR but not GAH) ===\n");
for n_idx in unmatched_nscr do
    K := nscr[n_idx];
    Print("  [missing #", n_idx, "] |K|=", Size(K),
          " AbelianInvariants=", AbelianInvariants(K),
          " orbit-sizes=", SortedList(List(Orbits(K, MovedPoints(Q)), Length)),
          "\n");
    Print("    gens=", GeneratorsOfGroup(K), "\n");
    MC := ClosureGroup(M_bar, C);
    K_C_prime := Intersection(K, MC);
    Print("    |K cap (M_bar*C)| = ", Size(K_C_prime),
          " (expected |C|=", Size(C), ")\n");
    if Size(K_C_prime) = Size(C) then
        hom_imgs := [];
        ok := true;
        for c_gen in GeneratorsOfGroup(C) do
            found := fail;
            for k in K_C_prime do
                if k * c_gen^-1 in M_bar then
                    found := k * c_gen^-1;
                    break;
                fi;
            od;
            if found = fail then ok := false; break; fi;
            Add(hom_imgs, found);
        od;
        if ok then
            Print("    extracted hom on gensC:\n");
            for i in [1..Length(GeneratorsOfGroup(C))] do
                Print("      c=", GeneratorsOfGroup(C)[i],
                      "  ->  hom(c)=", hom_imgs[i], "\n");
            od;
        else
            Print("    could not extract hom (K_C_prime not graph form?)\n");
        fi;
    fi;
od;

LogTo();
QUIT;
