###############################################################################
#
# h1_action.g - H^1 Orbital Complement Enumeration (Phase 2)
#
# Implements normalizer orbit computation on H^1 to dramatically reduce
# complement enumeration time. Instead of enumerating all p^(dim H^1)
# complements and testing conjugacy pairwise, we compute orbits of the
# normalizer action on H^1 and return one representative per orbit.
#
# Mathematical insight (Holt's Theorem):
# Two complements G_f and G_f' are conjugate in the ambient group iff
# cocycles f and f' are in the same orbit under the normalizer action on H^1.
# The action is linear on the vector space H^1, so we can use matrix group
# orbit algorithms.
#
###############################################################################

# Ensure cohomology.g and modules.g are loaded
if not IsBound(CreateGModuleRecord) then
    Read("C:/Users/jeffr/Downloads/Lifting/cohomology.g");
fi;
if not IsBound(ChiefFactorAsModule) then
    Read("C:/Users/jeffr/Downloads/Lifting/modules.g");
fi;

# Global flag to enable/disable H^1 orbital optimization
# RE-ENABLED: Now uses outer normalizer N_P(S) ∩ N_P(M) action on H^1.
# Elements outside S provide non-trivial outer automorphism action, giving
# actual orbit reduction instead of trivial inner automorphism action.
# Only set default if not already configured (allows pre-setting before load)
if not IsBound(USE_H1_ORBITAL) then
    USE_H1_ORBITAL := true;
fi;

# Enable the section-homomorphism fallback for outer H^1 actions.  The Pcgs
# path remains preferred; this only runs when the quotient generators are not
# an exact Pcgs, where the previous code returned fail to avoid FP words.
if not IsBound(H1_OUTER_SECTION_ACTION) then
    H1_OUTER_SECTION_ACTION := false;
fi;

# Statistics for orbit computation
H1_ORBITAL_STATS := rec(
    calls := 0,
    total_orbits := 0,
    total_points := 0,
    orbit_time := 0,
    skipped_trivial := 0,
    t_module := 0,
    t_h1 := 0,
    t_action := 0,
    t_orbits := 0,
    t_convert := 0
);

###############################################################################
# ComputeActionMatrix(module, x)
#
# Compute the matrix for element x's conjugation action on the module M.
# For each Pcgs basis element m_i, compute m_i^x and express in coordinates.
#
# Input:
#   module - GModuleRecord with pcgsM basis
#   x      - element of ambient group Q (not the quotient!) acting by conjugation
#
# Returns: dim x dim matrix over GF(p) representing x's action
###############################################################################

ComputeActionMatrix := function(module, x)
    local dim, field, pcgsM, mat, i, m, img, exps, j;

    dim := module.dimension;
    field := module.field;
    pcgsM := module.pcgsM;

    mat := NullMat(dim, dim, field);

    for i in [1..dim] do
        m := pcgsM[i];
        img := m^x;  # Conjugation action
        exps := ExponentsOfPcElement(pcgsM, img);
        for j in [1..dim] do
            mat[i][j] := exps[j] * One(field);
        od;
    od;

    return mat;
end;

###############################################################################
# ComputeActionMatrixViaPreimage(module, xQuotient)
#
# Compute action matrix when we have an element of the quotient Q/M_bar.
# We need a preimage in Q to actually compute the conjugation.
#
# Input:
#   module     - GModuleRecord with preimageGens and quotientHom
#   xQuotient  - element of Q/M_bar (the quotient group)
#
# Returns: dim x dim matrix over GF(p) representing x's action
###############################################################################

ComputeActionMatrixViaPreimage := function(module, xQuotient)
    local G, Q, hom, preimage;

    G := module.group;  # This is Q/M_bar
    hom := module.quotientHom;
    Q := module.ambientGroup;

    # Find a preimage of xQuotient in Q
    preimage := PreImagesRepresentative(hom, xQuotient);

    # Now compute action using the preimage
    return ComputeActionMatrix(module, preimage);
end;

###############################################################################
# ApplyNormalizerActionOnCocycle(module, xPreimage, cocycleVec)
#
# Apply normalizer element x (in ambient Q) to cocycle f, producing f^x.
#
# The cocycle f: G -> M where G = Q/M_bar. The element x is in Q and normalizes M_bar.
# The action is: (f^x)(g) = x^{-1} * f(g^x) * x (where g^x means conjugation in Q/M_bar).
#
# For right-action modules: (f^x)(g) = f(g^{x^{-1}}) * actionMat(x)
#
# Since f is defined on G = Q/M_bar and x is in Q, we need to:
# 1. Take the generator gi in G = Q/M_bar
# 2. Get its preimage gi' in Q (from module.preimageGens)
# 3. Conjugate gi' by x^{-1} in Q to get (gi')^{x^{-1}}
# 4. Map back to G via the quotient hom
# 5. Evaluate f at this element
# 6. Apply x's action on M
#
# Input:
#   module      - GModuleRecord (with preimageGens and quotientHom)
#   xPreimage   - normalizer element in Q (ambient group)
#   cocycleVec  - vector in GF(p)^(ngens * dim) representing cocycle f
#
# Returns: transformed cocycle vector (f^x)
###############################################################################

ApplyNormalizerActionOnCocycle := function(module, xPreimage, cocycleVec)
    local G, ngens, dim, field, hom, xInv, newCocycleVec,
          i, giPreimage, giConjPreimage, giConj, cocycleValues,
          fgiConj, actionMat, result;

    G := module.group;  # G = Q/M_bar
    ngens := Length(module.generators);
    dim := module.dimension;
    field := module.field;
    hom := module.quotientHom;  # Q -> Q/M_bar = G

    # Get cocycle values f(g_i) for each generator
    cocycleValues := CocycleVectorToValues(cocycleVec, module);

    xInv := xPreimage^(-1);
    newCocycleVec := ListWithIdenticalEntries(ngens * dim, Zero(field));

    # Compute x's action matrix on M (for the second part of the formula)
    actionMat := ComputeActionMatrix(module, xPreimage);

    # For each generator g_i of G, compute (f^x)(g_i)
    for i in [1..ngens] do
        # Get preimage of g_i in Q
        giPreimage := module.preimageGens[i];

        # Conjugate in Q: (gi')^{x^{-1}} = x^{-1} * gi' * x
        giConjPreimage := giPreimage^xInv;

        # Map back to G = Q/M_bar
        giConj := Image(hom, giConjPreimage);

        # Evaluate f at giConj (an element of G)
        fgiConj := EvaluateCocycleForElement(module, cocycleValues, giConj);

        # Apply x's action on M: (f^x)(g_i) = f(g_i^{x^{-1}}) * actionMat
        result := fgiConj * actionMat;

        # Store in new cocycle vector
        newCocycleVec{[(i-1)*dim + 1 .. i*dim]} := result;
    od;

    return newCocycleVec;
