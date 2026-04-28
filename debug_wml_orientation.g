
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_wml_orientation.log");

L1 := Group([(1,2)(3,4),(5,6,7)]);
L2 := Group([(1,2),(3,4),(5,6,7)]);

# W_DESC: S_3 on 1-3, (S_2 wr S_2) on 4-7  (partition [3,2,2] descending)
W_DESC_S3 := SymmetricGroup([1..3]);
W_DESC_W2 := WreathProduct(SymmetricGroup(2), SymmetricGroup(2));
# Shift WreathProduct(S_2,S_2) to act on points 4..7
W_DESC_W2_shift := Group(List(GeneratorsOfGroup(W_DESC_W2),
                              g -> g^(MappingPermListList([1..4],[4..7]))));
W_DESC := Group(Concatenation(GeneratorsOfGroup(W_DESC_S3),
                              GeneratorsOfGroup(W_DESC_W2_shift)));

# W_ASC: (S_2 wr S_2) on 1-4, S_3 on 5-7   (partition [2,2,3] ascending)
W_ASC_W2 := WreathProduct(SymmetricGroup(2), SymmetricGroup(2));   # acts on 1-4 by default
W_ASC_S3 := Group(List(GeneratorsOfGroup(SymmetricGroup(3)),
                       g -> g^(MappingPermListList([1..3],[5..7]))));
W_ASC := Group(Concatenation(GeneratorsOfGroup(W_ASC_W2),
                              GeneratorsOfGroup(W_ASC_S3)));

ConjAction := function(K, g) return K^g; end;

ReportFor := function(name, L)
    local N_L_DESC, N_L_ASC, K_set, orbs_DESC, orbs_ASC;
    Print("\n=== ", name, " |L|=", Size(L), " ===\n");
    K_set := Filtered(NormalSubgroups(L), K -> K <> L);
    Print("K-count=", Length(K_set), "\n");

    Print("L in W_DESC = ", IsSubset(W_DESC, L), "\n");
    Print("L in W_ASC  = ", IsSubset(W_ASC, L), "\n");

    if IsSubset(W_DESC, L) then
        N_L_DESC := Normalizer(W_DESC, L);
        Print("|N_W_DESC(L)|=", Size(N_L_DESC), "\n");
        orbs_DESC := Orbits(N_L_DESC, K_set, ConjAction);
        Print("W_DESC orbits: ", Length(orbs_DESC), "\n");
        for o in orbs_DESC do
            Print("  size=", Length(o), " quot=", IdGroup(L/o[1]), "\n");
        od;
    fi;

    if IsSubset(W_ASC, L) then
        N_L_ASC := Normalizer(W_ASC, L);
        Print("|N_W_ASC(L)|=", Size(N_L_ASC), "\n");
        orbs_ASC := Orbits(N_L_ASC, K_set, ConjAction);
        Print("W_ASC orbits: ", Length(orbs_ASC), "\n");
        for o in orbs_ASC do
            Print("  size=", Length(o), " quot=", IdGroup(L/o[1]), "\n");
        od;
    fi;
end;

ReportFor("L1 = <(1,2)(3,4),(5,6,7)>", L1);
ReportFor("L2 = <(1,2),(3,4),(5,6,7)>", L2);

LogTo();
QUIT;
