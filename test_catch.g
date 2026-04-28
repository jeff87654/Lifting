LogTo("C:/Users/jeffr/Downloads/Lifting/test_catch.log");
BreakOnError := false;
Print("Testing CALL_WITH_CATCH on a deliberately failing call...\n");

# Force NoMethodFound: GroupByGenerators with bad arg types
res := CALL_WITH_CATCH(function()
    return GroupByGenerators(fail, fail);
end, []);
Print("Caught? ", res[1] = false, "\n");
Print("res[1]=", res[1], "\n");
if res[1] = false then
    Print("Caught error gracefully. Worker pattern works.\n");
else
    Print("UNEXPECTED: did not raise an error.\n");
fi;

LogTo();
QUIT;