end;

###############################################################################
# EvaluateCocycleForElement(module, cocycleValues, g)
#
# Evaluate cocycle f at element g, where g is expressed in the ambient group.
# Uses cocycle identity: f(gh) = f(g)^h + f(h)
#
# Input:
#   module        - GModuleRecord
#   cocycleValues - list [f(g_1), ..., f(g_r)] of values on generators
#   g             - element to evaluate f at
#
# Returns: f(g) as vector in GF(p)^dim
###############################################################################

EvaluateCocycleForElement := function(module, cocycleValues, g)
    local G, ngens, dim, field, word, pcgs, exps, i;

    G := module.group;
    ngens := Length(module.generators);
    dim := module.dimension;
    field := module.field;

    # If g is identity, f(1) = 0
    if g = One(G) then
        return ListWithIdenticalEntries(dim, Zero(field));
    fi;

    # Express g as a word in module.generators
    # Check if module.generators matches Pcgs(G)
    if CanEasilyComputePcgs(G) then
        pcgs := Pcgs(G);
        # Check if generators match Pcgs
        if ngens = Length(pcgs) and ForAll([1..ngens], i -> module.generators[i] = pcgs[i]) then
            exps := ExponentsOfPcElement(pcgs, g);
            # Convert to [[genIndex, power], ...] format
            word := [];
            for i in [1..Length(exps)] do
                if exps[i] <> 0 then
                    Add(word, [i, exps[i]]);
                fi;
            od;
        else
            # Generators don't match Pcgs, use FP-group method
            word := FactorizationInGenerators(G, g, module.generators);
        fi;
    else
        # Use FP-group factorization
        word := FactorizationInGenerators(G, g, module.generators);
    fi;

    # Use existing infrastructure
    return EvaluateCocycleOnWord(cocycleValues, word, module);
end;

###############################################################################
# FactorizationInGenerators(G, g, gens)
#
# Express g as a word in given generators.
# Returns list of [genIndex, power] pairs.
###############################################################################

FactorizationInGenerators := function(G, g, gens)
    local iso, FG, gImage, syllables, word, i, genIndex, pow;

    # Use GAP's Factorization via FP-group
    iso := IsomorphismFpGroupByGenerators(G, gens);
    gImage := Image(iso, g);

    # Parse the word
    syllables := ExtRepOfObj(UnderlyingElement(gImage));
    word := [];
    for i in [1, 3 .. Length(syllables)-1] do
        genIndex := syllables[i];
        pow := syllables[i+1];
        Add(word, [AbsInt(genIndex), pow * SignInt(genIndex)]);
    od;

    return word;
end;

###############################################################################
# H1SectionHomFromCocycle(module, cocycleVec)
#
# Build the section homomorphism C_f -> G for the complement represented by a
# cocycle.  This gives a cheap way to evaluate f(g) for non-Pcgs quotients:
# if s_0(g) is the base section and s_f(g) is the complement section, then
# f(g) is the M-component of s_0(g)^-1 * s_f(g).
###############################################################################

H1SectionHomFromCocycle := function(module, cocycleVec)
    local G, Q, ngens, dim, pcgsM, p, sourceGens, targetGens,
          i, fgi, mi, gen, C, phi;

    G := module.group;
    Q := module.ambientGroup;
    ngens := Length(module.generators);
    dim := module.dimension;
    pcgsM := module.pcgsM;
    p := module.p;

    sourceGens := [];
    targetGens := [];
    for i in [1..ngens] do
        fgi := cocycleVec{[(i-1)*dim + 1 .. i*dim]};
        mi := CocycleValueToElement(fgi, pcgsM, p);
        gen := module.preimageGens[i] * mi;
        if gen <> One(Q) then
            Add(sourceGens, gen);
            Add(targetGens, module.generators[i]);
        fi;
    od;

    if Length(sourceGens) = 0 then
        if Size(G) = 1 then
            return rec(group := TrivialSubgroup(Q),
                       hom := GroupHomomorphismByImages(TrivialSubgroup(Q), G, [], []));
        fi;
        return fail;
    fi;

    C := Group(sourceGens);
    phi := GroupHomomorphismByImages(C, G, sourceGens, targetGens);
    if phi = fail then
        return fail;
    fi;
    if not IsBijective(phi) then
        return fail;
    fi;

    return rec(group := C, hom := phi);
end;

###############################################################################
# H1BaseSectionHom(module)
#
# Build the base complement section C_0 -> G from module.preimageGens.
###############################################################################

H1BaseSectionHom := function(module)
    local G, Q, sourceGens, targetGens, C, phi;

    G := module.group;
    Q := module.ambientGroup;
    sourceGens := Filtered(module.preimageGens, g -> g <> One(Q));
    targetGens := module.generators{Filtered([1..Length(module.preimageGens)],
        i -> module.preimageGens[i] <> One(Q))};

    if Length(sourceGens) = 0 then
        if Size(G) = 1 then
            return rec(group := TrivialSubgroup(Q),
                       hom := GroupHomomorphismByImages(TrivialSubgroup(Q), G, [], []));
        fi;
        return fail;
    fi;

    C := Group(sourceGens);
    phi := GroupHomomorphismByImages(C, G, sourceGens, targetGens);
    if phi = fail then
        return fail;
    fi;
    if not IsBijective(phi) then
        return fail;
    fi;

    return rec(group := C, hom := phi);
end;

###############################################################################
# H1EvaluateCocycleViaSections(module, baseSection, cocycleSection, g)
#
# Evaluate the cocycle represented by cocycleSection at g without constructing
# an FP word in module.generators.
###############################################################################

H1EvaluateCocycleViaSections := function(module, baseSection, cocycleSection, g)
    local G, dim, field, s0, sf, m, exps;

    G := module.group;
    dim := module.dimension;
    field := module.field;

    if g = One(G) then
        return ListWithIdenticalEntries(dim, Zero(field));
    fi;

    s0 := PreImagesRepresentative(baseSection.hom, g);
    sf := PreImagesRepresentative(cocycleSection.hom, g);
    if s0 = fail or sf = fail then
        return fail;
    fi;

    m := s0^(-1) * sf;
    if not m in module.moduleGroup then
        return fail;
    fi;

    exps := ExponentsOfPcElement(module.pcgsM, m);
    return List(exps, x -> x * One(field));
end;

###############################################################################
# ProjectToH1Coordinates(cohomRecord, cocycleVec)
#
# Given a cocycle vector in Z^1, find its coordinates in the H^1 basis.
# H^1 = Z^1 / B^1, so we find the coset representative and express it
# in terms of the quotient basis.
#
# Input:
#   cohomRecord - CohomologyRecord from ComputeH1
#   cocycleVec  - cocycle vector in Z^1
#
# Returns: vector of GF(p) coordinates in H^1 basis
###############################################################################

