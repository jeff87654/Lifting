LogTo("C:/Users/jeffr/Downloads/Lifting/test_sn_fastpath.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n=== Test S_n fast path ===\n\n");

TestCombo := function(combo, expected)
    local shifted, offs, pos, c, G, P, result, t0, tMs;
    shifted := [];
    offs := [];
    pos := 0;
    for c in combo do
        G := TransitiveGroup(c[1], c[2]);
        Add(shifted, ShiftGroup(G, pos));
        Add(offs, pos);
        pos := pos + c[1];
    od;
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
    Print("Combo: ", combo, ", |P| = ", Size(P), "\n");
    t0 := Runtime();
    result := FindFPFClassesByLifting(P, shifted, offs);
    tMs := Runtime() - t0;
    Print("  Result: ", Length(result), " classes in ", tMs, "ms");
    if expected <> fail then
        if Length(result) = expected then
            Print(" [PASS, expected ", expected, "]\n");
        else
            Print(" [FAIL, expected ", expected, "]\n");
        fi;
    else
        Print(" [no expected value]\n");
    fi;
end;

# Test 1: S_5 substitute for the S_12 case
# [2,1] x [4,3] x [5,120] = C_2 x D_4 x S_5 -> expected 20 subdirects
Print("--- Test 1: [2,1] x [4,3] x [5,NrTransitive] = C_2 x D_4 x S_5 ---\n");
TestCombo([[2,1], [4,3], [5, NrTransitiveGroups(5)]], 20);

# Test 2: Small S_5 case matching stuck combo structure
Print("\n--- Test 2: [2,1] x [4,4] x [5,NrTransitive] = C_2 x A_4 x S_5 ---\n");
TestCombo([[2,1], [4,4], [5, NrTransitiveGroups(5)]], 2);

# Test 3: Actual stuck combo
Print("\n--- Test 3: [2,1] x [4,4] x [12,301] = C_2 x A_4 x S_12 ---\n");
TestCombo([[2,1], [4,4], [12,301]], 2);

# Test 4: The 20-class one we already have ground truth for
Print("\n--- Test 4: [2,1] x [4,3] x [12,301] = C_2 x D_4 x S_12 ---\n");
TestCombo([[2,1], [4,3], [12,301]], 20);

LogTo();
QUIT;
