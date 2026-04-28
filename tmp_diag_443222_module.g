
LogTo("C:/Users/jeffr/Downloads/Lifting/tmp_diag_443222_module.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean";
CHECKPOINT_DIR := "";
COMBO_OUTPUT_DIR := "";

_OrigChiefFactorAsModule := ChiefFactorAsModule;
ChiefFactorAsModule := function(Q, M_bar, N_bar)
  local module, hom, G, comps, C, gens, imgs, nontriv, sg, simgs,
        phi, pcgsG, invphi, qgens, pre, i;

  module := _OrigChiefFactorAsModule(Q, M_bar, N_bar);
  if IsRecord(module) and IsBound(module.isModuleConstructionFailed) then
    Print("\n=== CHIEF MODULE FAILURE ===\n");
    Print("|Q|=", Size(Q), " |M_bar|=", Size(M_bar), " |N_bar|=", Size(N_bar), "\n");
    Print("IsSolvable(Q)=", IsSolvableGroup(Q), " IsEA(M_bar)=", IsElementaryAbelian(M_bar), "\n");
    hom := SafeNaturalHomByNSG(Q, M_bar);
    if hom = fail then
      Print("SafeNaturalHomByNSG failed\n");
      LogTo(); Error("DIAG_ABORT");
    fi;
    G := ImagesSource(hom);
    Print("|G|=", Size(G), " CanPcgs(G)=", CanEasilyComputePcgs(G),
          " gensGAP=", Length(GeneratorsOfGroup(G)), "\n");
    if CanEasilyComputePcgs(G) then
      pcgsG := Pcgs(G);
      Print("Pcgs(G) len=", Length(pcgsG), " relOrders=", RelativeOrders(pcgsG), "\n");
    fi;

    if IsBound(module.foundComplements) then
      comps := module.foundComplements;
    else
      comps := [];
    fi;
    Print("foundComplements=", Length(comps), "\n");
    for i in [1..Minimum(Length(comps), 5)] do
      C := comps[i];
      Print("-- complement ", i, " |C|=", Size(C),
            " |C cap M|=", Size(Intersection(C, M_bar)), "\n");
      gens := GeneratorsOfGroup(C);
      imgs := List(gens, c -> Image(hom, c));
      nontriv := Filtered(imgs, x -> x <> One(G));
      Print("   GeneratorsOfGroup(C) len=", Length(gens),
            " image-len=", Length(nontriv));
      if Length(nontriv) > 0 then
        Print(" image-size=", Size(Group(nontriv)), "\n");
      else
        Print(" image-size=1\n");
      fi;
      Print("   C gens: ", gens, "\n");
      Print("   images: ", imgs, "\n");

      sg := SmallGeneratingSet(C);
      simgs := List(sg, c -> Image(hom, c));
      nontriv := Filtered(simgs, x -> x <> One(G));
      Print("   SmallGeneratingSet(C) len=", Length(sg),
            " image-len=", Length(nontriv));
      if Length(nontriv) > 0 then
        Print(" image-size=", Size(Group(nontriv)), "\n");
      else
        Print(" image-size=1\n");
      fi;
      Print("   small gens: ", sg, "\n");
      Print("   small images: ", simgs, "\n");

      phi := GroupHomomorphismByImages(C, G, gens, imgs);
      Print("   phi via GeneratorsOfGroup: ", phi <> fail);
      if phi <> fail then
        Print(" bijective=", IsBijective(phi));
      fi;
      Print("\n");

      if CanEasilyComputePcgs(G) and phi <> fail and IsBijective(phi) then
        invphi := InverseGeneralMapping(phi);
        qgens := Pcgs(G);
        pre := List(qgens, g -> Image(invphi, g));
        Print("   inverse Pcgs preimages valid=",
              ForAll(pre, x -> x <> fail and x in C), "\n");
        Print("   preimages: ", pre, "\n");
      fi;
    od;
    Print("=== END FAILURE ===\n");
    LogTo();
    Error("DIAG_ABORT");
  fi;
  return module;
end;

partition := [4,4,3,2,2,2];
currentFactors := [TransitiveGroup(4,3), TransitiveGroup(4,3),
                   TransitiveGroup(3,2), TransitiveGroup(2,1),
                   TransitiveGroup(2,1), TransitiveGroup(2,1)];
shifted := [];
offs := [];
off := 0;
for k in [1..Length(currentFactors)] do
  Add(offs, off);
  Add(shifted, ShiftGroup(currentFactors[k], off));
  off := off + NrMovedPoints(currentFactors[k]);
od;
P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
SetSize(P, Product(List(shifted, Size)));
N := BuildConjugacyTestGroup(17, partition);
CURRENT_BLOCK_RANGES := [[1,4],[5,8],[9,11],[12,13],[14,15],[16,17]];
Print("RUN exact combo |P|=", Size(P), " |N|=", Size(N), "\n");
res := HoltFPFSubgroupClassesOfProduct(P, shifted, offs, N);
Print("NO_FAILURE count=", Length(res), "\n");
LogTo();
QUIT;
