###############################################################################
#
# modules.g - G-Module Construction for Cohomology Computations
#
# Provides functions to create GModuleRecords from chief factors and
# set up data for converting cocycles to complements.
#
###############################################################################

# Ensure cohomology.g is loaded
if not IsBound(CreateGModuleRecord) then
    Read("C:/Users/jeffr/Downloads/Lifting/cohomology.g");
fi;

###############################################################################
# ChiefFactorAsModule(Q, M_bar, N_bar)
#
# Create a GModuleRecord from a chief factor M_bar/N_bar in quotient Q.
#
# In the lifting algorithm, we have:
#   - Q = S/L where S is a subgroup and L is normal in S
#   - M_bar = Image(hom, M) is the image of chief series term M in Q
#   - N_bar = 1 typically (trivial subgroup of Q)
#
# The action is conjugation: for g in Q, m in M_bar, m^g = g^{-1} * m * g
#
# Input:
#   Q     - the ambient quotient group
#   M_bar - elementary abelian normal subgroup of Q (the module)
#   N_bar - normal subgroup of M_bar (usually trivial), module is M_bar/N_bar
#
# Returns: GModuleRecord for the quotient G = Q/M_bar acting on M_bar/N_bar
###############################################################################

ChiefFactorAsModule := function(Q, M_bar, N_bar)
    local G, p, hom, module, gens_Q, gens_G, module_group,
           standardComplement, baseComplements,
           baseComplement, newGensQ, newGensG, i, j,
           pcgsG, phi, invphi, found, imgG;

    # The acting group G is Q/M_bar (complements are subgroups mapping onto G)
    hom := SafeNaturalHomByNSG(Q, M_bar);
    if hom = fail then
        return rec(complements := [], h1dim := 0);
    fi;
    G := ImagesSource(hom);

    # For the module, we use M_bar itself (assuming N_bar is trivial)
    if Size(N_bar) > 1 then
        # Need to work with M_bar/N_bar
        Error("Non-trivial N_bar not yet supported");
    fi;

    module_group := M_bar;

    # Determine the prime p
    if not IsElementaryAbelian(module_group) then
        Error("M_bar must be elementary abelian");
    fi;

    if Size(module_group) = 1 then
        # Trivial module
        p := 2;  # Arbitrary choice for trivial module
        return rec(
            p := p,
            dimension := 0,
            field := GF(p),
            group := G,
            generators := GeneratorsOfGroup(G),
            matrices := List(GeneratorsOfGroup(G), g -> []),
            pcgsM := Pcgs(module_group),
            moduleGroup := module_group,
            quotientHom := hom,
            ambientGroup := Q,
            foundComplements := [Q]  # The whole group is the unique complement
        );
    fi;

    p := PrimePGroup(module_group);
    if p = fail then
        Error("M_bar must be an elementary abelian p-group");
    fi;

    # CRITICAL FIX: Ensure strict generator correspondence
    #
    # The cocycle-to-complement formula requires that:
    # 1. preimageGens[i] maps to module.generators[i] under quotient
    # 2. preimageGens form a valid complement (Group(preimageGens) ∩ M_bar = {1})
    #
    # We achieve this by:
    # 1. Getting an actual complement using multi-strategy approach (optimized)
    # 2. Using the complement's generators as preimageGens
    # 3. Deriving gens_G by mapping preimageGens (not the other way around!)

    # OPTIMIZATION: Multi-strategy single-complement finder
    # Instead of calling ComplementClassesRepresentatives (which finds ALL classes),
    # we use targeted strategies to find just ONE complement quickly.

    baseComplement := fail;
    baseComplements := [];  # Will store all found complements for fallback

    # Strategy 1: Coprime case (Schur-Zassenhaus)
    # When gcd(|G|, |M_bar|) = 1, complements exist and are conjugate.
    # HallSubgroup is optimized for this case.
    if baseComplement = fail and Size(G) > 1 then
        if Gcd(Size(G), Size(M_bar)) = 1 then
            # In coprime case, find Hall subgroup for primes of G
            baseComplement := HallSubgroup(Q, PrimeDivisors(Size(G)));
            if baseComplement <> fail then
                # Verify it's actually a complement
                if Size(Intersection(baseComplement, M_bar)) > 1 or
                   Size(baseComplement) <> Size(G) then
                    baseComplement := fail;
                else
                    baseComplements := [baseComplement];  # Store for fallback
                fi;
            fi;
        fi;
    fi;

    # Strategy 1.5: Section-based complement finder (avoids CCR)
    # For solvable G: use NaturalHomomorphism preimages as section.
    # Often GAP's canonical preimages already form a complement.
    # Cost: ~2ms (SubgroupNC + Intersection) vs ~17ms for CCR.
    # IMPORTANT: We do NOT set baseComplements here (only baseComplement).
    # This forces H^1 enumeration for ALL complement classes, which is correct
    # when there are multiple classes. Setting baseComplements = [one complement]
    # would cause the complement reuse fast path to return only 1 class.
    if baseComplement = fail and CanEasilyComputePcgs(G) and Size(G) > 1 then
        pcgsG := Pcgs(G);
        if pcgsG <> fail and Length(pcgsG) > 0 then
            gens_Q := List(pcgsG, g -> PreImagesRepresentative(hom, g));
            if ForAll(gens_Q, q -> not q in M_bar) then
                standardComplement := SubgroupNC(Q, gens_Q);
                if HasSize(standardComplement) or IsSolvableGroup(Q) then
                    if Size(standardComplement) = Size(G) and
                       Size(Intersection(standardComplement, M_bar)) = 1 then
                        baseComplement := standardComplement;
                        # DO NOT set baseComplements - leave empty so H^1 enumerates all classes
                    fi;
                fi;
            fi;
        fi;
    fi;

    # Strategy 1.7: General section-based complement finder (for any G)
    # Use GeneratorsOfGroup(G) preimages. Works for both solvable and non-solvable G.
    # For non-solvable G (S_n, A_n), this often succeeds because GAP's canonical
    # preimages from NaturalHomomorphism frequently form a complement.
    # Cost: ~2ms (SubgroupNC + Size + Intersection) vs ~17ms+ for CCR.
    if baseComplement = fail and Size(G) > 1 then
        gens_Q := List(GeneratorsOfGroup(G), g -> PreImagesRepresentative(hom, g));
        if ForAll(gens_Q, q -> not q in M_bar) then
            standardComplement := SubgroupNC(Q, gens_Q);
            if Size(standardComplement) = Size(G) and
               Size(Intersection(standardComplement, M_bar)) = 1 then
                baseComplement := standardComplement;
                # DO NOT set baseComplements - leave empty so H^1 enumerates all classes
            fi;
        fi;
    fi;

    # Strategy 2: Use GAP's ComplementClassesRepresentatives
    # This is robust and optimized for the single-complement case internally
    # OPT 4c: Cache complement finding - store all found complements
    if baseComplement = fail then
        baseComplements := ComplementClassesRepresentatives(Q, M_bar);
        if Length(baseComplements) = 0 then
            # Non-split extension - no complements exist
            # Return a special record indicating this
            return rec(
                isNonSplit := true,
                foundComplements := []
            );
        fi;
        baseComplement := baseComplements[1];
    fi;

    # PREFERRED: Try to use Pcgs(G) as module.generators via inverse mapping.
    # This enables the efficient Pcgs cocycle method (O(r^2) relations) instead
    # of the FP-group method which can hit coset enumeration limits for large groups.
    #
    # If this fails, fall back to SmallGeneratingSet which will use the FP-group
    # cocycle method (correct for any generating set, but slower).

    gens_Q := [];
    gens_G := [];
    found := false;

    if CanEasilyComputePcgs(G) and Size(G) > 1 then
        pcgsG := Pcgs(G);
        if pcgsG <> fail and Length(pcgsG) > 0 then
            # Build isomorphism from complement to G, then invert to get
            # preimages of Pcgs(G) elements in baseComplement
            phi := GroupHomomorphismByImages(
                baseComplement, G,
                GeneratorsOfGroup(baseComplement),
                List(GeneratorsOfGroup(baseComplement), x -> Image(hom, x))
            );

            if phi <> fail and IsBijective(phi) then
                invphi := InverseGeneralMapping(phi);
                gens_G := List(pcgsG);
                gens_Q := List(gens_G, g -> Image(invphi, g));

                # Verify all preimages are valid complement elements
                if ForAll(gens_Q, q -> q <> fail and q in baseComplement) then
                    found := true;
                else
                    gens_Q := [];
                    gens_G := [];
                fi;
            fi;
        fi;
    fi;

    # FALLBACK: Use SmallGeneratingSet (works with any generators via FP-group method)
    if not found then
        gens_Q := SmallGeneratingSet(baseComplement);
        gens_G := List(gens_Q, c -> Image(hom, c));

        # Remove trivial generators while maintaining correspondence
        newGensQ := [];
        newGensG := [];
        for j in [1..Length(gens_Q)] do
            if gens_G[j] <> One(G) then
                Add(newGensQ, gens_Q[j]);
                Add(newGensG, gens_G[j]);
            fi;
        od;
        gens_Q := newGensQ;
        gens_G := newGensG;

        # Check if generators span G
        if Length(gens_G) > 0 and Size(Group(gens_G)) = Size(G) then
            found := true;
        fi;
    fi;

    # OPT 4a: If SmallGeneratingSet failed, try GeneratorsOfGroup directly
    if not found then
        gens_Q := GeneratorsOfGroup(baseComplement);
        gens_G := List(gens_Q, c -> Image(hom, c));
        newGensQ := [];
        newGensG := [];
        for j in [1..Length(gens_Q)] do
            if gens_G[j] <> One(G) then
                Add(newGensQ, gens_Q[j]);
                Add(newGensG, gens_G[j]);
            fi;
        od;
        gens_Q := newGensQ;
        gens_G := newGensG;

        if Length(gens_G) > 0 and Size(Group(gens_G)) = Size(G) then
            found := true;
        fi;
    fi;

    # OPT 4b: Try other complement representatives if the first failed
    if not found and Length(baseComplements) > 1 then
        for i in [2..Minimum(Length(baseComplements), 5)] do
            baseComplement := baseComplements[i];

            # Try Pcgs method on this complement
            if CanEasilyComputePcgs(G) and Size(G) > 1 then
                pcgsG := Pcgs(G);
                if pcgsG <> fail and Length(pcgsG) > 0 then
                    phi := GroupHomomorphismByImages(
                        baseComplement, G,
                        GeneratorsOfGroup(baseComplement),
                        List(GeneratorsOfGroup(baseComplement), x -> Image(hom, x))
                    );
                    if phi <> fail and IsBijective(phi) then
                        invphi := InverseGeneralMapping(phi);
                        gens_G := List(pcgsG);
                        gens_Q := List(gens_G, g -> Image(invphi, g));
                        if ForAll(gens_Q, q -> q <> fail and q in baseComplement) then
                            found := true;
                            break;
                        fi;
                    fi;
                fi;
            fi;

            # Try GeneratorsOfGroup on this complement (OPT 4a: robust for non-solvable)
            if not found then
                gens_Q := GeneratorsOfGroup(baseComplement);
                gens_G := List(gens_Q, c -> Image(hom, c));
                newGensQ := [];
                newGensG := [];
                for j in [1..Length(gens_Q)] do
                    if gens_G[j] <> One(G) then
                        Add(newGensQ, gens_Q[j]);
                        Add(newGensG, gens_G[j]);
                    fi;
                od;
                gens_Q := newGensQ;
                gens_G := newGensG;
                if Length(gens_G) > 0 and Size(Group(gens_G)) = Size(G) then
                    found := true;
                    break;
                fi;
            fi;
        od;
    fi;

    # Final generator recovery: if baseComplement is genuinely a complement,
    # the restricted quotient map baseComplement -> G is an isomorphism.  Some
    # quotient/group-parent combinations nevertheless make Group(gens_G) look
    # too small for images of the complement's stored generators.  In that case,
    # generate the full image subgroup first and pull those generators back
    # through the restricted isomorphism.
    if not found then
        imgG := Image(hom, baseComplement);
        if imgG <> fail and Size(imgG) = Size(G) then
            phi := GroupHomomorphismByImages(
                baseComplement, imgG,
                GeneratorsOfGroup(baseComplement),
                List(GeneratorsOfGroup(baseComplement), x -> Image(hom, x))
            );

            if phi <> fail and IsBijective(phi) then
                invphi := InverseGeneralMapping(phi);
                gens_G := GeneratorsOfGroup(imgG);
                gens_Q := List(gens_G, g -> Image(invphi, g));

                if ForAll(gens_Q, q -> q <> fail and q in baseComplement)
                   and Length(gens_G) > 0 then
                    found := true;
                else
                    gens_Q := [];
                    gens_G := [];
                fi;
            fi;
        fi;
    fi;

    # Final fallback: if no complement worked, return failure
    if not found then
        if Length(gens_G) = 0 or (Length(gens_G) > 0 and Size(Group(gens_G)) < Size(G)) then
            Info(InfoWarning, 1, "ChiefFactorAsModule: generators insufficient after trying all complements");
            return rec(
                isModuleConstructionFailed := true,
                foundComplements := baseComplements
            );
        fi;
    fi;

    # VALIDATION: Verify generator correspondence
    # Each gens_Q[i] must map to gens_G[i] under the quotient homomorphism
    for i in [1..Length(gens_Q)] do
        if Image(hom, gens_Q[i]) <> gens_G[i] then
            Info(InfoWarning, 1, "ChiefFactorAsModule: generator correspondence broken at index ", i);
            return rec(
                isModuleConstructionFailed := true,
                foundComplements := baseComplements
            );
        fi;
    od;

    # VALIDATION: Verify that gens_Q actually form a complement
    if Length(gens_Q) > 0 then
        standardComplement := Group(gens_Q);
        if Size(Intersection(standardComplement, M_bar)) > 1 then
            Info(InfoWarning, 1, "ChiefFactorAsModule: preimageGens do not form a complement!");
            return rec(
                isModuleConstructionFailed := true,
                foundComplements := baseComplements
            );
        fi;
    fi;

    # Now create the module with Q acting on M_bar via conjugation
    # The generators correspond exactly: gens_G[i] <-> gens_Q[i]
    module := CreateGModuleRecordViaPreimagesWithGens(G, gens_G, module_group, p, gens_Q);

    # Store additional data for complement conversion
    module.quotientHom := hom;
    module.ambientGroup := Q;
    module.preimageGens := gens_Q;
    # OPT 4c: Cache all found complements for reuse in GetComplementsViaH1
    module.foundComplements := baseComplements;

    return module;
