
LogTo("C:/Users/jeffr/Downloads/Lifting/test_bw_heuristic.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/diag_combo6_v3_allcalls.g");

# Compute bw estimate (the search-space size GAP would use).
EstimateBw := function(C, M_bar)
    local gens, cl_M, bw;
    if IsSolvableGroup(C) and CanEasilyComputePcgs(C) then
        gens := MinimalGeneratingSet(C);
    else
        gens := SmallGeneratingSet(C);
    fi;
    cl_M := ConjugacyClasses(M_bar);
    bw := Product(List(gens,
            g -> Sum(Filtered(cl_M,
                    j -> IsInt(Order(g) / Order(Representative(j)))),
                Size)));
    return bw;
end;

big := Filtered(GAH_ALL_CALLS, r -> r.source = "GAH" and r.Q_size = 115200);
Print("[bw] testing on ", Length(big), " |Q|=115200 records\n\n");

for i in [1..Length(big)] do
    r := big[i];
    Q := Group(r.Q_gens);
    M_bar := Group(r.M_bar_gens);
    SetSize(Q, r.Q_size);
    SetSize(M_bar, r.M_bar_size);
    C := Centralizer(Q, M_bar);

    bw := EstimateBw(C, M_bar);
    t0 := Runtime();
    h := AllHomomorphismClasses(C, M_bar);
    t := Runtime() - t0;
    Print("[bw] rec ", i, ": |C|=", Size(C),
          " gens orders = ", List(GeneratorsOfGroup(C), Order),
          " | bw = ", bw,
          " | AllHomClass = ", t, "ms (", Length(h), " classes)\n");
od;

LogTo();
QUIT;
