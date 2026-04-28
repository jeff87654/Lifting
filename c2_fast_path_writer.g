# c2_fast_path_writer.g — invoke the legacy C_2^n linear-algebra fast path
# (FindSubdirectsForPartitionWith2s) and write its results in legacy
# parallel_sn format.
#
# Inputs (substituted by Python):
#   PARTITION_STR     — GAP list literal, e.g. "[6,4,2,2]"
#   COMBO_STR         — GAP list literal of (d,t) pairs, e.g.
#                       "[[6,1],[4,3],[2,1],[2,1]]"
#   OUTPUT_PATH_CYG   — Cygwin path for the output combo .g file.
#   LOG_PATH_CYG      — Cygwin path for GAP log.
#
# The script must:
#   1. Build transitive factors and their shifted-into-blocks copies.
#   2. Call FindSubdirectsForPartitionWith2s.
#   3. Apply post-dedup if needed (matches the dispatch in
#      lifting_method_fast_v2.g:2899-2934).
#   4. Write standard `# combo / # candidates / # deduped / # elapsed_ms`
#      header followed by one bracketed generator list per group.

LogTo("__LOG_PATH__");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

PARTITION  := __PARTITION_STR__;
COMBO      := __COMBO_STR__;
OUTPUT     := "__OUTPUT_PATH__";

Print("c2_fast_path: partition=", PARTITION, " combo=", COMBO, "\n");

# Reorder COMBO to match PARTITION (sorted descending by d).
# Legacy `FindSubdirectsForPartitionWith2s` expects transFactors in partition
# order so that the trailing 2's correspond to the trailing C_2 entries.
COMBO_SORTED := ShallowCopy(COMBO);
SortBy(COMBO_SORTED, x -> -x[1]);   # descending by degree d
# (Within same d, preserve relative order — stable sort.)

# Build transitive factors per (d, t) entry, shifted into their block.
N_TARGET   := Sum(PARTITION);
trans_factors := [];
shifted_factors := [];
offsets := [];
off := 0;
for i in [1..Length(COMBO_SORTED)] do
    d := COMBO_SORTED[i][1];
    t := COMBO_SORTED[i][2];
    Add(trans_factors, TransitiveGroup(d, t));
    Add(offsets, off);
    Add(shifted_factors,
        TransitiveGroup(d, t)^MappingPermListList([1..d], [off+1..off+d]));
    off := off + d;
od;

# Run the C_2 fast path.
t0 := Runtime();
result := FindSubdirectsForPartitionWith2s(PARTITION, trans_factors,
                                            shifted_factors, offsets);
DO_QUIT_EARLY := false;
if result = fail then
    Print("c2_fast_path: NOT_APPLICABLE (FindSubdirectsForPartitionWith2s returned fail)\n");
    PrintTo(OUTPUT, "# c2_fast_path: NOT_APPLICABLE\n");
    DO_QUIT_EARLY := true;
fi;
n_candidates := 0;
if not DO_QUIT_EARLY then
    t_subdirect := Runtime() - t0;
    n_candidates := Length(result);
    Print("c2_fast_path: ", n_candidates, " candidates in ", t_subdirect, "ms\n");
fi;

# Wrap the rest in `if not DO_QUIT_EARLY` so we can avoid the early QUIT.
deduped := [];
if not DO_QUIT_EARLY then

# Post-dedup for elementary-abelian P.  Always runs when P is EA.
# (The legacy code at lifting_method_fast_v2.g:2899-2934 had a `Length > 50`
# gate, but it relied on a downstream `incrementalDedup` to catch small
# cases.  Standalone, we have no downstream — so always GF(2)-dedup.)
# GF(2) is O(N^2 * dim_P) on tiny N — takes milliseconds.
P := Group(Concatenation(List(shifted_factors, GeneratorsOfGroup)));
P_is_EA := IsElementaryAbelian(P);
deduped := result;
if P_is_EA and Length(result) > 0 then
    Print("c2_fast_path: GF(2) post-dedup on ", Length(result), " candidates\n");
    N := Normalizer(SymmetricGroup(N_TARGET), P);
    deduped := _DeduplicateEAFPFbyGF2Orbits(P, result, N);
    Print("c2_fast_path: post-dedup -> ", Length(deduped), "\n");
fi;

# Final Sn-conjugacy dedup.
#
# Theoretical note: when P is elementary abelian (combo of all (2,t)'s), the
# GF(2)-orbit dedup above already gave Norm(S_n, P)-orbit reps. For an FPF
# subgroup H \subseteq P with orbital structure [2,2,...,2], any element
# g \in S_n with g H g^{-1} \subseteq P preserves the block partition (the
# orbits of P), hence g \in Norm(S_n, P). So the GF(2) orbits ARE the
# S_n orbits, and the pairwise RA loop is redundant. We skip it for EA P.
#
# For non-EA P (mixed-degree combo, e.g. [(d,t),(2,1),(2,1)] with d>2) we
# still run the pairwise RA in S_n.

