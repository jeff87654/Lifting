LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/debug_range_err2.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean";

T1 := TransitiveGroup(7, 5);
T2 := ShiftGroup(TransitiveGroup(3, 1), 7);
T3 := ShiftGroup(TransitiveGroup(2, 1), 10);
P := Group(Concatenation(GeneratorsOfGroup(T1), GeneratorsOfGroup(T2),
                          GeneratorsOfGroup(T3)));
shifted := [T1, T2, T3];
offsets := [0, 7, 10];
Npart := SymmetricGroup(12);

Print("|P| = ", Size(P), "  IsSolvable? ", IsSolvableGroup(P), "\n");

Print("\nStep 1: HoltBuildLiftSeries (P non-solvable)...\n");
BreakOnError := false;
r1 := CALL_WITH_CATCH(function() return HoltBuildLiftSeries(P); end, []);
BreakOnError := true;
if r1[1] then
  sr := r1[2];
  Print("  OK radical |Pt|=", Size(sr.radical), " layers=", Length(sr.layers), "\n");
else
  Print("  STEP 1 FAILED\n");
fi;

Print("\nStep 2: HoltTopClasses...\n");
BreakOnError := false;
r2 := CALL_WITH_CATCH(function() return HoltTopClasses(P, sr); end, []);
BreakOnError := true;
if r2[1] then
  tc := r2[2];
  Print("  OK got ", Length(tc), " top classes\n");
else
  Print("  STEP 2 FAILED\n");
fi;

Print("\nStep 3: Filter by IsFPFSubdirect...\n");
BreakOnError := false;
r3 := CALL_WITH_CATCH(function()
    return Filtered(tc, H -> IsFPFSubdirect(H, shifted, offsets)); end, []);
BreakOnError := true;
if r3[1] then
  filt := r3[2];
  Print("  OK filtered to ", Length(filt), " classes\n");
else
  Print("  STEP 3 FAILED\n");
fi;

Print("\nStep 4: Lift through one layer (first parent)...\n");
if Length(filt) >= 1 and Length(sr.layers) >= 1 then
  lyr := sr.layers[Length(sr.layers)];  # top-down first
  Print("  layer p=", lyr.p, " d=", lyr.d, "\n");
  BreakOnError := false;
  r4 := CALL_WITH_CATCH(function()
      return HoltLiftOneParentAcrossLayer(P, lyr, filt[1], fail); end, []);
  BreakOnError := true;
  if r4[1] then
    Print("  OK got ", Length(r4[2]), " children\n");
  else
    Print("  STEP 4 FAILED\n");
  fi;
fi;

LogTo();
QUIT;
