LogTo("C:/Users/jeffr/Downloads/Lifting/verify_8442.log");

# Char-orbit formula for [8,4,4,2]/[T(2,1), T(8,*), T(4,*)^2]:
# For each FPF subdirect H ≤ T(8,*)×T(4,*)^2 in S_16 (from S_16 [8,4,4]/* combos),
# contrib(H) = 1 + #N_S16(H)-orbits on index-2 subgroups of H.
# Total = sum over all 80,189 H reps.

S16 := SymmetricGroup(16);

# Load all S_16 [8,4,4] combos
src_dir := "C:/Users/jeffr/Downloads/Lifting/parallel_sn/16/[8,4,4]";
files := DirectoryContents(src_dir);
n_files_processed := 0;
n_groups_total := 0;
total_contrib := 0;
big_t0 := Runtime();
slow_count := 0;

for fn in files do
    if Length(fn) <= 2 or fn{[Length(fn)-1..Length(fn)]} <> ".g" then continue; fi;
    fpath := Concatenation(src_dir, "/", fn);
    fs := StringFile(fpath);
    if fs = fail then continue; fi;
    text := ReplacedString(fs, "\\\n", "");
    lines := SplitString(text, "\n");
    n_files_processed := n_files_processed + 1;
    file_group_count := 0;
    file_contrib := 0;

    for line in lines do
        if Length(line) > 0 and line[1] = '[' then
            H := Group(EvalString(line));
            file_group_count := file_group_count + 1;

            idx2 := Filtered(MaximalSubgroupClassReps(H), M -> Index(H, M) = 2);
            if Length(idx2) = 0 then
                contrib := 1;
            else
                ts := Runtime();
                N := Normalizer(S16, H);
                orbs := OrbitsDomain(N, idx2,
                    function(M, n) return M^n; end);
                te := Runtime() - ts;
                if te > 5000 then slow_count := slow_count + 1; fi;
                contrib := 1 + Length(orbs);
            fi;
            file_contrib := file_contrib + contrib;
        fi;
    od;

    n_groups_total := n_groups_total + file_group_count;
    total_contrib := total_contrib + file_contrib;
    if n_files_processed mod 10 = 0 or n_files_processed <= 5 then
        Print("  files=", n_files_processed, "/750 H_total=", n_groups_total,
              " contrib=", total_contrib,
              " elapsed=", Int((Runtime()-big_t0)/1000), "s slow_N>5s=", slow_count, "\n");
    fi;
od;

Print("\n=== Final ===\n");
Print("Files processed: ", n_files_processed, "\n");
Print("H total: ", n_groups_total, " (expect 80189)\n");
Print("Sum contrib: ", total_contrib, "\n");
Print("Disk [8,4,4,2] sum: 1,105,238\n");
Print("Predictor: 1,161,508\n");
Print("Delta vs disk: ", total_contrib - 1105238, "\n");
Print("Delta vs predictor: ", total_contrib - 1161508, "\n");

LogTo();
QUIT;
