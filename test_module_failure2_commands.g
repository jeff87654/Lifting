
LogTo("C:/Users/jeffr/Downloads/Lifting/test_module_failure2_output.txt");
Print("Module Construction Failure Debug - Realistic Scenario\n");
Print("=======================================================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Patch GetH1OrbitRepresentatives to add more debugging
_Original_GetH1OrbitRepresentatives := GetH1OrbitRepresentatives;

GetH1OrbitRepresentatives := function(Q, M_bar, ambient)
    local module, result;

    # Create module
    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));

    if module = fail then
        Print("# DEBUG: ChiefFactorAsModule failed for:\n");
        Print("#   |Q| = ", Size(Q), "\n");
        Print("#   |M_bar| = ", Size(M_bar), "\n");
        Print("#   IsElementaryAbelian(M_bar) = ", IsElementaryAbelian(M_bar), "\n");

        # Check if complements exist at all
        Print("#   Checking ComplementClassesRepresentatives...\n");
        result := ComplementClassesRepresentatives(Q, M_bar);
        Print("#   Found ", Length(result), " complement classes\n");

        if Length(result) = 0 then
            Print("#   => NON-SPLIT EXTENSION - no complements exist\n");
        else
            Print("#   => Complements exist but module construction failed!\n");
        fi;

        return ComplementClassesRepresentatives(Q, M_bar);
    fi;

    return _Original_GetH1OrbitRepresentatives(Q, M_bar, ambient);
end;

# Temporarily reduce info output
SetInfoLevel(InfoWarning, 0);

Print("Running S8 enumeration with debug...\n\n");

result := CountAllConjugacyClassesFast(8);

Print("\n\nS8 Result: ", result, " (expected: 296)\n");
if result = 296 then
    Print("Status: PASS\n");
else
    Print("Status: FAIL\n");
fi;

Print("\n======================================\n");
Print("Debug Test Complete\n");
Print("======================================\n");
LogTo();
QUIT;