end;

###############################################################################
# CreateGModuleRecordViaPreimagesWithGens(G, gensG, M, p, preimageGens)
#
# Create a GModuleRecord where G acts on M via conjugation by preimageGens.
#
# This is used when G = Q/M_bar and we have preimages of G's generators in Q.
#
# Input:
#   G            - the acting group (abstract quotient)
#   gensG        - specific generators of G to use (should be small generating set)
#   M            - elementary abelian p-group (the module)
#   p            - the prime
#   preimageGens - elements of ambient group Q whose images generate G (corresponding to gensG)
#
# Returns: GModuleRecord
###############################################################################

CreateGModuleRecordViaPreimagesWithGens := function(G, gensG, M, p, preimageGens)
    local result, pcgsM, dim, matrices, gen, mat, m, img, exps, i, j, field;

    field := GF(p);

    # Get a Pcgs for M to use as basis
    pcgsM := Pcgs(M);
    dim := Length(pcgsM);

    # Build action matrices using conjugation by preimageGens
    matrices := [];
    for gen in preimageGens do
        mat := NullMat(dim, dim, field);
        for i in [1..dim] do
            m := pcgsM[i];
            img := m^gen;  # Conjugation action
            exps := ExponentsOfPcElement(pcgsM, img);
            for j in [1..dim] do
                mat[i][j] := exps[j] * One(field);
            od;
        od;
        Add(matrices, mat);
    od;

    result := rec(
        p := p,
        dimension := dim,
        field := field,
        group := G,
        generators := gensG,  # Use the specified generators
        matrices := matrices,
        pcgsM := pcgsM,
        moduleGroup := M
    );

    return result;