ProjectToH1Coordinates := function(cohomRecord, cocycleVec)
    local dimH1, field, B1, quotientBasis, solutions, augmented, p;

    dimH1 := cohomRecord.H1Dimension;
    field := cohomRecord.module.field;
    p := cohomRecord.module.p;

    if dimH1 = 0 then
        return [];
    fi;

    B1 := cohomRecord.coboundaryBasis;
    quotientBasis := cohomRecord.quotientBasis;

    # We need to find coordinates c_1, ..., c_k such that
    # cocycleVec = sum(c_i * quotientBasis[i]) + (element of B^1)

    # SolutionMat(mat, vec) solves x*mat = vec for row vector x
    # We want to solve for coefficients c such that c * [quotientBasis; B1] = cocycleVec

    if Length(B1) = 0 then
        # B^1 = 0, so Z^1 = H^1
        # Solve c * quotientBasis = cocycleVec
        if Length(quotientBasis) = 0 then
            return [];
        fi;
        solutions := SolutionMat(quotientBasis, cocycleVec);
        if solutions = fail then
            # cocycleVec not in span of quotientBasis - return zero
            return ListWithIdenticalEntries(dimH1, Zero(field));
        fi;
        return solutions;
    fi;

    # General case: solve c * [quotientBasis; B1] = cocycleVec
    # The augmented matrix has quotientBasis rows first, then B1 rows
    augmented := Concatenation(quotientBasis, B1);
    solutions := SolutionMat(augmented, cocycleVec);

    if solutions = fail then
        # cocycleVec not in Z^1? Return zero
        return ListWithIdenticalEntries(dimH1, Zero(field));
    fi;

    # First dimH1 coordinates are the H^1 coordinates
    return solutions{[1..dimH1]};
end;

###############################################################################
# H1CoordsToFullCocycle(cohomRecord, coords)
#
# Convert H^1 coordinates back to a full cocycle vector in Z^1.
#
# Input:
#   cohomRecord - CohomologyRecord from ComputeH1
#   coords      - vector of GF(p) coordinates in H^1 basis
#
# Returns: cocycle vector in Z^1
###############################################################################

H1CoordsToFullCocycle := function(cohomRecord, coords)
    local dimH1, field, quotientBasis, numVars, result, i;

    dimH1 := cohomRecord.H1Dimension;
    field := cohomRecord.module.field;
    quotientBasis := cohomRecord.quotientBasis;

    if dimH1 = 0 or Length(coords) = 0 then
        numVars := Length(cohomRecord.module.generators) * cohomRecord.module.dimension;
        return ListWithIdenticalEntries(numVars, Zero(field));
    fi;

    # Compute sum(coords[i] * quotientBasis[i])
    result := ListWithIdenticalEntries(Length(quotientBasis[1]), Zero(field));
    for i in [1..dimH1] do
        if coords[i] <> Zero(field) then
            result := result + coords[i] * quotientBasis[i];
        fi;
    od;

    return result;
end;

###############################################################################
# ComputeH1ActionMatrix(cohomRecord, module, xPreimage)
#
# Compute the matrix for x's action on the quotient space H^1 = Z^1/B^1.
# For each H^1 basis vector v_i, apply x-action to get a cocycle,
# then project back to H^1 coordinates.
#
# Input:
#   cohomRecord - CohomologyRecord from ComputeH1
#   module      - GModuleRecord
#   xPreimage   - normalizer element (preimage in ambient group Q, not quotient)
#
# Returns: dimH1 x dimH1 matrix over GF(p) representing x's action on H^1
###############################################################################

ComputeH1ActionMatrix := function(cohomRecord, module, xPreimage)
    local dimH1, field, mat, i, basisVec, fullCocycle, transformedCocycle, newCoords;

    dimH1 := cohomRecord.H1Dimension;
    field := module.field;

    if dimH1 = 0 then
        return [];
    fi;

    mat := NullMat(dimH1, dimH1, field);

    for i in [1..dimH1] do
        # Get the i-th H^1 basis element as a full cocycle
        basisVec := ListWithIdenticalEntries(dimH1, Zero(field));
        basisVec[i] := One(field);
        fullCocycle := H1CoordsToFullCocycle(cohomRecord, basisVec);

        # Apply x-action on the cocycle
        transformedCocycle := ApplyNormalizerActionOnCocycle(module, xPreimage, fullCocycle);

        # Project back to H^1 coordinates
        newCoords := ProjectToH1Coordinates(cohomRecord, transformedCocycle);

        # This gives the i-th row of the action matrix
        mat[i] := newCoords;
    od;

    return mat;
end;

###############################################################################
# ComputeOuterActionOnH1(cohomRecord, module, n, S, L, homSL, P)
#
# Compute the action on H^1 of an element n from N_P(S) ∩ N_P(M) that is
# OUTSIDE S. This gives the "outer automorphism" action that produces
# non-trivial orbits on H^1.
#
# The key insight: Elements inside S (more precisely, in S·M) act by inner
# automorphisms, which are trivial on H^1. Elements outside S give the
# non-trivial outer automorphism action.
#
# The action formula for outer element n on cocycle f: G -> M_bar is:
#   (f^n)(g) = n^(-1) * f(g^n) * n  (conjugation in the ambient)
#
# For a cocycle defined on generators g_i of G = Q/M_bar:
#   1. Get preimage of g_i in S via homSL^(-1): gi_S
#   2. Conjugate gi_S by n in P: gi_S^n = n^(-1) * gi_S * n
#   3. Since n normalizes S, gi_S^n is in S
#   4. Map gi_S^n to Q via homSL: gi_Q_conj
#   5. Project to G = Q/M_bar via quotientHom: g_conj
#   6. Evaluate f at g_conj
#   7. Conjugate result by n in M_bar (M_bar is n-invariant since n normalizes M)
#
# Input:
#   cohomRecord - CohomologyRecord from ComputeH1
#   module      - GModuleRecord with quotientHom, preimageGens, pcgsM
#   n           - outer element in N_P(S) ∩ N_P(M), with n not in S
#   S           - the subgroup S (preimage of Q under the layer quotient)
#   L           - the kernel L of the layer homomorphism (S/L = Q)
#   homSL       - the natural homomorphism S -> S/L = Q
#   P           - the ambient direct product
#
# Returns: dimH1 x dimH1 matrix over GF(p) representing n's action on H^1
###############################################################################

