
LogTo("C:/Users/jeffr/Downloads/Lifting/test_fast_allhom.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/diag_combo6_v3_allcalls.g");

# Custom Hom-class enumeration that bypasses GAP's random gen search.
FastAllHomClasses := function(H, G)
    local cl, gens, bi, params, k;
    if IsCyclic(H) then
        # Cyclic case: fast already in stock GAP.
        return AllHomomorphismClasses(H, G);
    fi;
    if IsSolvableGroup(H) and CanEasilyComputePcgs(H) then
        gens := MinimalGeneratingSet(H);
    else
        gens := SmallGeneratingSet(H);
    fi;
    cl := ConjugacyClasses(G);
    bi := List(gens, i -> Filtered(cl,
                j -> IsInt(Order(i) / Order(Representative(j)))));
    if ForAny(bi, i -> Length(i) = 0) then
        return [];
    fi;
    params := rec(gens := gens, from := H);
    return MorClassLoop(G, bi, params, 9);
end;

# Test on each |Q|=115200 record: stock vs Fast.
big := Filtered(GAH_ALL_CALLS, r -> r.source = "GAH" and r.Q_size = 115200);
Print("[fast] testing on ", Length(big), " |Q|=115200 records\n\n");

stock_times := [];
fast_times := [];
for i in [1..Length(big)] do
    r := big[i];
    Q := Group(r.Q_gens);
    M_bar := Group(r.M_bar_gens);
    SetSize(Q, r.Q_size);
    SetSize(M_bar, r.M_bar_size);
    C := Centralizer(Q, M_bar);

    t0 := Runtime();
    h_stock := AllHomomorphismClasses(C, M_bar);
    t_stock := Runtime() - t0;
    Add(stock_times, t_stock);

    t0 := Runtime();
    h_fast := FastAllHomClasses(C, M_bar);
    t_fast := Runtime() - t0;
    Add(fast_times, t_fast);

    Print("[fast] rec ", i,
          ": stock ", t_stock, "ms (", Length(h_stock), " classes)",
          " | fast ", t_fast, "ms (", Length(h_fast), " classes)\n");
od;

Print("\n[fast] stock total = ", Sum(stock_times), "ms",
      " | fast total = ", Sum(fast_times), "ms\n");
Print("[fast] stock max = ", Maximum(stock_times), "ms",
      " | fast max = ", Maximum(fast_times), "ms\n");
Print("[fast] stock counts = ", List(stock_times, x -> x), "\n");
Print("[fast] fast counts = ", List(fast_times, x -> x), "\n");

LogTo();
QUIT;