end;

###############################################################################
# CreateGModuleRecordViaPreimages(G, M, p, preimageGens)
#
# Wrapper that uses GeneratorsOfGroup(G).
###############################################################################

CreateGModuleRecordViaPreimages := function(G, M, p, preimageGens)
    return CreateGModuleRecordViaPreimagesWithGens(G, GeneratorsOfGroup(G), M, p, preimageGens);
end;

###############################################################################
# BuildComplementInfo(Q, M_bar, module)
#
# Build additional data needed to convert cocycles to complements.
#
# A complement C to M_bar in Q is isomorphic to Q/M_bar and satisfies:
#   C * M_bar = Q  and  C ∩ M_bar = 1
#
# Given a cocycle f : G -> M_bar, the complement is:
#   C_f = { g' * f(g) : g in G }
# where g' is a fixed preimage of g in Q (right-action convention).
#
# More precisely, if {g_1, ..., g_r} generate G and g_i' are their preimages,
# then C_f is generated by { f(g_i) * g_i' : i = 1..r }
#
# Input:
#   Q      - the ambient group
#   M_bar  - normal subgroup (module)
#   module - GModuleRecord from ChiefFactorAsModule
#
# Returns: ComplementInfo record
###############################################################################

BuildComplementInfo := function(Q, M_bar, module)
    local info;

    info := rec(
        Q := Q,
        M_bar := M_bar,
        module := module,
        preimageGens := module.preimageGens,
        pcgsM := module.pcgsM
    );

    return info;