ComputeOuterActionOnH1 := function(cohomRecord, module, n, S, L, homSL, P)
    local dimH1, field, ngens, dim, Q, M_bar, quotientHom, G, pcgsM,
          mat, i, basisVec, fullCocycle, transformedCocycle, newCoords,
          cocycleValues, j, gi_Q, gi_S, gi_S_conj, gi_Q_conj, g_conj,
          fval, fval_conj, nInv, actionMatM,
          m, m_S, m_S_conj, m_Q_conj, exps,
          translationCocycle, translationH1, usePcgs, pcgsG,
          useSection, baseSection, cocycleSection,
          s_conj, s_conj_S, rho_s_conj_S, rho_s_conj_Q,
          delta_elem, delta_exps, exps_g, word_g, w, kk;

    dimH1 := cohomRecord.H1Dimension;
    field := module.field;

    if dimH1 = 0 then
        return rec(matrix := [], translation := []);
    fi;

    ngens := Length(module.generators);
    dim := module.dimension;
    Q := module.ambientGroup;  # This is S/L
    M_bar := module.moduleGroup;  # The module M/L in Q (M_bar)
    quotientHom := module.quotientHom;  # Q -> Q/M_bar = G
    G := ImagesSource(quotientHom);
    pcgsM := module.pcgsM;

    nInv := n^(-1);

    # Compute n's conjugation action matrix on M_bar
    # actionMatM represents α_{n^{-1}} (conjugation by n^{-1}) on M_bar
    # consistent with the n^{-1} action convention used throughout
    actionMatM := NullMat(dim, dim, field);
    for i in [1..dim] do
        m := pcgsM[i];
        m_S := PreImagesRepresentative(homSL, m);
        m_S_conj := m_S^n;  # n^{-1} * m * n in GAP
        m_Q_conj := Image(homSL, m_S_conj);
        exps := ExponentsOfPcElement(pcgsM, m_Q_conj);
        for j in [1..dim] do
            actionMatM[i][j] := exps[j] * One(field);
        od;
    od;

    # Determine if we can use Pcgs for section lift computation
    usePcgs := false;
    useSection := false;
    baseSection := fail;
    pcgsG := fail;
    if CanEasilyComputePcgs(G) then
        pcgsG := Pcgs(G);
        if ngens = Length(pcgsG) and ForAll([1..ngens],
                kk -> module.generators[kk] = pcgsG[kk]) then
            usePcgs := true;
        fi;
    fi;

    # For non-solvable G, FactorizationInGenerators uses IsomorphismFpGroupByGenerators
    # which is extremely expensive. Try a section-homomorphism action instead.
    if not usePcgs then
        if H1_OUTER_SECTION_ACTION then
            baseSection := H1BaseSectionHom(module);
            if baseSection <> fail then
                useSection := true;
            else
                return fail;
            fi;
        else
            return fail;
        fi;
    fi;

    # Compute translation (affine part of the H^1 action).
    # The H^1 action is affine: v -> v * mat + translation.
    # The translation comes from the section discrepancy:
    #   δ(g_j) = s(g_j)^{-1} * α_{n^{-1}}(s(φ(g_j)))
    # where φ is the automorphism of G induced by n.
    translationCocycle := ListWithIdenticalEntries(ngens * dim, Zero(field));

    for j in [1..ngens] do
        gi_Q := module.preimageGens[j];
        gi_S := PreImagesRepresentative(homSL, gi_Q);

        # Compute φ(g_j) via forward conjugation by n
        gi_S_conj := gi_S^nInv;  # n * gi_S * n^{-1} in GAP
        gi_Q_conj := Image(homSL, gi_S_conj);
        g_conj := Image(quotientHom, gi_Q_conj);  # φ(g_j) in G

        # Compute section lift s(φ(g_j)) in C_0 ⊆ Q
        if g_conj = One(G) then
            s_conj := One(Q);
        elif usePcgs then
            exps_g := ExponentsOfPcElement(pcgsG, g_conj);
            s_conj := One(Q);
            for kk in [1..ngens] do
                if exps_g[kk] <> 0 then
                    s_conj := s_conj * module.preimageGens[kk]^exps_g[kk];
                fi;
            od;
        elif useSection then
            s_conj := PreImagesRepresentative(baseSection.hom, g_conj);
            if s_conj = fail then
                return fail;
            fi;
        else
            word_g := FactorizationInGenerators(G, g_conj, module.generators);
            s_conj := One(Q);
            for w in word_g do
                s_conj := s_conj * module.preimageGens[w[1]]^w[2];
            od;
        fi;

        # Compute α_{n^{-1}}(s(φ(g_j))) = (n^{-1}) * s(φ(g_j)) * n
        s_conj_S := PreImagesRepresentative(homSL, s_conj);
        rho_s_conj_S := s_conj_S^n;  # n^{-1} * s_conj_S * n in GAP
        rho_s_conj_Q := Image(homSL, rho_s_conj_S);

        # δ(g_j) = s(g_j)^{-1} * α_{n^{-1}}(s(φ(g_j))) ∈ M_bar
        delta_elem := gi_Q^(-1) * rho_s_conj_Q;

        # Express in pcgsM coordinates
        delta_exps := ExponentsOfPcElement(pcgsM, delta_elem);
        for kk in [1..dim] do
            translationCocycle[(j-1)*dim + kk] := delta_exps[kk] * One(field);
        od;
    od;

    # Project translation to H^1 coordinates
    translationH1 := ProjectToH1Coordinates(cohomRecord, translationCocycle);

    # Compute linear matrix (action of n^{-1} on H^1 basis vectors)
    mat := NullMat(dimH1, dimH1, field);

    for i in [1..dimH1] do
        # Get the i-th H^1 basis element as a full cocycle
        basisVec := ListWithIdenticalEntries(dimH1, Zero(field));
        basisVec[i] := One(field);
        fullCocycle := H1CoordsToFullCocycle(cohomRecord, basisVec);

        # Get cocycle values f(g_j) for each generator g_j
        cocycleValues := CocycleVectorToValues(fullCocycle, module);
        if useSection then
            cocycleSection := H1SectionHomFromCocycle(module, fullCocycle);
            if cocycleSection = fail then
                return fail;
            fi;
        fi;

        # Compute transformed cocycle (linear part only)
        transformedCocycle := ListWithIdenticalEntries(ngens * dim, Zero(field));

        for j in [1..ngens] do
            gi_Q := module.preimageGens[j];
            gi_S := PreImagesRepresentative(homSL, gi_Q);

            # Compute φ(g_j) (same direction as translation computation)
            gi_S_conj := gi_S^nInv;
            gi_Q_conj := Image(homSL, gi_S_conj);
            g_conj := Image(quotientHom, gi_Q_conj);

            # Evaluate f at φ(g_j)
            if useSection then
                fval := H1EvaluateCocycleViaSections(module, baseSection, cocycleSection, g_conj);
                if fval = fail then
                    return fail;
                fi;
            else
                fval := EvaluateCocycleForElement(module, cocycleValues, g_conj);
            fi;

            # Apply n^{-1} action on M_bar
            fval_conj := fval * actionMatM;

            # Store in transformed cocycle vector
            transformedCocycle{[(j-1)*dim + 1 .. j*dim]} := fval_conj;
        od;

        # Project back to H^1 coordinates
        newCoords := ProjectToH1Coordinates(cohomRecord, transformedCocycle);

        # This gives the i-th row of the action matrix
        mat[i] := newCoords;
    od;

    return rec(matrix := mat, translation := translationH1);
