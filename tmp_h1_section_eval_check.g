
LogTo("C:/Users/jeffr/Downloads/Lifting/tmp_h1_section_eval_check.log");
H1_OUTER_SECTION_ACTION := true;
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
CheckModule := function(Q, M)
  local module, H1, base, rep, section, vals, G, elems, g, a, b, failures;
  module := ChiefFactorAsModule(Q, M, TrivialSubgroup(M));
  if not IsRecord(module) or IsBound(module.isNonSplit) or IsBound(module.isModuleConstructionFailed) then
    Print("MODULE_FAIL\n"); return;
  fi;
  H1 := CachedComputeH1(module);
  Print("H1_DIM=", H1.H1Dimension, " reps=", Length(H1.H1Representatives), " |G|=", Size(module.group), "\n");
  if Length(H1.H1Representatives) = 0 then return; fi;
  base := H1BaseSectionHom(module);
  failures := 0;
  elems := Elements(module.group);
  for rep in H1.H1Representatives do
    section := H1SectionHomFromCocycle(module, rep);
    if section = fail then Print("SECTION_FAIL\n"); return; fi;
    vals := CocycleVectorToValues(rep, module);
    for g in elems do
      a := EvaluateCocycleForElement(module, vals, g);
      b := H1EvaluateCocycleViaSections(module, base, section, g);
      if a <> b then
        failures := failures + 1;
      fi;
    od;
  od;
  Print("FAILURES=", failures, "\n");
end;
S4 := SymmetricGroup(4);
V4 := Group((1,2)(3,4),(1,3)(2,4));
CheckModule(S4, V4);
LogTo();
QUIT;