end;

###############################################################################
# CocycleValueToElement(value, pcgsM, p)
#
# Convert a vector in GF(p)^dim to an element of M.
#
# Input:
#   value - vector [a_1, ..., a_n] in GF(p)^n
#   pcgsM - Pcgs of M
#   p     - the prime
#
# Returns: m = pcgsM[1]^a_1 * ... * pcgsM[n]^a_n
###############################################################################

CocycleValueToElement := function(value, pcgsM, p)
    local m, i, exp;

    m := One(pcgsM[1]);  # Identity in the group containing M

    for i in [1..Length(value)] do
        exp := IntFFE(value[i]);  # Convert GF(p) element to integer
        if exp <> 0 then
            m := m * pcgsM[i]^exp;
        fi;
    od;

    return m;
end;

###############################################################################
# CocycleToComplement(cocycleVec, complementInfo)
#
# Convert a cocycle (as vector in GF(p)^(r*n)) to a complement subgroup.
#
# Given f represented by (f(g_1), ..., f(g_r)), the complement is:
#   C_f = < g_i' * f(g_i) : i = 1..r >
#
# where g_i' is a fixed preimage of g_i in Q (from the base complement).
# Since f(g_i) is in M_bar (the kernel), g_i' * f(g_i) still maps to g_i.
# The cocycle condition ensures these generators form a subgroup isomorphic
# to G = Q/M_bar. This is the right-action convention: s_f(g) = s_0(g) * f(g).
#
# Input:
#   cocycleVec     - vector in GF(p)^(r*n) representing the cocycle
#   complementInfo - record from BuildComplementInfo
#
# Returns: Subgroup C of Q that is a complement to M_bar
###############################################################################