end;

###############################################################################
# BuildH1ActionRecord(cohomRecord, module, normalizerGens)
#
# Build a complete record for the normalizer action on H^1.
#
# Input:
#   cohomRecord    - CohomologyRecord from ComputeH1
#   module         - GModuleRecord
#   normalizerGens - generators of the normalizer (preimages in ambient Q)
#
# Returns: Record with action matrices and other data for orbit computation
#          Returns fail if any matrix computation fails
###############################################################################

BuildH1ActionRecord := function(cohomRecord, module, normalizerGens)
    local dimH1, field, p, actionMatrices, gen, mat, validMatrices;

    dimH1 := cohomRecord.H1Dimension;
    field := module.field;
    p := module.p;

    if dimH1 = 0 then
        return rec(
            dimension := 0,
            field := field,
            p := p,
            matrices := [],
            normalizerGens := normalizerGens,
            cohomRecord := cohomRecord,
            module := module
        );
    fi;

    # Compute action matrix for each normalizer generator
    actionMatrices := [];
    validMatrices := true;

    for gen in normalizerGens do
        mat := ComputeH1ActionMatrix(cohomRecord, module, gen);

        # Check for failure
        if mat = fail or mat = [] or Length(mat) <> dimH1 then
            validMatrices := false;
            break;
        fi;

        # Check matrix is invertible (has correct dimensions and is a matrix)
        if not IsList(mat) or not ForAll(mat, row -> IsList(row) and Length(row) = dimH1) then
            validMatrices := false;
            break;
        fi;

        Add(actionMatrices, mat);
    od;

    if not validMatrices then
        return fail;
    fi;

    return rec(
        dimension := dimH1,
        field := field,
        p := p,
        matrices := actionMatrices,
        normalizerGens := normalizerGens,
        cohomRecord := cohomRecord,
        module := module
    );
end;

###############################################################################
# VectorToIndex(vec, p)
#
# Convert a vector over GF(p) to a unique integer index for O(1) lookup.
# Uses p-adic representation: sum(v[i] * p^(i-1))
###############################################################################

VectorToIndex := function(vec, p)
    local idx, i;

    idx := 0;
    for i in [1..Length(vec)] do
        idx := idx + IntFFE(vec[i]) * p^(i-1);
    od;

    return idx + 1;  # 1-indexed
end;

###############################################################################
# IndexToVector(idx, dim, p)
#
# Convert an integer index back to a vector over GF(p).
###############################################################################

IndexToVector := function(idx, dim, p)
    local vec, i, val, field;

    field := GF(p);
    vec := [];
    val := idx - 1;  # Convert to 0-indexed

    for i in [1..dim] do
        Add(vec, (val mod p) * One(field));
        val := QuoInt(val, p);
    od;

    return vec;
end;

###############################################################################
# ComputeH1OrbitsExplicit(H1actionRecord)
#
# Compute orbits of the normalizer action on H^1 using explicit BFS.
# For small H^1 (|H^1| <= threshold), enumerate all points.
#
# Returns: List of orbit representatives (vectors in GF(p)^dimH1)
###############################################################################

ComputeH1OrbitsExplicit := function(H1actionRecord)
    local dimH1, p, field, totalPoints, visited, orbitReps, queue,
          current, idx, mat, matInv, neighbor, neighborIdx, i, j,
          startIdx, startVec, trans, hasTranslations, zeroVec;

    dimH1 := H1actionRecord.dimension;
    p := H1actionRecord.p;
    field := H1actionRecord.field;

    if dimH1 = 0 then
        return [[]];  # Single trivial orbit
    fi;

    totalPoints := p^dimH1;
    visited := BlistList([1..totalPoints], []);  # Boolean array for visited
    orbitReps := [];

    # Check if we have affine translations
    hasTranslations := IsBound(H1actionRecord.translations)
                       and Length(H1actionRecord.translations) > 0;
    zeroVec := ListWithIdenticalEntries(dimH1, Zero(field));

    # BFS over all points
    for startIdx in [1..totalPoints] do
        if visited[startIdx] then
            continue;
        fi;

        # Start new orbit
        startVec := IndexToVector(startIdx, dimH1, p);
        Add(orbitReps, startVec);

        # BFS to mark all points in this orbit
        queue := [startVec];
        visited[startIdx] := true;

        while Length(queue) > 0 do
            current := Remove(queue, 1);

            # Apply each generator and its inverse
            for i in [1..Length(H1actionRecord.matrices)] do
                mat := H1actionRecord.matrices[i];

                # Skip invalid matrices
                if mat = fail or mat = [] then
                    continue;
                fi;

                # Get translation (zero if no translations)
                if hasTranslations then
                    trans := H1actionRecord.translations[i];
                else
                    trans := zeroVec;
                fi;

                # Forward affine action: v -> v * mat + trans
                neighbor := current * mat + trans;
                neighborIdx := VectorToIndex(neighbor, p);
                if not visited[neighborIdx] then
                    visited[neighborIdx] := true;
                    Add(queue, neighbor);
                fi;

                # Inverse affine action: v -> (v - trans) * mat^{-1}
                matInv := mat^(-1);
                if matInv <> fail then
                    neighbor := (current - trans) * matInv;
                    neighborIdx := VectorToIndex(neighbor, p);
                    if not visited[neighborIdx] then
                        visited[neighborIdx] := true;
                        Add(queue, neighbor);
                    fi;
                fi;
            od;
        od;
    od;

    return orbitReps;
end;

###############################################################################
# ComputeH1OrbitsMatrixGroup(H1actionRecord)
#
# Compute orbits using GAP's matrix group orbit algorithms.
# For large H^1, this is more efficient than explicit BFS.
#
# Returns: List of orbit representatives (vectors in GF(p)^dimH1)
###############################################################################

