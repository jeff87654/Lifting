###############################################################################
# Verify worker A combo 8 dedup correctness:
#   Pick 10 random groups from the 41 in [4,1]_[4,2]_[4,2]_[6,15].g
#   Run RepresentativeAction(Npart, H_i, H_j) for all 45 pairs.
#   Any match => fresh result has duplicates => dedup is broken.
###############################################################################

LogTo("C:/Users/jeffr/Downloads/Lifting/verify_combo_8.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Load the 41 groups from disk file
fpath := "C:/Users/jeffr/Downloads/Lifting/parallel_s18/[6,4,4,4]/[4,1]_[4,2]_[4,2]_[6,15].g";
fs := StringFile(fpath);
text := ReplacedString(fs, "\\\n", "");
groups := [];
for line in SplitString(text, "\n") do
    if Length(line) > 0 and line[1] = '[' then
        Add(groups, Group(EvalString(line)));
    fi;
od;
Print("Loaded ", Length(groups), " groups from disk\n");

# Build the partition normalizer Npart for [6,4,4,4] with the combo's factors:
# combo (sorted): [4,1] [4,2] [4,2] [6,15]
# In partition order [6,4,4,4]: factors = [TG(6,15), TG(4,1), TG(4,2), TG(4,2)]
factors := [TransitiveGroup(6,15), TransitiveGroup(4,1),
            TransitiveGroup(4,2), TransitiveGroup(4,2)];
shifted := []; offs := []; off := 0;
for f in factors do
    Add(offs, off);
    Add(shifted, ShiftGroup(f, off));
    off := off + NrMovedPoints(f);
od;
Npart := BuildPerComboNormalizer([6,4,4,4], factors, 18);
Print("|Npart| = ", Size(Npart), "\n");

# Pick 10 random distinct groups
n := Length(groups);
chosen_idxs := [];
while Length(chosen_idxs) < 10 do
    i := Random([1..n]);
    if not i in chosen_idxs then Add(chosen_idxs, i); fi;
od;
Print("Random indices chosen: ", chosen_idxs, "\n");

picks := List(chosen_idxs, i -> groups[i]);

# Pairwise RA test under Npart
n_pairs := 0;
n_match := 0;
matched_pairs := [];
t0 := Runtime();
for i in [1..Length(picks)] do
    for j in [i+1..Length(picks)] do
        n_pairs := n_pairs + 1;
        ra := RepresentativeAction(Npart, picks[i], picks[j]);
        if ra <> fail then
            n_match := n_match + 1;
            Add(matched_pairs, [chosen_idxs[i], chosen_idxs[j]]);
            Print("  MATCH: groups[", chosen_idxs[i], "] ~ groups[",
                  chosen_idxs[j], "] (under Npart-conjugation)\n");
        fi;
    od;
od;
elapsed := (Runtime() - t0) / 1000.0;

Print("\n=== Verdict ===\n");
Print("Pairs tested: ", n_pairs, "\n");
Print("Conjugate pairs found: ", n_match, "\n");
Print("Matched: ", matched_pairs, "\n");
Print("Elapsed: ", elapsed, "s\n");
if n_match = 0 then
    Print("RESULT: All 10 picks are distinct under Npart. Dedup looks CORRECT.\n");
    Print("        Fresh value of 41 (vs predicted 9, stored 12) is likely right.\n");
else
    Print("RESULT: ", n_match, " duplicate pair(s) found. Dedup is BROKEN.\n");
fi;

LogTo();
QUIT;