S_target := SymmetricGroup(N_TARGET);
n_in := Length(deduped);

if P_is_EA then
    Print("c2_fast_path: skipping pairwise Sn dedup (EA P, GF(2) orbits = Sn orbits)\n");
    rep_indices := [1..n_in];
    n_distinct := n_in;
else
    fp_fp := function(G)
        local sz, abi, ds;
        sz := Size(G);
        abi := AbelianInvariants(G);
        ds := List(DerivedSeries(G), Size);
        if IdGroupsAvailable(sz) then return [sz, IdGroup(G), abi, ds]; fi;
        return [sz, abi, ds];
    end;

    fps := List(deduped, fp_fp);
    parent := [1..n_in];
    UF_Find := function(x)
        while parent[x] <> x do
            parent[x] := parent[parent[x]]; x := parent[x];
        od;
        return x;
    end;
    UF_Union := function(x, y)
        local rx, ry;
        rx := UF_Find(x); ry := UF_Find(y);
        if rx <> ry then parent[ry] := rx; fi;
    end;

    bucket_keys := [];
    bucket_lists := [];
    for ii in [1..n_in] do
        pos := Position(bucket_keys, fps[ii]);
        if pos = fail then
            Add(bucket_keys, fps[ii]);
            Add(bucket_lists, [ii]);
        else
            Add(bucket_lists[pos], ii);
        fi;
    od;

    t_ra := Runtime();
    n_ra_calls := 0;
    for b in [1..Length(bucket_lists)] do
        bk := bucket_lists[b];
        for ii in [1..Length(bk)-1] do
            for jj in [ii+1..Length(bk)] do
                if UF_Find(bk[ii]) = UF_Find(bk[jj]) then continue; fi;
                n_ra_calls := n_ra_calls + 1;
                if RepresentativeAction(S_target, deduped[bk[ii]], deduped[bk[jj]]) <> fail then
                    UF_Union(bk[ii], bk[jj]);
                fi;
            od;
        od;
    od;
    classes := Set([1..n_in], i -> UF_Find(i));
    Print("c2_fast_path: Sn dedup -> ", Length(classes), " distinct (", n_ra_calls,
          " RA calls in ", Runtime() - t_ra, "ms)\n");

    rep_indices := [];
    seen_class := rec();
    for ii in [1..n_in] do
        cls := UF_Find(ii);
        cls_key := String(cls);
        if not IsBound(seen_class.(cls_key)) then
            seen_class.(cls_key) := true;
            Add(rep_indices, ii);
        fi;
    od;
    n_distinct := Length(rep_indices);
fi;

# Format the combo string for header (matches "[ [ d, t ], [ d, t ], ... ]").
combo_str := "[ ";
for i in [1..Length(COMBO)] do
    if i > 1 then combo_str := Concatenation(combo_str, ", "); fi;
    combo_str := Concatenation(combo_str,
        "[ ", String(COMBO[i][1]), ", ", String(COMBO[i][2]), " ]");
od;
combo_str := Concatenation(combo_str, " ]");

# Write legacy-format output ATOMICALLY: write to OUTPUT.tmp, then mv to OUTPUT.
# This prevents partial-file corruption if GAP crashes mid-write.
elapsed_ms := Runtime() - t0;
TMP_OUT := Concatenation(OUTPUT, ".tmp");
PrintTo(TMP_OUT, "# combo: ", combo_str, "\n");
AppendTo(TMP_OUT, "# candidates: ", n_candidates, "\n");
AppendTo(TMP_OUT, "# deduped: ", n_distinct, "\n");
AppendTo(TMP_OUT, "# elapsed_ms: ", elapsed_ms, "\n");
for i in rep_indices do
    gens := GeneratorsOfGroup(deduped[i]);
    if Length(gens) > 0 then
        gens_s := JoinStringsWithSeparator(List(gens, String), ",");
    else
        gens_s := "";
    fi;
    AppendTo(TMP_OUT, "[", gens_s, "]\n");
od;
Exec(Concatenation("mv -f -- '", TMP_OUT, "' '", OUTPUT, "'"));

Print("RESULT predicted=", n_distinct, " candidates=", n_candidates,
      " elapsed_ms=", elapsed_ms, "\n");

fi;  # end of `if not DO_QUIT_EARLY`

LogTo();
QUIT;