ComputeH1OrbitsMatrixGroup := function(H1actionRecord)
    local dimH1, p, field, matGroup, allVectors, orbitReps, orbits,
          orbit, rep, i, gens, seen, v, o,
          hasTranslations, augDim, augGens, augMat, mat, trans, kk,
          augVectors, augOrbit, zeroVec;

    dimH1 := H1actionRecord.dimension;
    p := H1actionRecord.p;
    field := H1actionRecord.field;

    if dimH1 = 0 then
        return [[]];
    fi;

    # Handle trivial action (no generators or identity matrices)
    if Length(H1actionRecord.matrices) = 0 then
        # Every point is its own orbit
        return List([0..p^dimH1-1], i -> IndexToVector(i+1, dimH1, p));
    fi;

    # Check if we have affine translations
    hasTranslations := IsBound(H1actionRecord.translations)
                       and Length(H1actionRecord.translations) > 0;

    if hasTranslations then
        # Use augmented (dimH1+1)-dimensional matrices for affine action
        # Affine map v -> v*A + t is encoded as [v,1] * [[A,0],[t,1]]
        augDim := dimH1 + 1;
        augGens := [];

        for i in [1..Length(H1actionRecord.matrices)] do
            mat := H1actionRecord.matrices[i];
            trans := H1actionRecord.translations[i];

            augMat := NullMat(augDim, augDim, field);
            # Top-left block: the linear matrix A
            for kk in [1..dimH1] do
                augMat[kk]{[1..dimH1]} := mat[kk];
            od;
            # Bottom-left block: the translation vector t
            augMat[augDim]{[1..dimH1]} := trans;
            # Bottom-right: 1
            augMat[augDim][augDim] := One(field);
            # Top-right column: already 0 from NullMat

            Add(augGens, augMat);
        od;

        # Filter out identity matrices
        gens := Filtered(augGens, m -> m <> IdentityMat(augDim, field));

        if Length(gens) = 0 then
            return List([0..p^dimH1-1], i -> IndexToVector(i+1, dimH1, p));
        fi;

        matGroup := Group(gens);

        # Points are [v, 1] for each v ∈ GF(p)^dimH1
        augVectors := List([1..p^dimH1], function(idx)
            local vec;
            vec := IndexToVector(idx, dimH1, p);
            return Concatenation(vec, [One(field)]);
        end);

        # Compute orbits using OnRight
        orbitReps := [];
        seen := BlistList([1..p^dimH1], []);

        for v in augVectors do
            i := VectorToIndex(v{[1..dimH1]}, p);
            if seen[i] then
                continue;
            fi;

            augOrbit := Orbit(matGroup, v, OnRight);

            for o in augOrbit do
                seen[VectorToIndex(o{[1..dimH1]}, p)] := true;
            od;

            Add(orbitReps, v{[1..dimH1]});
        od;

        return orbitReps;
    fi;

    # Pure linear action (no translations)
    # Create matrix group from action matrices
    gens := Filtered(H1actionRecord.matrices, m -> m <> IdentityMat(dimH1, field));

    if Length(gens) = 0 then
        # Trivial action - every point is its own orbit
        return List([0..p^dimH1-1], i -> IndexToVector(i+1, dimH1, p));
    fi;

    matGroup := Group(gens);

    # Use GAP's Orbits function with OnRight action
    allVectors := List([1..p^dimH1], i -> IndexToVector(i, dimH1, p));

    # Compute orbits
    orbitReps := [];
    seen := BlistList([1..p^dimH1], []);

    for v in allVectors do
        i := VectorToIndex(v, p);
        if seen[i] then
            continue;
        fi;

        # Compute orbit of v
        orbit := Orbit(matGroup, v, OnRight);

        # Mark all points in orbit as seen
        for o in orbit do
            seen[VectorToIndex(o, p)] := true;
        od;

        # Add representative (the first point, v)
        Add(orbitReps, v);
    od;

    return orbitReps;
end;

###############################################################################
# ComputeH1Orbits(H1actionRecord)
#
# Dispatch to appropriate orbit computation method based on |H^1| size.
#
# Returns: List of orbit representatives
###############################################################################

ComputeH1Orbits := function(H1actionRecord)
    local dimH1, p, totalPoints;

    dimH1 := H1actionRecord.dimension;
    p := H1actionRecord.p;

    if dimH1 = 0 then
        return [[]];
    fi;

    totalPoints := p^dimH1;

    # Use explicit BFS for small H^1, matrix group orbits for larger
    if totalPoints <= 10000 then
        return ComputeH1OrbitsExplicit(H1actionRecord);
    else
        return ComputeH1OrbitsMatrixGroup(H1actionRecord);
    fi;
end;

###############################################################################
# ComputeNormalizerPreimageGens(N, M_bar, Q)
#
# Get generators for N acting on H^1, returning elements in Q (not the quotient).
# Elements of M_bar act by coboundaries (trivially on H^1), so we filter those out.
#
# Input:
#   N     - normalizer in ambient group (subset of Q)
#   M_bar - the module (normal subgroup of Q)
#   Q     - the ambient group containing M_bar
#
# Returns: List of normalizer generators in Q (preimages, not quotient elements)
###############################################################################

ComputeNormalizerPreimageGens := function(N, M_bar, Q)
    local gensN, result, gen;

    gensN := GeneratorsOfGroup(N);
    result := [];

    for gen in gensN do
        # Filter out elements of M_bar (they act trivially on H^1)
        if not gen in M_bar then
            Add(result, gen);
        fi;
    od;

    return result;
end;

###############################################################################
# BuildH1ActionRecordFromOuterNorm(cohomRecord, module, outerNormGens, S, L, homSL, P)
#
# Build H^1 action record using OUTER normalizer generators.
# These are elements of N_P(S) ∩ N_P(M) that are OUTSIDE S.
# They provide the non-trivial outer automorphism action on H^1.
#
# Input:
#   cohomRecord    - CohomologyRecord from ComputeH1
#   module         - GModuleRecord
#   outerNormGens  - generators from N_P(S) ∩ N_P(M) that are outside S
#   S              - the subgroup S (preimage of Q)
#   L              - the kernel L (S/L = Q)
#   homSL          - natural homomorphism S -> S/L = Q
#   P              - the ambient direct product
#
# Returns: Record with action matrices for orbit computation, or fail
###############################################################################

BuildH1ActionRecordFromOuterNorm := function(cohomRecord, module, outerNormGens, S, L, homSL, P)
    local dimH1, field, p, actionMatrices, actionTranslations, gen,
          result, mat, trans, validMatrices, isIdentity, isZeroTrans;

    dimH1 := cohomRecord.H1Dimension;
    field := module.field;
    p := module.p;

    if dimH1 = 0 then
        return rec(
            dimension := 0,
            field := field,
            p := p,
            matrices := [],
            translations := [],
            normalizerGens := outerNormGens,
            cohomRecord := cohomRecord,
            module := module
        );
    fi;

    # Compute action (matrix + translation) for each outer normalizer generator
    actionMatrices := [];
    actionTranslations := [];
    validMatrices := true;

    for gen in outerNormGens do
        result := ComputeOuterActionOnH1(cohomRecord, module, gen, S, L, homSL, P);

        # Check for failure
        if not IsRecord(result) or not IsBound(result.matrix) then
            validMatrices := false;
            break;
        fi;

        mat := result.matrix;
        trans := result.translation;

        if mat = fail or mat = [] or Length(mat) <> dimH1 then
            validMatrices := false;
            break;
        fi;

        # Check matrix has correct dimensions
        if not IsList(mat) or not ForAll(mat, row -> IsList(row) and Length(row) = dimH1) then
            validMatrices := false;
            break;
        fi;

        # An affine action is non-trivial if either matrix != identity OR translation != 0
        isIdentity := (mat = IdentityMat(dimH1, field));
        isZeroTrans := ForAll(trans, x -> x = Zero(field));
        if not (isIdentity and isZeroTrans) then
            Add(actionMatrices, mat);
            Add(actionTranslations, trans);
        fi;
    od;

    if not validMatrices then
        return fail;
    fi;

    return rec(
        dimension := dimH1,
        field := field,
        p := p,
        matrices := actionMatrices,
        translations := actionTranslations,
        normalizerGens := outerNormGens,
        cohomRecord := cohomRecord,
        module := module
    );
