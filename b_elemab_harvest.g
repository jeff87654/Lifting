###############################################################################
# b_elemab_harvest.g
#
# Engine harvest of class sizes for elementary-abelian (T = (Z/p)^m)^k combos
# (covers C_p^k, V_4^k, F_p^k, ... -- the b_elemab family).
#
# Formula (derived from W = AGL_m(F_p) wr S_k = T^k ⋊ (GL_m wr S_k); T^k abelian
# so acts trivially on V <= T^k):
#     |N_W(H)| = |T^k| * |Stab_{(GL_m wr S_k)}(V as F_p-subspace of F_p^{mk})|
#     cs       = (d*k)! / |N_W(H)|
#
# |GL_m wr S_k| is tiny (|GL_m|^k * k!), so the Stabilizer call is essentially
# free per rep.  For GL_m = trivial (m=1, p=2: AGL_1(F_2)=C_2) the formula
# reduces to a closed-form |Stab_{S_k}(V)| =
# |Stab_{A_perm}(mults under Permuted)| * Product(mult_i!).
###############################################################################

Read("C:/Users/jeffr/Downloads/Lifting/b_elemab.g");

# Build (GL_m(F_p))^k wr S_k as a matrix group on F_p^{mk}.
ELEMAB_BuildGLmWrSk := function(p, m, k)
    local mk, gens, g, M, i, ip, ip_m;
    mk := m * k;
    gens := [];
    # Per-block GL_m gens (block-diagonal embedding)
    for i in [1..k] do
        for g in GeneratorsOfGroup(GL(m, p)) do
            M := IdentityMat(mk) * One(GF(p));
            M{[(i-1)*m + 1 .. i*m]}{[(i-1)*m + 1 .. i*m]} := g;
            Add(gens, M);
        od;
    od;
    # S_k gens: adjacent transpositions (swap blocks i, i+1) as permutation matrices
    for i in [1..k-1] do
        M := IdentityMat(mk) * One(GF(p));
        for ip in [1..m] do
            M[(i-1)*m + ip][(i-1)*m + ip] := Zero(GF(p));
            M[i*m + ip][i*m + ip] := Zero(GF(p));
            M[(i-1)*m + ip][i*m + ip] := One(GF(p));
            M[i*m + ip][(i-1)*m + ip] := One(GF(p));
        od;
        Add(gens, M);
    od;
    return Group(gens);
end;

# Build a canonical basis matrix for V <= F_p^{mk} of a rep
# (rows = basis vectors).  For OnSubspacesByCanonicalBasis we must pass
# the SEMIECHELON canonical form so identity-action checks work.
ELEMAB_RepToBasisMat := function(rep)
    local p, m, k, mk, r, S, mults, rec_data, all_subs, Bs, idx, blocks, i,
          copy, M, j, V_basis;
    p := rep.p; m := rep.m; k := rep.k; mk := m * k;
    if IsBound(rep.full_T_k) and rep.full_T_k then
        # full space basis = identity
        return IdentityMat(mk) * One(GF(p));
    fi;
    r := rep.r;
    S := rep.S; mults := rep.mults;
    rec_data := ELEMAB_GLrOnSubspaces(p, r, m);
    all_subs := rec_data.all_subs;
    Bs := List(S, idx -> ELEMAB_BasisMatrix(p, r, m, all_subs[idx]));
    blocks := [];
    for i in [1..Length(S)] do
        for copy in [1..mults[i]] do
            Add(blocks, Bs[i]);
        od;
    od;
    M := List([1..r], j -> []);
    for i in [1..k] do
        for j in [1..r] do
            Append(M[j], blocks[i][j]);
        od;
    od;
    V_basis := List(M, row -> row * One(GF(p)));
    return BasisVectors(SemiEchelonBasis(VectorSpace(GF(p), V_basis)));
end;

# Compute cs for a single rep using the tiny-group Stabilizer.
ELEMAB_RepClassSize := function(rep)
    local p, m, k, d, B, WrG, stab;
    p := rep.p; m := rep.m; k := rep.k;
    d := p ^ m;
    B := ELEMAB_RepToBasisMat(rep);
    WrG := ELEMAB_BuildGLmWrSk(p, m, k);
    stab := Stabilizer(WrG, B, OnSubspacesByCanonicalBasis);
    return Factorial(d * k) / (p^(m * k) * Size(stab));
end;

# Top-level: compute class_sum + per-rep class_sizes for [d=p^m, t]^k.
BElemab_ClassSumWithSizes := function(p, m, k)
    local d, all_reps, r, class_sizes, class_sum, rep, cs, t0, t_hb;
    d := p ^ m;
    t0 := Runtime();
    all_reps := [];
    for r in [m..m * k] do
        Append(all_reps, ELEMAB_EnumerateRankRReps(p, m, k, r));
    od;
    Print("[elemab-h] total reps=", Length(all_reps),
          "  (enum_ms=", Runtime() - t0, ")\n");
    class_sizes := [];
    class_sum := 0;
    t_hb := Runtime();
    for rep in all_reps do
        cs := ELEMAB_RepClassSize(rep);
        Add(class_sizes, cs);
        class_sum := class_sum + cs;
        if Runtime() - t_hb >= 15000 then
            Print("[elemab-h] done ", Length(class_sizes), "/",
                  Length(all_reps), "  cs_sum=", class_sum,
                  "  (elapsed_ms=", Runtime() - t0, ")\n");
            t_hb := Runtime();
        fi;
    od;
    return rec(count := Length(all_reps),
               class_sum := class_sum,
               class_sizes := class_sizes,
               elapsed_ms := Runtime() - t0);
end;
