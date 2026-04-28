
LogTo("C:/Users/jeffr/Downloads/Lifting/test_module_failure3_output.txt");
Print("Module Failure Detailed Debug for S9\n");
Print("=====================================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/cohomology.g");
Read("C:/Users/jeffr/Downloads/Lifting/modules.g");

# Patch ChiefFactorAsModule to print exactly why it fails
_Orig_ChiefFactorAsModule := ChiefFactorAsModule;

ChiefFactorAsModule := function(Q, M_bar, N_bar)
    local G, p, hom, module, gens_Q, gens_G, module_group,
          standardComplement, gen, found, c, baseComplements,
          baseComplement, baseGens, m, newGensQ, newGensG, i, genGroup,
          pcgsG, phi, invphi, pcgsComp, elem;

    # The acting group G is Q/M_bar
    hom := NaturalHomomorphismByNormalSubgroup(Q, M_bar);
    G := ImagesSource(hom);

    if Size(N_bar) > 1 then
        Error("Non-trivial N_bar not yet supported");
    fi;

    module_group := M_bar;

    if not IsElementaryAbelian(module_group) then
        Print("FAIL_REASON: M_bar not elementary abelian\n");
        return fail;
    fi;

    if Size(module_group) = 1 then
        p := 2;
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
            ambientGroup := Q
        );
    fi;

    p := PrimePGroup(module_group);

    # Strategy 1: Coprime case
    baseComplement := fail;
    if Size(G) > 1 then
        if Gcd(Size(G), Size(M_bar)) = 1 then
            baseComplement := HallSubgroup(Q, PrimeDivisors(Size(G)));
            if baseComplement <> fail then
                if Size(Intersection(baseComplement, M_bar)) > 1 or
                   Size(baseComplement) <> Size(G) then
                    baseComplement := fail;
                fi;
            fi;
        fi;
    fi;

    # Strategy 2: ComplementClassesRepresentatives
    if baseComplement = fail then
        baseComplements := ComplementClassesRepresentatives(Q, M_bar);
        if Length(baseComplements) = 0 then
            Print("FAIL_REASON: ComplementClassesRepresentatives returned empty (non-split)\n");
            Print("  |Q| = ", Size(Q), ", |M_bar| = ", Size(M_bar), ", |G| = ", Size(G), "\n");
            return fail;
        fi;
        baseComplement := baseComplements[1];
    fi;

    # Try Pcgs-based construction
    gens_Q := [];
    gens_G := [];
    found := false;

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
                fi;
            fi;
        fi;
    fi;

    # Fallback strategies
    if not found and Size(baseComplement) <= 1000 and CanEasilyComputePcgs(G) then
        pcgsG := Pcgs(G);
        if pcgsG <> fail and Length(pcgsG) > 0 then
            gens_Q := [];
            gens_G := List(pcgsG);
            found := true;
            for gen in gens_G do
                c := First(AsSSortedList(baseComplement),
                          elem -> Image(hom, elem) = gen);
                if c <> fail then
                    Add(gens_Q, c);
                else
                    found := false;
                    gens_Q := [];
                    break;
                fi;
            od;
        fi;
    fi;

    if not found and CanEasilyComputePcgs(baseComplement) then
        pcgsComp := Pcgs(baseComplement);
        if pcgsComp <> fail and Length(pcgsComp) > 0 then
            gens_Q := List(pcgsComp);
            gens_G := List(gens_Q, c -> Image(hom, c));
            if Size(Group(gens_G)) = Size(G) then
                found := true;
            fi;
        fi;
    fi;

    if not found then
        gens_Q := SmallGeneratingSet(baseComplement);
        gens_G := List(gens_Q, c -> Image(hom, c));
        if Length(gens_G) > 0 and Size(Group(gens_G)) = Size(G) then
            found := true;
        else
            gens_Q := GeneratorsOfGroup(baseComplement);
            gens_G := List(gens_Q, c -> Image(hom, c));
        fi;
    fi;

    # Remove trivial generators
    newGensQ := [];
    newGensG := [];
    for i in [1..Length(gens_Q)] do
        if gens_G[i] <> One(G) then
            Add(newGensQ, gens_Q[i]);
            Add(newGensG, gens_G[i]);
        fi;
    od;
    gens_Q := newGensQ;
    gens_G := newGensG;

    # Check generators
    if Length(gens_G) = 0 then
        if Size(G) > 1 then
            Print("FAIL_REASON: No non-trivial generators found\n");
            Print("  |Q| = ", Size(Q), ", |M_bar| = ", Size(M_bar), ", |G| = ", Size(G), "\n");
            return fail;
        fi;
    else
        genGroup := Group(gens_G);
        if Size(genGroup) < Size(G) then
            gens_Q := SmallGeneratingSet(baseComplement);
            gens_G := List(gens_Q, c -> Image(hom, c));
            newGensQ := [];
            newGensG := [];
            for i in [1..Length(gens_Q)] do
                if gens_G[i] <> One(G) then
                    Add(newGensQ, gens_Q[i]);
                    Add(newGensG, gens_G[i]);
                fi;
            od;
            gens_Q := newGensQ;
            gens_G := newGensG;

            if Length(gens_G) = 0 or Size(Group(gens_G)) < Size(G) then
                Print("FAIL_REASON: Generators insufficient (don't generate G)\n");
                Print("  |Q| = ", Size(Q), ", |M_bar| = ", Size(M_bar), ", |G| = ", Size(G), "\n");
                Print("  |genGroup| = ", Size(Group(gens_G)), "\n");
                return fail;
            fi;
        fi;
    fi;

    # Validate complement
    if Length(gens_Q) > 0 then
        standardComplement := Group(gens_Q);
        if Size(Intersection(standardComplement, M_bar)) > 1 then
            Print("FAIL_REASON: preimageGens do not form a complement\n");
            Print("  |Q| = ", Size(Q), ", |M_bar| = ", Size(M_bar), "\n");
            return fail;
        fi;
    fi;

    module := CreateGModuleRecordViaPreimagesWithGens(G, gens_G, module_group, p, gens_Q);
    module.quotientHom := hom;
    module.ambientGroup := Q;
    module.preimageGens := gens_Q;

    return module;
