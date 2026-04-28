###############################################################################
# Compute and cache FPF subdirect products of D_4^3 under N_{[4,4,4]}.
#
# These are subgroups K <= D_4 x D_4 x D_4 (acting on 12 points as 3 blocks
# of 4) such that:
#   - K projects surjectively onto each D_4 factor
#   - Orbit representatives under the partition normalizer of [4,4,4]
#     (which includes S_3 block swaps + per-block N_{S_4}(D_4) = S_4)
#
# Output: a file containing the generating sets of each subdirect product.
###############################################################################
LogTo("C:/Users/jeffr/Downloads/Lifting/compute_d4_cube_cache.log");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\n=== Computing D_4^3 subdirect cache ===\n\n");

# Build the combo: [4,3] x [4,3] x [4,3] on degree 12
combo := [[4,3], [4,3], [4,3]];
shifted := [];
offs := [];
pos := 0;
for c in combo do
    G := TransitiveGroup(c[1], c[2]);
    Add(shifted, ShiftGroup(G, pos));
    Add(offs, pos);
    pos := pos + c[1];
od;

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P = D_4 x D_4 x D_4, |P| = ", Size(P), "\n");

# Build partition normalizer of [4,4,4]
# = (N_{S_4}(D_4))^3 semi-direct S_3 (block swap)
# N_{S_4}(D_4) = S_4 (D_4 is normalized by S_4 since [S_4:D_4]=3 and S_4 has D_4 as Sylow-2)
# Actually N_{S_4}(D_4) = D_4 itself for some reps; let's just use BuildPerComboNormalizer
partition := [4,4,4];
normArg := BuildPerComboNormalizer(partition, shifted, 12);
Print("|N_[4,4,4]| (per-combo) = ", Size(normArg), "\n\n");

# Run the lifting to get D_4^3 subdirects
Print("Running FindFPFClassesByLifting...\n");
t0 := Runtime();
subdirects := FindFPFClassesByLifting(P, shifted, offs, normArg);
tLift := Runtime() - t0;
Print("Lifting completed in ", tLift, "ms\n");
Print("Raw subdirect count (before final dedup): ", Length(subdirects), "\n\n");

# The result from lifting is the raw candidate list. We need to dedup under
# the partition normalizer to get canonical representatives.
Print("Deduplicating under partition normalizer...\n");
t0 := Runtime();
CURRENT_BLOCK_RANGES := [[1,4], [5,8], [9,12]];
byInv := rec();
deduped := [];
for H in subdirects do
    inv := CheapSubgroupInvariantFull(H);
    key := InvariantKey(inv);
    if IsBound(byInv.(key)) then
        isDup := false;
        for rep in byInv.(key) do
            if RepresentativeAction(normArg, H, rep) <> fail then
                isDup := true; break;
            fi;
        od;
        if not isDup then
            Add(byInv.(key), H);
            Add(deduped, H);
        fi;
    else
        byInv.(key) := [H];
        Add(deduped, H);
    fi;
od;
tDedup := Runtime() - t0;
Print("Deduped count: ", Length(deduped), " (", tDedup, "ms)\n\n");

# Save the cache to a file
cacheFile := "C:/Users/jeffr/Downloads/Lifting/database/d4_cube_cache.g";
PrintTo(cacheFile, "# D_4^3 FPF subdirect cache (N_[4,4,4] orbit reps)\n");
AppendTo(cacheFile, "# Total: ", Length(deduped), " subdirects\n");
AppendTo(cacheFile, "# Built\n");
AppendTo(cacheFile, "D4_CUBE_CACHE := [\n");
for i in [1..Length(deduped)] do
    gens := GeneratorsOfGroup(deduped[i]);
    AppendTo(cacheFile, "  ", gens);
    if i < Length(deduped) then
        AppendTo(cacheFile, ",");
    fi;
    AppendTo(cacheFile, "\n");
od;
AppendTo(cacheFile, "];\n");
Print("Cache saved to ", cacheFile, "\n");
Print("Total file size: ", Length(deduped), " groups\n");

LogTo();
QUIT;
