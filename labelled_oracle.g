###############################################################################
# labelled_oracle.g
#
# Oracle for labelled-subgroup counting.  Given an FPF conjugacy-class
# representative H (subgroup of S_m, full support), its number of labelled
# S_m-conjugates is the class size  cs = m! / |N_{S_m}(H)|.
#
# Two ways to obtain |N_{S_m}(H)|:
#   * direct   : Normalizer(SymmetricGroup(m), H)            -- exact, slow for large m
#   * localized: |N_W(H)|, W = N_{S_m}(D), D = prod of orbit constituents
#                (proven identity N_{S_m}(H) = N_W(H); W tiny vs S_m)
#
# This file provides the DIRECT oracle (correctness baseline) plus a
# localized variant built from H's own orbit constituents, so it needs no
# combo metadata.  Used by compute_labelled.py.
###############################################################################

# ParseRepGroup(repString, m)
#   repString is a bare GAP list of permutations, e.g. "[(1,2),(3,4)]" or "[]".
#   Returns the subgroup of S_m it generates.
ParseRepGroup := function(repString)
    local lst;
    NormalizeWhitespace(repString);
    if repString = "[]" or repString = "[ ]" then
        return Group(());
    fi;
    lst := EvalString(repString);
    if Length(lst) = 0 then
        return Group(());
    fi;
    return Group(lst);
end;

# DirectClassSize(H, m)
#   cs = m! / |N_{S_m}(H)|  via a direct backtrack Normalizer in S_m.
DirectClassSize := function(H, m)
    local nrm;
    nrm := Normalizer(SymmetricGroup(m), H);
    return Factorial(m) / Size(nrm);
end;

# BuildConstituentProduct(H, m)
#   D = direct product (on the natural m points) of the transitive
#   constituents of H on each of its orbits.  Orbits of size 1 (fixed points)
#   contribute nothing.  For an FPF H this D has the same orbits as H.
BuildConstituentProduct := function(H, m)
    local orbs, gens, o, restr, g, img, p, movedSet;
    orbs := Orbits(H, [1..m]);
    gens := [];
    for o in orbs do
        if Length(o) = 1 then
            continue;
        fi;
        movedSet := Set(o);
        # constituent = action of H on this orbit, lifted back to S_m by
        # acting as identity off the orbit.
        for g in GeneratorsOfGroup(H) do
            img := [1..m];
            for p in o do
                img[p] := p^g;
            od;
            Add(gens, PermList(img));
        od;
    od;
    if Length(gens) = 0 then
        return Group(());
    fi;
    return Group(gens);
end;

# LocalizedClassSize(H, m)
#   cs = m! / |N_W(H)|, W = Normalizer(S_m, D).  Equal to DirectClassSize by
#   the proven identity, but W is built once and reused; the final
#   Normalizer(W,H) backtrack runs inside the small W.  NOTE: still pays one
#   S_m backtrack to build W -- use BuildWBlockwise for scaling.
LocalizedClassSize := function(H, m)
    local D, W, nrm;
    D := BuildConstituentProduct(H, m);
    W := Normalizer(SymmetricGroup(m), D);
    nrm := Normalizer(W, H);
    return Factorial(m) / Size(nrm);
end;

# BlockConstituent(H, pts, m)
#   The transitive constituent of H on the orbit `pts` (sorted set), as a
#   subgroup of S_m acting as identity off `pts`.
BlockConstituent := function(H, pts, m)
    local gens, g, img, p;
    gens := [];
    for g in GeneratorsOfGroup(H) do
        img := [1..m];
        for p in pts do
            img[p] := p^g;
        od;
        Add(gens, PermList(img));
    od;
    return Group(gens);
end;

# BlockTransId(C, pts)
#   TransitiveIdentification of the constituent C restricted to its own block
#   points `pts` (relabelled 1..d).  Two equal-degree blocks are swappable in
#   S_m iff they share this id (same transitive group up to S_d-conjugacy).
#   Always available for d <= 21 (well within the transitive-groups library).
BlockTransId := function(C, pts)
    local d, restr;
    d := Length(pts);
    restr := Group(List(GeneratorsOfGroup(C),
        g -> PermList(List([1..d], k -> Position(pts, pts[k] ^ g)))));
    return [d, TransitiveIdentification(restr)];
end;