end;

###############################################################################
# GetH1OrbitRepresentatives(Q, M_bar, outerNormGens, S, L, homSL, P)
#
# Main entry point for Phase 2 optimization with OUTER normalizer action.
# Compute H^1 orbits under outer automorphism action and return one complement
# per orbit.
#
# The key insight: Inner automorphisms (elements of S acting on H^1) are
# trivial on cohomology H^1. To get non-trivial orbits, we need OUTER
# automorphisms from N_P(S) ∩ N_P(M) that are outside S.
#
# Input:
#   Q             - the quotient group S/L (ambient of complements)
#   M_bar         - elementary abelian normal subgroup (the module M/L)
#   outerNormGens - generators of outer normalizer (in P, outside S)
#   S             - the subgroup being lifted
#   L             - the kernel of the layer homomorphism
#   homSL         - natural homomorphism S -> S/L = Q
#   P             - the ambient direct product
#
# Returns: List of complement subgroups (one per P-conjugacy class orbit)
###############################################################################

GetH1OrbitRepresentatives := function(arg)
    local Q, M_bar, outerNormGens, S, L, homSL, P,
          startTime, module, H1, complementInfo, G,
          normGens, H1action, orbitReps, complements, rep,
          cocycleVec, C, invalidCount, numOrbits, fullCount,
          useOuterNorm, fpfFilterFunc, numFPFRejected,
          t0_prof;

    # Handle both old signature (Q, M_bar, ambient) and new signature
    # (Q, M_bar, outerNormGens, S, L, homSL, P [, fpfFilter])
    Q := arg[1];
    M_bar := arg[2];
    fpfFilterFunc := fail;  # OPT 5: Optional FPF filter

    if Length(arg) = 3 then
        # Old signature: (Q, M_bar, ambient) - use inner action (trivial)
        outerNormGens := [];
        S := fail;
        L := fail;
        homSL := fail;
        P := arg[3];
        useOuterNorm := false;
    elif Length(arg) >= 7 then
        # New signature with outer normalizer info
        outerNormGens := arg[3];
        S := arg[4];
        L := arg[5];
        homSL := arg[6];
        P := arg[7];
        useOuterNorm := Length(outerNormGens) > 0;
        # OPT 5: Accept optional FPF filter function as 8th argument
        if Length(arg) >= 8 then
            fpfFilterFunc := arg[8];
        fi;
    else
        Error("GetH1OrbitRepresentatives: invalid number of arguments");
    fi;

    startTime := Runtime();

    # Handle trivial M_bar
    if Size(M_bar) = 1 then
        H1_ORBITAL_STATS.skipped_trivial := H1_ORBITAL_STATS.skipped_trivial + 1;
        return [Q];
    fi;

    # Check if module is elementary abelian
    if not IsElementaryAbelian(M_bar) then
        Error("GetH1OrbitRepresentatives requires elementary abelian M_bar");
    fi;

    # Create module
    t0_prof := Runtime();
    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
    H1_ORBITAL_STATS.t_module := H1_ORBITAL_STATS.t_module + (Runtime() - t0_prof);

    # Handle various failure modes from ChiefFactorAsModule
    if IsRecord(module) and IsBound(module.isNonSplit) and module.isNonSplit then
        Info(InfoWarning, 2, "GetH1OrbitRepresentatives: non-split extension");
        return [];
    fi;

    if IsRecord(module) and IsBound(module.isModuleConstructionFailed) then
        Info(InfoWarning, 1, "GetH1OrbitRepresentatives: module construction failed");
        return module.foundComplements;
    fi;

    if module = fail then
        Info(InfoWarning, 1, "GetH1OrbitRepresentatives: module construction failed (legacy)");
        return ComplementClassesRepresentatives(Q, M_bar);
    fi;

    # Compute H^1
    t0_prof := Runtime();
    H1 := CachedComputeH1(module);
    H1_ORBITAL_STATS.t_h1 := H1_ORBITAL_STATS.t_h1 + (Runtime() - t0_prof);

    # Handle trivial H^1 (unique complement)
    if H1.H1Dimension = 0 then
        complementInfo := BuildComplementInfo(Q, M_bar, module);
        C := CocycleToComplement(H1.H1Representatives[1], complementInfo);
        H1_ORBITAL_STATS.skipped_trivial := H1_ORBITAL_STATS.skipped_trivial + 1;
        return [C];
    fi;

    fullCount := H1.numComplements;

    # Build H^1 action record
    t0_prof := Runtime();
    if useOuterNorm then
        # Use outer normalizer action (potentially non-trivial on H^1)
        H1action := BuildH1ActionRecordFromOuterNorm(H1, module, outerNormGens, S, L, homSL, P);

        if H1action = fail then
            Info(InfoWarning, 1, "GetH1OrbitRepresentatives: BuildH1ActionRecordFromOuterNorm failed");
            complementInfo := BuildComplementInfo(Q, M_bar, module);
            return EnumerateComplementsFromH1(H1, complementInfo);
        fi;

        # Check if we actually have any non-identity action matrices
        if Length(H1action.matrices) = 0 then
            # Trivial outer action - every cocycle is its own orbit
            Info(InfoWarning, 2, "GetH1OrbitRepresentatives: outer action is trivial");
            complementInfo := BuildComplementInfo(Q, M_bar, module);
            return EnumerateComplementsFromH1(H1, complementInfo);
        fi;
    else
        # Old behavior: use inner action (which is trivial on H^1)
        # This path is for backward compatibility
        normGens := ComputeNormalizerPreimageGens(Q, M_bar, Q);

        if Length(normGens) = 0 then
            Info(InfoWarning, 2, "GetH1OrbitRepresentatives: trivial normalizer action");
            complementInfo := BuildComplementInfo(Q, M_bar, module);
            return EnumerateComplementsFromH1(H1, complementInfo);
        fi;

        H1action := BuildH1ActionRecord(H1, module, normGens);

        if H1action = fail then
            Info(InfoWarning, 2, "GetH1OrbitRepresentatives: BuildH1ActionRecord failed");
            complementInfo := BuildComplementInfo(Q, M_bar, module);
            return EnumerateComplementsFromH1(H1, complementInfo);
        fi;
    fi;

    H1_ORBITAL_STATS.t_action := H1_ORBITAL_STATS.t_action + (Runtime() - t0_prof);

    # Compute orbits
    t0_prof := Runtime();
    orbitReps := ComputeH1Orbits(H1action);
    numOrbits := Length(orbitReps);

    H1_ORBITAL_STATS.t_orbits := H1_ORBITAL_STATS.t_orbits + (Runtime() - t0_prof);

    # Convert orbit representatives to complements
    # OPT 5: Apply FPF filter during conversion to avoid expensive complement
    # construction for non-FPF orbit reps
    t0_prof := Runtime();
    complementInfo := BuildComplementInfo(Q, M_bar, module);
    complements := [];
    invalidCount := 0;
    numFPFRejected := 0;

    for rep in orbitReps do
        # Convert H^1 coordinates to full cocycle
        cocycleVec := H1CoordsToFullCocycle(H1, rep);

        # Convert to complement
        C := CocycleToComplement(cocycleVec, complementInfo);

        # Validate complement
        if Size(C) * Size(M_bar) <> Size(Q) then
            invalidCount := invalidCount + 1;
            continue;
        fi;

        if Size(Intersection(C, M_bar)) > 1 then
            invalidCount := invalidCount + 1;
            continue;
        fi;

        # OPT 5: Apply FPF filter if provided
        if fpfFilterFunc <> fail then
            if not fpfFilterFunc(C) then
                numFPFRejected := numFPFRejected + 1;
                continue;
            fi;
        fi;

        Add(complements, C);
    od;

    H1_ORBITAL_STATS.t_convert := H1_ORBITAL_STATS.t_convert + (Runtime() - t0_prof);

    # Update statistics
    H1_ORBITAL_STATS.calls := H1_ORBITAL_STATS.calls + 1;
    H1_ORBITAL_STATS.total_orbits := H1_ORBITAL_STATS.total_orbits + numOrbits;
    H1_ORBITAL_STATS.total_points := H1_ORBITAL_STATS.total_points + fullCount;
    H1_ORBITAL_STATS.orbit_time := H1_ORBITAL_STATS.orbit_time + (Runtime() - startTime);



    # If any complements failed validation, fall back to standard method
    if invalidCount > 0 then
        Info(InfoWarning, 1, "GetH1OrbitRepresentatives: ", invalidCount,
             " of ", numOrbits, " orbit reps invalid (|Q|=", Size(Q),
             " |M_bar|=", Size(M_bar), " |G|=", Size(module.group),
             "), falling back");
        complementInfo := BuildComplementInfo(Q, M_bar, module);
        complements := EnumerateComplementsFromH1(H1, complementInfo);

        if complements = fail then
            Info(InfoWarning, 1, "GetH1OrbitRepresentatives: EnumerateComplementsFromH1 also failed, using GAP");
            return ComplementClassesRepresentatives(Q, M_bar);
        fi;
        return complements;
    fi;

    return complements;
