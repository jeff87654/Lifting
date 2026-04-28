LogTo("C:/Users/jeffr/Downloads/Lifting/verify_44442_via_chars.log");

# Character-orbit formula for [4,4,4,4,2] / [T(2,1), T(4,3)^4]
# For each FPF class H of D_4^4 in S_16:
#   classes contributed = 1 + #N_{S_16}(H)-orbits on Hom(H, C_2)*
#                       = 1 + #N_{S_16}(H)-orbits on index-2 subgroups of H

S16 := SymmetricGroup(16);
S18 := SymmetricGroup(18);

f := "C:/Users/jeffr/Downloads/Lifting/parallel_sn/16/[4,4,4,4]/[4,3]_[4,3]_[4,3]_[4,3].g";
fs := StringFile(f);
lines := SplitString(fs, "\n");

groups := [];
for line in lines do
    if Length(line) > 0 and line[1] = '[' then
        # Strip line continuations '\' and concatenate to next non-empty
        # Actually the file uses GAP backslash-continuation, so we need to
        # handle multi-line generator lists. Just join all lines that aren't
        # comments or empty into one big string and split on newlines that
        # don't follow a backslash.
    fi;
od;

# Simpler: read using GAP eval-line approach. The file format has
# each subgroup as a list-of-perms, possibly split with backslash-continuation.
# Strip trailing \\ + newline pairs, then eval each [...] line.
text := ReplacedString(fs, "\\\n", "");  # strip continuation
lines := SplitString(text, "\n");
groups := [];
for line in lines do
    if Length(line) > 0 and line[1] = '[' then
        gens := EvalString(line);
        Add(groups, Group(gens));
    fi;
od;
Print("Loaded ", Length(groups), " subgroups\n");

total := 0;
big_n := 0;
slow_count := 0;
slow_total_t := 0;

t0 := Runtime();
for i in [1..Length(groups)] do
    H := groups[i];
    # Index-2 subgroups via maximal subgroups
    idx2 := Filtered(MaximalSubgroupClassReps(H), M -> Index(H, M) = 2);

    if Length(idx2) = 0 then
        # H has no index-2 subgroups (rare) — only the trivial extension
        contrib := 1;
    else
        ts := Runtime();
        N := Normalizer(S16, H);
        # Orbits of N acting on the set of index-2 subgroups by conjugation
        orbs := OrbitsDomain(N, idx2, function(M, n) return M^n; end);
        te := Runtime() - ts;
        if te > 5000 then
            slow_count := slow_count + 1;
            slow_total_t := slow_total_t + te;
        fi;
        contrib := 1 + Length(orbs);
    fi;

    total := total + contrib;
    if i mod 500 = 0 then
        Print("  i=", i, "/", Length(groups), " total=", total,
              " elapsed=", (Runtime()-t0)/1000.0, "s slow_N>5s=", slow_count, "\n");
    fi;
od;
elapsed := (Runtime() - t0) / 1000.0;
Print("\nFinal: total = ", total, " in ", elapsed, "s\n");
Print("Disk count for [4,4,4,4,2]/[T(2,1),T(4,3)^4] = 250965\n");
Print("Delta = ", total - 250965, "\n");

LogTo();
QUIT;
