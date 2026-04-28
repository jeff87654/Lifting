
LogTo("C:/Users/jeffr/Downloads/Lifting/test_gah_missing.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/diag_combo6_diffs.g");

r := DIAG_GAH_DIFFERS_LOADED[1];

# Run GAH with seed=34 (which gave 8 in our prior test) to get a maximally
# undercounting example.
Reset(GlobalMersenneTwister, 34);
Q := Group(r.Q_gens);
M_bar := Group(r.M_bar_gens);
SetSize(Q, r.Q_size);
SetSize(M_bar, r.M_bar_size);
C := Centralizer(Q, M_bar);

GENERAL_AUT_HOM_VERBOSE := true;

Print("[mis] Running GAH (seed 34)...\n");
gah := GeneralAutHomComplements(Q, M_bar, C);
Print("[mis] GAH returned ", Length(gah), " classes\n\n");

Print("[mis] Running NSCR for ground truth...\n");
nscr := NonSolvableComplementClassReps(Q, M_bar);
Print("[mis] NSCR returned ", Length(nscr), " classes\n\n");

# Identify missing NSCR reps (those not Q-conjugate to any GAH rep).
Print("[mis] Identifying missing K(s)...\n");
missing := [];
for n_idx in [1..Length(nscr)] do
    found := false;
    for g in gah do
        if Size(nscr[n_idx]) = Size(g) then
            if RepresentativeAction(Q, nscr[n_idx], g) <> fail then
                found := true; break;
            fi;
        fi;
    od;
    if not found then Add(missing, n_idx); fi;
od;
Print("[mis] missing NSCR indices: ", missing, "\n\n");

# For each missing K, extract its (hom, m) parametrization wrt the same
# a_lift GAH would use.
Print("[mis] === Reproducing GAH internals ===\n");

# Recompute phi, A, complsInA the same way GAH does.
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
Print("[mis] |A| = ", Size(A), "  |Inn| = ", Size(innT), "\n");

# Use seed 34 to get same complsInA as GAH used.
Reset(GlobalMersenneTwister, 34);
complsInA := NonSolvableComplementClassReps(A, innT);
Print("[mis] complsInA: ", Length(complsInA), " reps\n");
for ai in complsInA do
    Print("  A_i = ", GeneratorsOfGroup(ai), "\n");
od;

Ai := complsInA[1];
a_gen := GeneratorsOfGroup(Ai)[1];
Print("\n[mis] using a_gen = ", a_gen, "\n");

# Find a_lift like GAH does.
cand := PreImagesRepresentative(phi, a_gen);
Print("[mis] PreImagesRepresentative: ", cand, "  Order=", Order(cand), "\n");
if Order(cand) <> 2 then
    for c_elt in C do
        attempt := c_elt * cand;
        if Order(attempt) = 2 then
            cand := attempt; break;
        fi;
    od;
fi;
a_lift := cand;
Print("[mis] a_lift = ", a_lift, "  Order=", Order(a_lift), "\n");
Print("[mis] phi(a_lift) = a_gen ? ", Image(phi, a_lift) = a_gen, "\n\n");

# For each missing K, extract (hom, m).
gensC := GeneratorsOfGroup(C);
Print("[mis] gensC = ", gensC, "\n\n");

for n_idx in missing do
    K := nscr[n_idx];
    Print("[mis] === Missing K #", n_idx, " ===\n");
    Print("    |K|=", Size(K), "  gens=", GeneratorsOfGroup(K), "\n");

    # K_C_prime := K cap (M_bar * C).
    MC := ClosureGroup(M_bar, C);
    K_C_prime := Intersection(K, MC);
    Print("    |K_C_prime| = ", Size(K_C_prime), " (expect ", Size(C), ")\n");

    if Size(K_C_prime) <> Size(C) then
        Print("    !! K_C_prime size mismatch -- K_C' is NOT |C|\n");
        continue;
    fi;

    # Extract hom: c -> hom(c) such that K_C_prime contains hom(c)*c.
    hom_imgs := [];
    ok := true;
    for c_gen in gensC do
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
    if not ok then
        Print("    !! could not extract hom\n");
        continue;
    fi;
    Print("    hom(c) for each c in gensC:\n");
    for i in [1..Length(gensC)] do
        Print("      c=", gensC[i], " -> hom(c)=", hom_imgs[i], "\n");
    od;

    # Find ell in K with phi(ell) in a_gen*Inn(M_bar) and order 2.
    Print("    looking for ell in K with phi(ell) in a_gen*Inn and ell^2=1...\n");
    ell_found := fail;
    for k in K do
        if Image(phi, k) <> One(A) and Order(k) = 2 then
            phi_k := Image(phi, k);
            # phi_k should be in a_gen*Inn coset.
            if phi_k * a_gen^-1 in innT then
                ell_found := k;
                break;
            fi;
        fi;
    od;
    if ell_found = fail then
        Print("    !! NO ell in K with order 2 mapping to a_gen*Inn\n");
        continue;
    fi;
    Print("    ell = ", ell_found, "  Order = ", Order(ell_found), "\n");
    Print("    phi(ell) = ", Image(phi, ell_found), "\n");

    # ell = m * a_lift, so m = ell * a_lift^-1.
    m_extracted := ell_found * a_lift^-1;
    Print("    m = ell * a_lift^-1 = ", m_extracted, "\n");
    Print("    m in M_bar? ", m_extracted in M_bar, "\n");

    if m_extracted in M_bar then
        # Verify cocycle: m*a_gen(m) = 1.
        m_a := a_lift * m_extracted * a_lift^-1;  # a_gen(m)
        Print("    m * a_gen(m) = ", m_extracted * m_a, "  (=1?)\n");

        # Build the hom for evaluation.
        hom_obj := GroupHomomorphismByImages(C, M_bar, gensC, hom_imgs);
        if hom_obj = fail then
            Print("      !! hom_imgs do not form a valid hom\n");
        else
            Print("    hom is valid hom (hom: C -> M_bar)\n");
            for i in [1..Length(gensC)] do
                c_a := gensC[i]^a_lift;
                lhs := Image(hom_obj, c_a);
                rhs := ell_found * Image(hom_obj, gensC[i]) * ell_found^-1;
                Print("      c_idx=", i, " lhs=", lhs, " rhs=", rhs,
                      "  match? ", lhs = rhs, "\n");
                if lhs <> rhs then all_ok := false; fi;
            od;
            Print("    equivariance all-ok? ", all_ok, "\n");
        fi;
    fi;
od;

LogTo();
QUIT;
