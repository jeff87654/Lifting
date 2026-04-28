
LogTo("C:/Users/jeffr/Downloads/Lifting/trace_gah.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/diag_combo6_diffs.g");

r := DIAG_GAH_DIFFERS_LOADED[1];
Reset(GlobalMersenneTwister, 34);  # seed that gives GAH=8

Q := Group(r.Q_gens);
M_bar := Group(r.M_bar_gens);
SetSize(Q, r.Q_size);
SetSize(M_bar, r.M_bar_size);
C := Centralizer(Q, M_bar);

# Reproduce GAH setup.
gensT := SmallGeneratingSet(M_bar);
autT := AutomorphismGroup(M_bar);
isoPerm := IsomorphismPermGroup(autT);
autPerm := Image(isoPerm);
innGens := List(gensT, t -> Image(isoPerm, ConjugatorAutomorphismNC(M_bar, t)));
innT := Group(innGens);
qGens := GeneratorsOfGroup(Q);
qImages := List(qGens, function(g)
    local imgs;
    imgs := List(gensT, m -> m^g);
    return Image(isoPerm,
        GroupHomomorphismByImages(M_bar, M_bar, gensT, imgs));
end);
phi := GroupHomomorphismByImages(Q, autPerm, qGens, qImages);
A := Image(phi);

complsInA := NonSolvableComplementClassReps(A, innT);
Print("[trace] complsInA len=", Length(complsInA), "\n");
Ai := complsInA[1];
a_gen := GeneratorsOfGroup(Ai)[1];
Print("[trace] a_gen=", a_gen, "\n");

# a_lift via _findRightOrderLift logic.
cand := PreImagesRepresentative(phi, a_gen);
if Order(cand) <> 2 then
    for c_elt in C do
        if Order(c_elt * cand) = 2 then cand := c_elt * cand; break; fi;
    od;
fi;
a_lift := cand;
Print("[trace] a_lift=", a_lift, "  Order=", Order(a_lift), "\n");

gensC := GeneratorsOfGroup(C);
homClasses := AllHomomorphismClasses(C, M_bar);
Print("[trace] |homClasses|=", Length(homClasses), "\n\n");

# Loop through homClasses, dump per-hom info, build K's.
all_K_built := [];
hom_trace := [];
for hom_idx in [1..Length(homClasses)] do
    hom := homClasses[hom_idx];
    base_imgs := List(gensC, c -> Image(hom, c));
    c_a_map := List(gensC, c -> Image(hom, c^a_lift));

    # Find validTaus.
    validTaus := [];
    for m_trial in M_bar do
        ell := m_trial * a_lift;
        if ell^2 <> One(Q) then continue; fi;
        ok := true;
        for c_idx in [1..Length(gensC)] do
            if ell * c_a_map[c_idx] * ell^-1 <> base_imgs[c_idx] then
                ok := false; break;
            fi;
        od;
        if ok then Add(validTaus, m_trial); fi;
    od;

    if Length(validTaus) = 0 then
        Add(hom_trace, rec(hom_idx := hom_idx, base_imgs := base_imgs,
                           validTaus := 0, orbitReps := 0, K_count := 0));
        continue;
    fi;

    # Stab.
    if ForAll(base_imgs, x -> x = One(M_bar)) then
        stab_elts := AsList(M_bar);
    else
        stab_elts := AsList(Centralizer(M_bar,
                            Group(Filtered(base_imgs, x -> x <> One(M_bar)))));
    fi;

    # Orbit dedup.
    orbitReps := Set([]);
    for m_trial in validTaus do
        canon := m_trial;
        for stab_m in stab_elts do
            cand := stab_m^-1 * m_trial * (a_lift * stab_m * a_lift^-1);
            if cand < canon then canon := cand; fi;
        od;
        cand := a_lift^-1 * m_trial * a_lift;
        if cand < canon then canon := cand; fi;
        for stab_m in stab_elts do
            cand := a_lift^-1 * (stab_m^-1 * m_trial
                  * (a_lift * stab_m * a_lift^-1)) * a_lift;
            if cand < canon then canon := cand; fi;
        od;
        AddSet(orbitReps, canon);
    od;

    # Build K's.
    K_per_hom := [];
    for m_trial in orbitReps do
        ell := m_trial * a_lift;
        K_gens := Concatenation(
            List([1..Length(gensC)], i -> base_imgs[i] * gensC[i]),
            [ell]);
        K := Group(K_gens);
        size_K := Size(K);
        int_K := Size(Intersection(K, M_bar));
        if size_K = 960 and int_K = 1 then
            Add(K_per_hom, K);
            Add(all_K_built, K);
        else
            Print("    hom #", hom_idx, " m=", m_trial, " ell=", ell,
                  " Size(K)=", size_K, " (expect 960) Int=", int_K,
                  " (expect 1)\n");
            Print("      base_imgs=", base_imgs, "\n");
        fi;
    od;

    Add(hom_trace, rec(hom_idx := hom_idx, base_imgs := base_imgs,
                       validTaus := Length(validTaus),
                       stab_size := Length(stab_elts),
                       orbitReps := Length(orbitReps),
                       K_count := Length(K_per_hom)));
od;

Print("[trace] === per-hom summary ===\n");
for h in hom_trace do
    Print("  hom #", h.hom_idx, ":");
    if IsBound(h.stab_size) then
        Print("  validTaus=", h.validTaus,
              "  stab_size=", h.stab_size,
              "  orbitReps=", h.orbitReps,
              "  K=", h.K_count);
    else
        Print("  validTaus=", h.validTaus, "  K=0");
    fi;
    Print("\n");
od;

Print("\n[trace] total K built = ", Length(all_K_built), "\n");

# Now do the cross-hom dedup like GAH does.
Print("[trace] === cross-hom dedup (RA on each pair within invariant bucket) ===\n");
result := [];
byInv := rec();
for candidate in all_K_built do
    key := Concatenation(
        String(AbelianInvariants(candidate)), "|",
        String(SortedList(List(Orbits(candidate, MovedPoints(Q)), Length))));
    if not IsBound(byInv.(key)) then byInv.(key) := []; fi;
    bucket := byInv.(key);
    is_dup := false;
    for bg in bucket do
        if RepresentativeAction(Q, candidate, bg) <> fail then
            is_dup := true; break;
        fi;
    od;
    if not is_dup then
        Add(bucket, candidate);
        Add(result, candidate);
    fi;
od;
Print("[trace] dedup result: ", Length(result), " classes\n");

# Compare with NSCR.
Print("[trace] === NSCR comparison ===\n");
nscr := NonSolvableComplementClassReps(Q, M_bar);
Print("[trace] NSCR: ", Length(nscr), " classes\n");

missing := [];
for n_idx in [1..Length(nscr)] do
    found := false;
    for k in result do
        if Size(nscr[n_idx]) = Size(k) and
           RepresentativeAction(Q, nscr[n_idx], k) <> fail then
            found := true; break;
        fi;
    od;
    if not found then Add(missing, n_idx); fi;
od;
Print("[trace] missing NSCR indices: ", missing, "\n");

LogTo();
QUIT;
