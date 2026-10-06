###############################################################################
# b_c4_harvest.g
#
# Engine harvest for C_4^k FPF combos ([4,1]^k partitions).  Same UC-telescoping
# structure as b_d8_harvest.g.
#
# Derivation:
#   G = C_4^k (abelian) -> N_G(H) = G.  W = D_8 wr S_k = (C_4^k) rtimes (C_2 wr S_k).
#   C_2 wr S_k acts via per-block inversion + S_k permutation.
#   For each engine rep (U, C, ell-orbit-under-stab) the class size is
#     cs = (4k)! * orbit_len * |R| / (8^k * |C_rec.stab|).
#   Summing over ell-orbits per (U, C) uses |R| * E_size = 2^{L_dim}:
#     class_sum_per_(U,C) = (4k)! * 2^{L_dim} / (8^k * |C_rec.stab|).
#
# Per-rep cost: zero (no ell-orbit enumeration; only U + C orbit enumeration,
# which the engine does for counting anyway).
###############################################################################

Read("C:/Users/jeffr/Downloads/Lifting/b_c4.g");

BC4_ClassSumUC := function(k)
    local setup, U_orbits, U_rec, C_orbits, C_rec, t0, t_hb, u_idx,
          U_dim, C_dim, L_dim, contrib, class_sum, fact_n;
    setup := BC4_Setup(k);
    fact_n := Factorial(4 * k);
    t0 := Runtime();
    U_orbits := BC4_EnumerateUorbits(setup);
    class_sum := 0;
    t_hb := Runtime();
    for u_idx in [1..Length(U_orbits)] do
        U_rec := U_orbits[u_idx];
        U_dim := Dimension(U_rec.U);
        C_orbits := BC4_EnumerateCorbits(setup, U_rec);
        for C_rec in C_orbits do
            C_dim := Dimension(C_rec.C);
            L_dim := U_dim * (Dimension(setup.Z) - C_dim);
            contrib := fact_n * 2^L_dim / (8^k * Length(C_rec.stab));
            class_sum := class_sum + contrib;
        od;
        if Runtime() - t_hb >= 15000 or u_idx = Length(U_orbits) then
            Print("[BC4uc] k=", k, "  u=", u_idx, "/", Length(U_orbits),
                  "  cs_so_far=", class_sum,
                  "  (elapsed_ms=", Runtime() - t0, ")\n");
            t_hb := Runtime();
        fi;
    od;
    return rec(class_sum := class_sum, elapsed_ms := Runtime() - t0);
end;