CocycleToComplement := function(cocycleVec, complementInfo)
    local module, ngens, dim, p, pcgsM, preimageGens, gens, i, fgi, mi, gi_prime,
          imgCheck, C;

    module := complementInfo.module;
    ngens := Length(module.generators);
    dim := module.dimension;
    p := module.p;
    pcgsM := complementInfo.pcgsM;
    preimageGens := complementInfo.preimageGens;

    # Handle trivial module case
    if dim = 0 then
        if Length(preimageGens) = 0 then
            return TrivialSubgroup(complementInfo.Q);
        fi;
        return Group(preimageGens);
    fi;

    # ASSERTION: Verify generator correspondence
    # preimageGens[i] must map to module.generators[i] under quotientHom
    if IsBound(module.quotientHom) then
        for i in [1..ngens] do
            imgCheck := Image(module.quotientHom, preimageGens[i]);
            if imgCheck <> module.generators[i] then
                Print("ERROR in CocycleToComplement: generator correspondence broken!\n");
                Print("  preimageGens[", i, "] maps to ", imgCheck,
                      " but module.generators[", i, "] = ", module.generators[i], "\n");
                Print("  |G| = ", Size(module.group), " ngens = ", ngens,
                      " dim = ", dim, " p = ", p, "\n");
                return fail;
            fi;
        od;
    fi;

    gens := [];

    for i in [1..ngens] do
        # Extract f(g_i) from the cocycle vector
        fgi := cocycleVec{[(i-1)*dim + 1 .. i*dim]};

        # Convert to module element
        mi := CocycleValueToElement(fgi, pcgsM, p);

        # Get preimage of g_i (which lies in a valid base complement)
        gi_prime := preimageGens[i];

        # Right-action cocycle convention: s_f(g) = s_0(g) * f(g)
        # where s_0 is the base section (preimageGens)
        Add(gens, gi_prime * mi);
    od;

    # Filter out identity generators
    gens := Filtered(gens, gen -> gen <> One(complementInfo.Q));

    if Length(gens) = 0 then
        return TrivialSubgroup(complementInfo.Q);
    fi;

    C := Group(gens);

    return C;
end;

###############################################################################
# PrecomputeBasisModuleElements(H1record, complementInfo)
#
# OPTIMIZATION: Precompute module elements for each basis vector of H^1.
# This avoids redundant CocycleValueToElement calls during batch generation.
#
# Returns: List of lists, where basisElements[b][i] is the module element
#          corresponding to f(g_i) for basis vector b.
###############################################################################

