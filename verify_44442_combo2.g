LogTo("C:/Users/jeffr/Downloads/Lifting/verify_44442_combo2.log");

# Char-orbit formula for [4,4,4,4,2]/[T(2,1), T(4,2), T(4,3)^3]
# Disk says 168,412. Use S_16 base file [4,4,4,4]/[T(4,2),T(4,3)^3] = 8,354.
S16 := SymmetricGroup(16);

f := "C:/Users/jeffr/Downloads/Lifting/parallel_sn/16/[4,4,4,4]/[4,2]_[4,3]_[4,3]_[4,3].g";
fs := StringFile(f);
text := ReplacedString(fs, "\\\n", "");
groups := [];
for line in SplitString(text, "\n") do
    if Length(line) > 0 and line[1] = '[' then
        Add(groups, Group(EvalString(line)));
    fi;
od;
Print("Loaded ", Length(groups), " subgroups\n");

total := 0;
t0 := Runtime();
for i in [1..Length(groups)] do
    H := groups[i];
    idx2 := Filtered(MaximalSubgroupClassReps(H), M -> Index(H, M) = 2);
    if Length(idx2) = 0 then
        contrib := 1;
    else
        N := Normalizer(S16, H);
        orbs := OrbitsDomain(N, idx2, function(M, n) return M^n; end);
        contrib := 1 + Length(orbs);
    fi;
    total := total + contrib;
    if i mod 500 = 0 then
        Print("  i=", i, "/", Length(groups), " total=", total,
              " elapsed=", (Runtime()-t0)/1000.0, "s\n");
    fi;
od;
Print("\nFinal: total = ", total, " in ", (Runtime() - t0)/1000.0, "s\n");
Print("Disk count for [4,4,4,4,2]/[T(2,1),T(4,2),T(4,3)^3] = 168412\n");
Print("Delta = ", total - 168412, "\n");
LogTo();
QUIT;
