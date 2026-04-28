LogTo("C:/Users/jeffr/Downloads/Lifting/verify_combo_1.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Combo 1: [4,2]_[4,3]_[4,3]_[6,14], fresh=3028, predicted=1504, stored=2207.
fpath := "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[6,4,4,4]/[4,2]_[4,3]_[4,3]_[6,14].g";
fs := StringFile(fpath);
text := ReplacedString(fs, "\\\n", "");
groups := [];
for line in SplitString(text, "\n") do
    if Length(line) > 0 and line[1] = '[' then
        Add(groups, Group(EvalString(line)));
    fi;
od;
Print("Loaded ", Length(groups), " groups\n");

# Partition order [6,4,4,4]; combo (sorted) [4,2] [4,3] [4,3] [6,14]
factors := [TransitiveGroup(6,14), TransitiveGroup(4,2),
            TransitiveGroup(4,3), TransitiveGroup(4,3)];
Npart := BuildPerComboNormalizer([6,4,4,4], factors, 18);
Print("|Npart| = ", Size(Npart), "\n");

# Pick 10 random distinct groups
n := Length(groups);
chosen_idxs := [];
while Length(chosen_idxs) < 10 do
    i := Random([1..n]);
    if not i in chosen_idxs then Add(chosen_idxs, i); fi;
od;
Print("Random indices: ", chosen_idxs, "\n");

picks := List(chosen_idxs, i -> groups[i]);

n_pairs := 0;
n_match := 0;
t0 := Runtime();
for i in [1..Length(picks)] do
    for j in [i+1..Length(picks)] do
        n_pairs := n_pairs + 1;
        ra := RepresentativeAction(Npart, picks[i], picks[j]);
        if ra <> fail then
            n_match := n_match + 1;
            Print("  MATCH: groups[", chosen_idxs[i], "] ~ groups[",
                  chosen_idxs[j], "]\n");
        fi;
    od;
od;
Print("\nPairs: ", n_pairs, ", Matches: ", n_match,
      ", Elapsed: ", (Runtime()-t0)/1000.0, "s\n");
if n_match = 0 then
    Print("RESULT: 10 random picks all distinct. 3028 likely correct.\n");
else
    Print("RESULT: ", n_match, " duplicate pair(s). Dedup BROKEN for this combo.\n");
fi;
LogTo();
QUIT;