PrecomputeBasisModuleElements := function(H1record, complementInfo)
    local basisElements, b, basis, ngens, dim, p, pcgsM, i, fgi;

    if not IsBound(H1record.quotientBasis) or Length(H1record.quotientBasis) = 0 then
        return [];
    fi;

    ngens := Length(complementInfo.module.generators);
    dim := complementInfo.module.dimension;
    p := complementInfo.module.p;
    pcgsM := complementInfo.pcgsM;

    basisElements := [];

    for b in [1..Length(H1record.quotientBasis)] do
        basis := H1record.quotientBasis[b];
        basisElements[b] := [];
        for i in [1..ngens] do
            fgi := basis{[(i-1)*dim + 1 .. i*dim]};
            basisElements[b][i] := CocycleValueToElement(fgi, pcgsM, p);
        od;
    od;

    return basisElements;
end;

###############################################################################
# EnumerateComplementsFromH1(H1record, complementInfo)
#
# Enumerate all complement classes using H^1 representatives.
#
# Each element of H^1 gives a distinct conjugacy class of complements.
# The number of complements is |H^1| = p^(dim H^1).
#
# OPTIMIZATION: Uses batch generation with precomputed basis elements when
# quotientBasis is available, combining via group multiplication.
#
# Input:
#   H1record       - CohomologyRecord from ComputeH1
#   complementInfo - record from BuildComplementInfo
#
# Returns: List of complement subgroups (one per conjugacy class), or fail if
#          any complement fails validation (indicating a bug in cocycle computation)
###############################################################################

EnumerateComplementsFromH1 := function(H1record, complementInfo)
    local complements, cocycle, C, invalidCount, useBatch,
          basisElements, dimH1, p, ngens, preimageGens, Q, M_bar,
          allCombs, comb, gens, i, mi, b, gi_prime;

    complements := [];
    invalidCount := 0;

    # Determine if we can use batch generation
    # Use batch when quotientBasis exists and H^1 dimension > 1
    useBatch := IsBound(H1record.quotientBasis) and
                Length(H1record.quotientBasis) > 1 and
                H1record.H1Dimension > 1;

    if useBatch then
        # BATCH GENERATION: Precompute and combine
        basisElements := PrecomputeBasisModuleElements(H1record, complementInfo);

        if Length(basisElements) > 0 then
            dimH1 := H1record.H1Dimension;
            p := complementInfo.module.p;
            ngens := Length(complementInfo.module.generators);
            preimageGens := complementInfo.preimageGens;
            Q := complementInfo.Q;
            M_bar := complementInfo.M_bar;

            # Generate all p^dimH1 complements by combining basis contributions
            allCombs := Tuples([0..p-1], dimH1);

            for comb in allCombs do
                gens := [];

                for i in [1..ngens] do
                    gi_prime := preimageGens[i];

                    # Compute module element: product of basisElements[b][i]^comb[b]
                    mi := One(Q);
                    for b in [1..dimH1] do
                        if comb[b] <> 0 then
                            mi := mi * basisElements[b][i]^comb[b];
                        fi;
                    od;

                    # Right-action cocycle convention: s_f(g) = s_0(g) * f(g)
                    Add(gens, gi_prime * mi);
                od;

                # Filter out identity generators
                gens := Filtered(gens, gen -> gen <> One(Q));

                if Length(gens) = 0 then
                    C := TrivialSubgroup(Q);
                else
                    C := Group(gens);
                fi;

                # Validate
                if Size(C) * Size(M_bar) <> Size(Q) then
                    invalidCount := invalidCount + 1;
                    continue;
                fi;

                if Size(Intersection(C, M_bar)) > 1 then
                    invalidCount := invalidCount + 1;
                    continue;
                fi;

                Add(complements, C);
            od;

            # If batch generation succeeded without too many failures, return
            if invalidCount = 0 then
                return complements;
            fi;

            # Otherwise fall through to standard method
            complements := [];
            invalidCount := 0;
        fi;
    fi;

    # STANDARD METHOD: Iterate through precomputed representatives
    for cocycle in H1record.H1Representatives do
        C := CocycleToComplement(cocycle, complementInfo);

        # Handle fail from CocycleToComplement (assertion failure)
        if C = fail then
            invalidCount := invalidCount + 1;
            continue;
        fi;

        # Verify it's actually a complement
        if Size(C) * Size(complementInfo.M_bar) <> Size(complementInfo.Q) then
            Info(InfoWarning, 2, "EnumerateComplementsFromH1: wrong order |C|=",
                 Size(C), " expected ", Size(complementInfo.Q) / Size(complementInfo.M_bar));
            # Diagnostic: check if this is the zero cocycle
            if ForAll(cocycle, x -> x = Zero(complementInfo.module.field)) then
                Print("  DIAGNOSTIC: zero cocycle failed! preimageGens don't form a complement.\n");
                Print("  |Group(preimageGens)| = ", Size(Group(complementInfo.preimageGens)), "\n");
            else
                Print("  DIAGNOSTIC: failing cocycle = ", cocycle, "\n");
            fi;
            invalidCount := invalidCount + 1;
            continue;
        fi;

        if Size(Intersection(C, complementInfo.M_bar)) > 1 then
            Info(InfoWarning, 2, "EnumerateComplementsFromH1: not a complement, |C ∩ M_bar|=",
                 Size(Intersection(C, complementInfo.M_bar)));
            if ForAll(cocycle, x -> x = Zero(complementInfo.module.field)) then
                Print("  DIAGNOSTIC: zero cocycle intersection failure! preimageGens overlap M_bar.\n");
            else
                Print("  DIAGNOSTIC: failing cocycle = ", cocycle, "\n");
            fi;
            invalidCount := invalidCount + 1;
            continue;
        fi;

        Add(complements, C);
    od;

    # If any complements failed validation, return fail to trigger fallback
    if invalidCount > 0 then
        Info(InfoWarning, 1, "EnumerateComplementsFromH1: ", invalidCount,
             " invalid complements (|Q|=", Size(complementInfo.Q),
             " |M_bar|=", Size(complementInfo.M_bar),
             " ngens=", Length(complementInfo.module.generators),
             "), falling back to GAP method");
        return fail;
    fi;

    return complements;
