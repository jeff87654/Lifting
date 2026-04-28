
LogTo("C:/Users/jeffr/Downloads/Lifting/general_hom_test.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");

TestCase := function(build_Q, M_bar_func, comment)
    local Q, M_bar, C, idx, gap_gcd, t0, gen_result, t_gen,
          nscr_result, t_nscr, match;
    Q := build_Q();
    M_bar := M_bar_func(Q);
    C := Centralizer(Q, M_bar);
    idx := Size(Q) / Size(M_bar);
    gap_gcd := Gcd(Size(C), Size(M_bar));

    Print("=== ", comment, " ===\n");
    Print("  |Q|=", Size(Q), ", |M_bar|=", Size(M_bar),
          ", |C|=", Size(C), ", idx=", idx,
          ", gcd(|C|,|M_bar|)=", gap_gcd, "\n");

    t0 := Runtime();
    gen_result := GeneralAutHomComplements(Q, M_bar, C);
    t_gen := Runtime() - t0;
    if gen_result = fail then
        Print("  GeneralAutHom: FAIL (", t_gen, "ms)\n");
    else
        Print("  GeneralAutHom: ", Length(gen_result), " complements (", t_gen, "ms)\n");
    fi;

    t0 := Runtime();
    nscr_result := NonSolvableComplementClassReps(Q, M_bar);
    t_nscr := Runtime() - t0;
    Print("  NSCR:          ", Length(nscr_result), " complements (", t_nscr, "ms)\n");

    if gen_result = fail then
        Print("  [FAIL path — check why]\n\n");
    elif Length(gen_result) = Length(nscr_result) then
        Print("  OK (counts match)\n\n");
    else
        Print("  !! MISMATCH: ", Length(gen_result), " vs ", Length(nscr_result), " !!\n\n");
    fi;
end;

# --- Direct products (|C| = idx) ---
TestCase(function() return DirectProduct(AlternatingGroup(5), CyclicGroup(IsPermGroup, 2)); end,
         function(Q) return Image(Embedding(Q, 1), AlternatingGroup(5)); end,
         "A_5 x C_2 (DP, gcd=2)");

TestCase(function() return DirectProduct(AlternatingGroup(5), CyclicGroup(IsPermGroup, 3)); end,
         function(Q) return Image(Embedding(Q, 1), AlternatingGroup(5)); end,
         "A_5 x C_3 (DP, gcd=3)");

TestCase(function() return DirectProduct(AlternatingGroup(5), CyclicGroup(IsPermGroup, 7)); end,
         function(Q) return Image(Embedding(Q, 1), AlternatingGroup(5)); end,
         "A_5 x C_7 (DP, gcd=1 — just one complement)");

TestCase(function()
             local a, b;
             a := (1,2); b := (3,4);
             return DirectProduct(AlternatingGroup(5), Group([a,b]));
         end,
         function(Q) return Image(Embedding(Q, 1), AlternatingGroup(5)); end,
         "A_5 x V_4 (DP)");

TestCase(function() return DirectProduct(AlternatingGroup(6), CyclicGroup(IsPermGroup, 2)); end,
         function(Q) return Image(Embedding(Q, 1), AlternatingGroup(6)); end,
         "A_6 x C_2 (DP)");

# --- gcd = 1, non-direct-product ---
TestCase(function() return SymmetricGroup(5); end,
         function(Q) return AlternatingGroup(5); end,
         "S_5 = A_5 : C_2 (gcd=1, |C|=1)");

TestCase(function() return SymmetricGroup(6); end,
         function(Q) return AlternatingGroup(6); end,
         "S_6 = A_6 : C_2 (gcd=1, |C|=1)");

# --- gcd > 1, non-direct-product (THE NEW CASE) ---
# Build S_5 x C_2, where C_Q(A_5) = C_2 < idx=4.
TestCase(function() return DirectProduct(SymmetricGroup(5), CyclicGroup(IsPermGroup, 2)); end,
         function(Q) return Image(Embedding(Q, 1), AlternatingGroup(5)); end,
         "(S_5 x C_2) with M_bar = A_5 (|C|=2 < idx=4, gcd=2)");

# Build S_5 x C_6.  C_Q(A_5) = C_6. idx = 12.
TestCase(function() return DirectProduct(SymmetricGroup(5), CyclicGroup(IsPermGroup, 6)); end,
         function(Q) return Image(Embedding(Q, 1), AlternatingGroup(5)); end,
         "(S_5 x C_6) with M_bar = A_5 (|C|=6 < idx=12, gcd=2)");

# Wreath product A_5 wr C_2 -> has embedded A_5 x A_5.
# Take M_bar as one of the embedded A_5 factors.  Hard case.
# Skip for now (hard to set up cleanly in a test).

# Size-6 Out action on A_6 (PGL(2,9) and M_10 and S_6 between A_6 and Aut(A_6)).
# S_6 has |C_{S_6}(A_6)| = 1, gcd=1.
# Aut(A_6) has |C|=1 too.  So |C|<idx with gcd>1 is subtle to construct.

# Try A_6 x S_3 with M_bar = A_6.  C = S_3, |C| = 6, gcd(6,360)=6.
TestCase(function() return DirectProduct(AlternatingGroup(6), SymmetricGroup(3)); end,
         function(Q) return Image(Embedding(Q, 1), AlternatingGroup(6)); end,
         "A_6 x S_3 (DP, |C|=6=idx, gcd=6)");

# S_6 x C_2 with M_bar = A_6.  |C| = 2 (centralizer from C_2 factor),
# idx = |S_6 x C_2|/|A_6| = 1440/360 = 4.  |C|=2 < 4.  gcd(2,360)=2.
# This is a proper non-DP gcd>1 case.
TestCase(function() return DirectProduct(SymmetricGroup(6), CyclicGroup(IsPermGroup, 2)); end,
         function(Q) return Image(Embedding(Q, 1), AlternatingGroup(6)); end,
         "(S_6 x C_2) with M_bar = A_6 (|C|=2 < idx=4, gcd=2)");

LogTo();
QUIT;