end;

Print("Testing S9 partition [6,3]...\n\n");

# This partition should trigger the failures
S6 := SymmetricGroup(6);
S3 := SymmetricGroup(3);
P := DirectProduct(S6, S3);
emb1 := Embedding(P, 1);
emb2 := Embedding(P, 2);

# Create diagonal embedding for corresponding elements
# S3 embeds into both factors
standardS3 := SymmetricGroup(3);
diag := Group(List(GeneratorsOfGroup(standardS3), g ->
    Image(emb1, g) * Image(emb2, g)));

Print("Created diagonal S3 in S6 x S3\n");
Print("|diag| = ", Size(diag), "\n\n");

cs := ChiefSeries(diag);
Print("Chief series sizes: ", List(cs, Size), "\n\n");

for i in [1..Length(cs)-1] do
    M := cs[i];
    N := cs[i+1];

    if Size(M) > Size(N) then
        Print("Layer ", i, ": |M| = ", Size(M), ", |N| = ", Size(N), "\n");

        hom := NaturalHomomorphismByNormalSubgroup(diag, N);
        Q := ImagesSource(hom);
        M_bar := Image(hom, M);

        Print("  |Q| = ", Size(Q), ", |M_bar| = ", Size(M_bar), "\n");
        Print("  IsElementaryAbelian(M_bar) = ", IsElementaryAbelian(M_bar), "\n");

        if IsElementaryAbelian(M_bar) and Size(M_bar) > 1 then
            Print("  Calling ChiefFactorAsModule...\n");
            module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
            if module = fail then
                Print("  => FAILED\n");
            else
                Print("  => OK, dim = ", module.dimension, "\n");
            fi;
        fi;
        Print("\n");
    fi;
od;

Print("\n======================================\n");
Print("Debug Test Complete\n");
Print("======================================\n");
LogTo();
QUIT;