end;

###############################################################################
# GetComplementsViaH1(Q, M_bar [, filterFunc])
#
# Convenience function: compute H^1 and return all complement class reps.
#
# This is the main interface for the lifting algorithm.
#
# OPTIMIZATION: Accepts optional filter function for early pruning during
# complement enumeration (e.g., FPF checking).
#
# Input:
#   Q          - ambient group (a quotient S/L)
#   M_bar      - normal subgroup (image of chief series term in Q)
#   filterFunc - (optional) function C -> bool, returns true if C should be kept
#
# Returns: List of complement subgroups (representatives of conjugacy classes)
#          Falls back to GAP's ComplementClassesRepresentatives if H^1 method fails
###############################################################################

GetComplementsViaH1 := function(arg)
    local Q, M_bar, filterFunc, module, H1, complementInfo, complements,
          filteredComplements, C;

    # Parse arguments
    Q := arg[1];
    M_bar := arg[2];
    if Length(arg) >= 3 then
        filterFunc := arg[3];
    else
        filterFunc := fail;
    fi;

    # Handle trivial M_bar
    if Size(M_bar) = 1 then
        if filterFunc <> fail then
            if filterFunc(Q) then
                return [Q];
            else
                return [];
            fi;
        fi;
        return [Q];
    fi;

    # Handle non-elementary-abelian M_bar (shouldn't happen for chief factors)
    if not IsElementaryAbelian(M_bar) then
        Error("GetComplementsViaH1 requires elementary abelian M_bar");
    fi;

    # Create module (now uses a valid base complement for preimages)
    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));

    # Handle the different failure modes from ChiefFactorAsModule separately:

    # Case 1: Non-split extension (normal behavior, not a failure)
    if IsRecord(module) and IsBound(module.isNonSplit) and module.isNonSplit then
        Info(InfoWarning, 2, "GetComplementsViaH1: non-split extension, no complements exist");
        return [];
    fi;

    # Case 2: Module construction failed (genuine failure, use fallback)
    if module = fail or (IsRecord(module) and
            IsBound(module.isModuleConstructionFailed) and module.isModuleConstructionFailed) then
        Info(InfoWarning, 1, "GetComplementsViaH1: module construction failed, using GAP fallback");
        if IsRecord(module) and IsBound(module.foundComplements)
           and Length(module.foundComplements) > 0 then
            complements := module.foundComplements;
        else
            complements := ComplementClassesRepresentatives(Q, M_bar);
        fi;
        if filterFunc <> fail then
            return Filtered(complements, filterFunc);
        fi;
        return complements;
    fi;

    # Case 3: Missing matrices (incomplete module record)
    if IsRecord(module) and not IsBound(module.matrices) then
        Info(InfoWarning, 1, "GetComplementsViaH1: module missing matrices, using GAP fallback");
        complements := ComplementClassesRepresentatives(Q, M_bar);
        if filterFunc <> fail then
            return Filtered(complements, filterFunc);
        fi;
        return complements;
    fi;

    # FAST PATH: If ChiefFactorAsModule already found all complements via
    # ComplementClassesRepresentatives (stored in module.foundComplements),
    # reuse them directly. This avoids redundant H^1 computation.
    if IsBound(module.foundComplements) and IsList(module.foundComplements)
       and Length(module.foundComplements) > 0 then
        if filterFunc <> fail then
            return Filtered(module.foundComplements, filterFunc);
        fi;
        return module.foundComplements;
    fi;

    # Compute H^1 with caching (Phase 3 optimization)
    if IsBound(CachedComputeH1) then
        H1 := CachedComputeH1(module);
    else
        H1 := ComputeH1(module);
    fi;

    # Build complement info
    complementInfo := BuildComplementInfo(Q, M_bar, module);

    # Enumerate complements (with optional filter)
    if filterFunc <> fail then
        complements := EnumerateComplementsFromH1WithFilter(H1, complementInfo, filterFunc);
    else
        complements := EnumerateComplementsFromH1(H1, complementInfo);
    fi;

    # If enumeration failed (invalid complements detected), fall back to GAP
    if complements = fail then
        Info(InfoWarning, 1, "GetComplementsViaH1: enumeration failed, using GAP fallback");
        complements := ComplementClassesRepresentatives(Q, M_bar);
        if filterFunc <> fail then
            return Filtered(complements, filterFunc);
        fi;
        return complements;
    fi;

    # Skip count validation when filter is applied (filter may reduce count)
    if filterFunc = fail then
        # Final validation: check we got the expected number of complements
        # H^1 should give exactly p^(dim H^1) complements
        if Length(complements) <> H1.numComplements then
            Info(InfoWarning, 1, "GetComplementsViaH1: complement count mismatch, expected ",
                 H1.numComplements, " got ", Length(complements), ", using GAP fallback");
            complements := ComplementClassesRepresentatives(Q, M_bar);
        fi;
    fi;

    return complements;