end;

###############################################################################
# GetComplementsWithOrbits(Q, M_bar, ambient)
#
# Wrapper that decides whether to use orbital optimization.
# Falls back to standard GetComplementsViaH1 if orbital optimization is disabled
# or if conditions aren't favorable.
#
# Input:
#   Q       - the quotient group S/L
#   M_bar   - elementary abelian normal subgroup
#   ambient - the larger ambient group P (optional, for normalizer)
#
# Returns: List of complement subgroups (one per conjugacy class)
###############################################################################

GetComplementsWithOrbits := function(arg)
    local Q, M_bar, ambient, useOrbital;

    Q := arg[1];
    M_bar := arg[2];

    if Length(arg) >= 3 then
        ambient := arg[3];
    else
        ambient := Q;  # No larger ambient, normalizer is Q itself
    fi;

    # Decide whether to use orbital optimization
    useOrbital := USE_H1_ORBITAL and
                  IsElementaryAbelian(M_bar) and
                  Size(M_bar) > 1;

    # Only use orbital when H^1 is expected to be large enough to benefit
    # and there's a non-trivial ambient for normalizer
    if useOrbital and Size(ambient) > Size(Q) then
        return GetH1OrbitRepresentatives(Q, M_bar, ambient);
    fi;

    # Fall back to standard method
    return GetComplementsViaH1(Q, M_bar);
end;

###############################################################################
# Statistics Functions
###############################################################################

PrintH1OrbitalStats := function()
    local avgOrbits, avgPoints, reduction;

    Print("\n========== H^1 Orbital Statistics ==========\n");
    Print("Orbital method calls:  ", H1_ORBITAL_STATS.calls, "\n");
    Print("Total orbits computed: ", H1_ORBITAL_STATS.total_orbits, "\n");
    Print("Total H^1 points:      ", H1_ORBITAL_STATS.total_points, "\n");
    Print("Trivial cases skipped: ", H1_ORBITAL_STATS.skipped_trivial, "\n");
    Print("Total orbit time:      ", H1_ORBITAL_STATS.orbit_time / 1000.0, "s\n");

    if H1_ORBITAL_STATS.calls > 0 then
        avgOrbits := Float(H1_ORBITAL_STATS.total_orbits) / Float(H1_ORBITAL_STATS.calls);
        avgPoints := Float(H1_ORBITAL_STATS.total_points) / Float(H1_ORBITAL_STATS.calls);
        reduction := 1.0 - Float(H1_ORBITAL_STATS.total_orbits) / Float(H1_ORBITAL_STATS.total_points);
        Print("Avg orbits per call:   ", avgOrbits, "\n");
        Print("Avg points per call:   ", avgPoints, "\n");
        Print("Reduction factor:      ", reduction * 100.0, "%\n");
    fi;
    Print("=============================================\n");
end;

ResetH1OrbitalStats := function()
    H1_ORBITAL_STATS.calls := 0;
    H1_ORBITAL_STATS.total_orbits := 0;
    H1_ORBITAL_STATS.total_points := 0;
    H1_ORBITAL_STATS.orbit_time := 0;
    H1_ORBITAL_STATS.skipped_trivial := 0;
end;

###############################################################################

Print("H^1 Orbital Complement Enumeration (Phase 2) loaded.\n");
Print("====================================================\n");
Print("Main: GetH1OrbitRepresentatives(Q, M_bar, ambient)\n");
Print("Wrapper: GetComplementsWithOrbits(Q, M_bar [, ambient])\n");
Print("Stats: PrintH1OrbitalStats(), ResetH1OrbitalStats()\n");
Print("Config: USE_H1_ORBITAL (", USE_H1_ORBITAL, ")\n\n");