# BuildWBlockwise(H, m)
#   Build W = N_{S_m}(D) WITHOUT an S_m backtrack:
#     * per-block: M_i = Normalizer(Sym(block_i), C_i)   (tiny, degree d_i)
#     * block swaps: for blocks i,j of equal size with constituents conjugate
#       in S_d, an adjusted involution s with C_i^s = C_j, C_j^s = C_i.
#   Adjacent swaps within each cluster generate the block-permutation part.
#   This equals Normalizer(S_m, D) (validated against the direct oracle).
BuildWBlockwise := function(H, m)
    local orbs, blocks, b, pts, C, M, infos, gens, clusters, key, i,
          beta, x, conjC, gamma, s, k, posI, posJ, ptsI, ptsJ, d,
          sigImg, target;
    orbs := Orbits(H, [1..m]);
    blocks := Filtered(orbs, o -> Length(o) >= 2);
    blocks := List(blocks, Set);
    Sort(blocks, function(a, c) return Minimum(a) < Minimum(c); end);

    gens := [];
    infos := [];           # per block: rec(pts, C, sizeC, idkey)
    for b in blocks do
        pts := b;
        C := BlockConstituent(H, pts, m);
        M := Normalizer(SymmetricGroup(pts), C);
        Append(gens, GeneratorsOfGroup(M));
        Add(infos, rec(pts := pts, C := C));
    od;

    # cluster blocks by the exact swap invariant: (degree, TransitiveId).
    clusters := rec();
    for i in [1..Length(infos)] do
        key := String(BlockTransId(infos[i].C, infos[i].pts));
        if not IsBound(clusters.(key)) then
            clusters.(key) := [];
        fi;
        Add(clusters.(key), i);
    od;

    # adjacent adjusted swaps within each cluster.  For adjacent blocks i,j the
    # swap must be an involution sigma with phi = gamma o beta a bijection
    # pts_i -> pts_j satisfying phi(C_i) = C_j (which forces phi^{-1}(C_j) = C_i).
    #   beta  : in-order bijection pts_i <-> pts_j
    #   gamma : in Sym(pts_j), conjugating beta(C_i) to C_j (identity if already equal)
    #   sigma : p_i ↦ (p_j)^gamma  and its inverse  (involution, identity elsewhere)
    for key in RecNames(clusters) do
        if Length(clusters.(key)) < 2 then
            continue;
        fi;
        for k in [1 .. Length(clusters.(key)) - 1] do
            posI := clusters.(key)[k];
            posJ := clusters.(key)[k + 1];
            ptsI := infos[posI].pts;
            ptsJ := infos[posJ].pts;
            d := Length(ptsI);
            # in-order swap s and conjugate of C_i
            beta := [1 .. m];
            for x in [1 .. d] do
                beta[ptsI[x]] := ptsJ[x];
                beta[ptsJ[x]] := ptsI[x];
            od;
            s := PermList(beta);
            conjC := infos[posI].C ^ s;          # = beta(C_i), lives on pts_j
            if conjC = infos[posJ].C then
                gamma := ();
            else
                gamma := RepresentativeAction(SymmetricGroup(ptsJ),
                                              conjC, infos[posJ].C, OnPoints);
                if gamma = fail then
                    # clustering over-grouped (should not happen with TransId);
                    # skip -- per-combo direct check flags any resulting undercount.
                    continue;
                fi;
            fi;
            # build involution sigma with phi(pts_i[x]) = (pts_j[x])^gamma
            sigImg := [1 .. m];
            for x in [1 .. d] do
                target := ptsJ[x] ^ gamma;
                sigImg[ptsI[x]] := target;
                sigImg[target]  := ptsI[x];
            od;
            Add(gens, PermList(sigImg));
        od;
    od;

    if Length(gens) = 0 then
        return Group(());
    fi;
    return Group(gens);
end;

# LocalizedFastClassSize(H, m)
#   cs via BuildWBlockwise (no S_m backtrack).
LocalizedFastClassSize := function(H, m)
    return Factorial(m) / Size(Normalizer(BuildWBlockwise(H, m), H));
end;

###############################################################################
# Scalable post-pass: read a combo file directly and emit class sizes.
###############################################################################

# ReadRepLinesFromFile(path)
#   Return the list of generator-line strings (those starting with "[") from a
#   combo .g file, with GAP line-continuations ("\<newline>") joined.
ReadRepLinesFromFile := function(path)
    local text, joined, lines, out, ln;
    text := StringFile(path);
    if text = fail then
        return fail;
    fi;
    # join continuations: backslash immediately before a newline
    joined := ReplacedString(text, "\\\n", "");
    joined := ReplacedString(joined, "\\\r\n", "");
    lines := SplitString(joined, "\n");
    out := [];
    for ln in lines do
        NormalizeWhitespace(ln);
        if Length(ln) > 0 and ln[1] = '[' then
            Add(out, ln);
        fi;
    od;
    return out;
end;

# ProcessComboFileToSidecar(path, m, sidecarPath)
#   Compute per-rep class sizes for the combo file and write a sidecar with
#   "# class_sizes: c1,c2,..." and "# class_sum: S" lines.  Returns [S, nreps].
#   W is rebuilt from each rep's own constituents (safe: N_{S_m}(H) <= N_{S_m}(D_H)
#   only for H's own constituent product D_H).
ProcessComboFileToSidecar := function(path, m, sidecarPath)
    local reps, total, sizes, H, cs, r, out;
    reps := ReadRepLinesFromFile(path);
    if reps = fail then
        return fail;
    fi;
    total := 0;
    sizes := [];
    for r in reps do
        H := ParseRepGroup(r);
        cs := LocalizedFastClassSize(H, m);
        Add(sizes, cs);
        total := total + cs;
    od;
    out := OutputTextFile(sidecarPath, false);
    AppendTo(out, "# class_sum: ", total, "\n");
    AppendTo(out, "# nreps: ", Length(sizes), "\n");
    AppendTo(out, "# class_sizes: ",
             JoinStringsWithSeparator(List(sizes, String), ","), "\n");
    CloseStream(out);
    return [total, Length(sizes)];
end;
