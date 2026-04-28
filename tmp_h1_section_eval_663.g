
LogTo("C:/Users/jeffr/Downloads/Lifting/tmp_h1_section_eval_663.log");
H1_OUTER_SECTION_ACTION := true;
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
T62 := TransitiveGroup(6, 2);
T31 := TransitiveGroup(3, 1);
factors := [T62, T62, T31];
shifted := [];; offs := [];; off := 0;;
for k in [1..3] do
  Add(offs, off);
  Add(shifted, ShiftGroup(factors[k], off));
  off := off + NrMovedPoints(factors[k]);
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
series := RefinedChiefSeries(P);
parents := [P];
for i in [1..Length(series)-2] do
  ClearH1Cache();
  FPF_SUBDIRECT_CACHE := rec();
  parents := LiftThroughLayer(P, series[i], series[i+1], parents, shifted, offs, fail);
od;
M := series[Length(series)-1]; L := series[Length(series)];
S := parents[2];
hom := NaturalHomomorphismByNormalSubgroup(S, L);
Q := ImagesSource(hom); M_bar := Image(hom, M);
module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
ClearH1Cache(); H1 := CachedComputeH1(module);
Print("H1_DIM=", H1.H1Dimension, " reps=", Length(H1.H1Representatives), " |G|=", Size(module.group), "\n");
base := H1BaseSectionHom(module); failures := 0;
for rep in H1.H1Representatives do
  section := H1SectionHomFromCocycle(module, rep);
  vals := CocycleVectorToValues(rep, module);
  for g in Elements(module.group) do
    a := EvaluateCocycleForElement(module, vals, g);
    b := H1EvaluateCocycleViaSections(module, base, section, g);
    if a <> b then failures := failures + 1; fi;
  od;
od;
Print("FAILURES=", failures, "\n");
LogTo(); QUIT;