end;

###############################################################################
# EnumerateComplementsFromH1WithFilter(H1record, complementInfo, filterFunc)
#
# OPTIMIZATION: Enumerate complements with early filtering during generation.
# Applies filterFunc to each complement as it's generated, skipping invalid
# ones immediately rather than collecting all and filtering afterward.
#
# Input:
#   H1record       - CohomologyRecord from ComputeH1
#   complementInfo - record from BuildComplementInfo
#   filterFunc     - function C -> bool, returns true if C passes filter
#
# Returns: List of complement subgroups that pass the filter
###############################################################################

EnumerateComplementsFromH1WithFilter := function(H1record, complementInfo, filterFunc)
    local complements, cocycle, C, invalidCount, filteredCount;

    complements := [];
    invalidCount := 0;
    filteredCount := 0;

    for cocycle in H1record.H1Representatives do
        C := CocycleToComplement(cocycle, complementInfo);

        # Verify it's actually a complement
        if Size(C) * Size(complementInfo.M_bar) <> Size(complementInfo.Q) then
            Info(InfoWarning, 2, "EnumerateComplementsFromH1WithFilter: wrong order |C|=",
                 Size(C), " expected ", Size(complementInfo.Q) / Size(complementInfo.M_bar));
            invalidCount := invalidCount + 1;
            continue;
        fi;

        if Size(Intersection(C, complementInfo.M_bar)) > 1 then
            Info(InfoWarning, 2, "EnumerateComplementsFromH1WithFilter: not a complement, |C ∩ M_bar|=",
                 Size(Intersection(C, complementInfo.M_bar)));
            invalidCount := invalidCount + 1;
            continue;
        fi;

        # EARLY FILTERING: Apply filter before adding to results
        if filterFunc(C) then
            Add(complements, C);
        else
            filteredCount := filteredCount + 1;
        fi;
    od;

    # If any complements failed validation, return fail to trigger fallback
    if invalidCount > 0 then
        Info(InfoWarning, 1, "EnumerateComplementsFromH1WithFilter: ", invalidCount,
             " invalid complements, falling back to GAP method");
        return fail;
    fi;

    return complements;
end;

###############################################################################

Print("Modules loaded.\n");
Print("===============\n");
Print("Functions: ChiefFactorAsModule, BuildComplementInfo, CocycleToComplement\n");
Print("          EnumerateComplementsFromH1, GetComplementsViaH1\n\n");
