# Load all 120 emitted fps from parallel_sn_v2/16/[8,8]/[8,9]_[8,9].g
# and check via swap_perm conjugation how many are TRULY distinct.

LogTo("/cygdrive/c/Users/jeffr/Downloads/Lifting/diag_8_9_pair.log");
F := "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_sn_v2/16/[8,8]/[8,9]_[8,9].g";

# Read lines, skip headers, parse each [gens] line into a Group.
text := StringFile(F);
lines := SplitString(text, "\n");
gens_lines := Filtered(lines, l -> Length(l) > 0 and l[1] = '[');
Print("Read ", Length(gens_lines), " gen lines\n");

groups := [];
for ln in gens_lines do
    G := EvalString(Concatenation("Group(", ln, ")"));
    Add(groups, G);
od;
Print("Built ", Length(groups), " groups\n");

# Force StabChain on all
for G in groups do Size(G); od;
Print("StabChains computed\n");

# swap_perm: ML=8, MR=8 (both blocks of 8)
swap := Product([1..8], k -> (k, 8+k));

# Pairwise dedup: union-find, considering F1 ~ F2 if F1 = F2 OR F1 = F2^swap.
parent := [1..Length(groups)];
UF_Find := function(x)
    while parent[x] <> x do
        parent[x] := parent[parent[x]];
        x := parent[x];
    od;
    return x;
end;

n_pairs := 0;
n_eq := 0;
n_swap_eq := 0;
for i in [1..Length(groups)] do
    for j in [i+1..Length(groups)] do
        n_pairs := n_pairs + 1;
        if UF_Find(i) = UF_Find(j) then continue; fi;
        if groups[i] = groups[j] then
            n_eq := n_eq + 1;
            parent[UF_Find(j)] := UF_Find(i);
            continue;
        fi;
        if groups[i] = groups[j]^swap then
            n_swap_eq := n_swap_eq + 1;
            parent[UF_Find(j)] := UF_Find(i);
        fi;
    od;
od;

# Count classes
classes := Set([1..Length(groups)], i -> UF_Find(i));
Print("Total groups: ", Length(groups), "\n");
Print("Pairwise comparisons: ", n_pairs, "\n");
Print("Equal-as-groups (no swap): ", n_eq, "\n");
Print("Swap-equivalent: ", n_swap_eq, "\n");
Print("Distinct equivalence classes: ", Length(classes), "\n");

LogTo();
QUIT;
