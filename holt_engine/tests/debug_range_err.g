LogTo("C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/debug_range_err.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean";  # force clean pipeline, no legacy-fallback swallow
Print("HOLT_ENGINE_MODE = ", HOLT_ENGINE_MODE, "\n");

# The failing combo from the S11-S13 run: [T(7,5), T(3,1), T(2,1)] on [7,3,2].
T1 := TransitiveGroup(7, 5);
T2 := ShiftGroup(TransitiveGroup(3, 1), 7);
T3 := ShiftGroup(TransitiveGroup(2, 1), 10);
P := Group(Concatenation(GeneratorsOfGroup(T1), GeneratorsOfGroup(T2),
                          GeneratorsOfGroup(T3)));
shifted := [T1, T2, T3];
offsets := [0, 7, 10];
# |P| = 168*3*2 = 1008
Print("|P| = ", Size(P), "\n");
Npart := SymmetricGroup(12);
CURRENT_BLOCK_RANGES := [[1,7],[8,10],[11,12]];

# Test _HoltBlockFactoredNormalizer in isolation first.
Print("Testing _HoltBlockFactoredNormalizer...\n");
blockNorm := _HoltBlockFactoredNormalizer(shifted, offsets, 12);
Print("  |blockNorm| = ", Size(blockNorm), "\n");
Print("  IsSubgroup(Npart, blockNorm) = ", IsSubgroup(Npart, blockNorm), "\n");

# Now try the clean pipeline.
Print("\nTesting HoltFPFSubgroupClassesOfProduct...\n");
BreakOnError := false;
result := CALL_WITH_CATCH(function()
    return HoltFPFSubgroupClassesOfProduct(P, shifted, offsets, Npart);
end, []);
BreakOnError := true;

if result[1] = true then
    Print("  Clean pipeline returned ", Length(result[2]), " classes\n");
else
    Print("  Clean pipeline ERRORED\n");
    if Length(result) >= 2 then
        Print("  Error info: ", result[2], "\n");
    fi;
fi;

LogTo();
QUIT;
