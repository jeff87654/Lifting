LogTo("C:/Users/jeffr/Downloads/Lifting/time_ra_in_W.log");

# Build same context as wreath predictor for [3,1]^6
DD := 3; TID := 1; M_BLOCKS := 6; M := (M_BLOCKS - 1) * DD;
TARGET_N := M + DD;

T_orig := TransitiveGroup(DD, TID);
N_T_canonical := Normalizer(SymmetricGroup(DD), T_orig);
W := WreathProduct(N_T_canonical, SymmetricGroup(M_BLOCKS));
S18 := SymmetricGroup(TARGET_N);

Print("|W|=", Size(W), " |S18|=", Size(S18), "\n");

# Build two random subgroups of W to test RA timing.
# Use direct product of T_orig in m blocks (a known subgroup of W).
shift_to_block := function(b)
    return MappingPermListList([1..DD], [(b-1)*DD + 1 .. b*DD]);
end;

T_blocks := List([1..M_BLOCKS], b -> T_orig^shift_to_block(b));
G1 := DirectProduct(T_blocks);
G2 := G1;   # same group: should give RA = ()

Print("|G1|=", Size(G1), "\n");

# Time RA in W
t0 := Runtime();
r := RepresentativeAction(W, G1, G2);
Print("RA(W, G1, G2) = ", r = (), " elapsed=", Runtime() - t0, "ms\n");

# Time RA in S18
t0 := Runtime();
r := RepresentativeAction(S18, G1, G2);
Print("RA(S18, G1, G2) = ", r = (), " elapsed=", Runtime() - t0, "ms\n");

# Now build a slightly different G2 (conjugate by some W elt) and time
g := Random(W);
G2 := G1^g;
t0 := Runtime();
r := RepresentativeAction(W, G1, G2);
Print("RA(W, G1, G1^g) succ=", r <> fail, " elapsed=", Runtime() - t0, "ms\n");
t0 := Runtime();
r := RepresentativeAction(S18, G1, G2);
Print("RA(S18, G1, G1^g) succ=", r <> fail, " elapsed=", Runtime() - t0, "ms\n");

# Two non-conjugate subgroups: take G2 = G1 reset with one block dropped
T_blocks_diff := List(T_blocks, x -> x);
T_blocks_diff[1] := Group([Identity(T_orig)])^shift_to_block(1);
G2 := DirectProduct(T_blocks_diff);
t0 := Runtime();
r := RepresentativeAction(W, G1, G2);
Print("RA(W, G1, G2_diff) fail=", r = fail, " elapsed=", Runtime() - t0, "ms\n");
t0 := Runtime();
r := RepresentativeAction(S18, G1, G2);
Print("RA(S18, G1, G2_diff) fail=", r = fail, " elapsed=", Runtime() - t0, "ms\n");

LogTo();
QUIT;
