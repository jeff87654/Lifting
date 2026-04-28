LogTo("C:/Users/jeffr/Downloads/Lifting/verify_444222.log");

# Char-orbit formula extended: [4,4,4,2,2,2]/[T(2,1)^3, T(4,3)^3] = D_4^3 × C_2^3
# For each FPF subdirect H ≤ D_4^3 in S_12, count subdirect K ≤ H × C_2^3
# covering all 6 blocks, dedup'd under partition normalizer.
#
# Strategy: for each H, enumerate (M, V) where M ≤ H normal index 2^e (e=1,2,3)
# AND H/M elementary abelian of dim e. For each such M, iterate isos H/M → V
# where V ≤ C_2^3 is subdirect of dim e. Count |GL(F_2, e)| for each.
# Sum over H = total candidates BEFORE dedup.

S18 := SymmetricGroup(18);
S12 := SymmetricGroup(12);

# Load D_4^3 base classes from S_12 [4,4,4]/[T(4,3)^3]
f := "C:/Users/jeffr/Downloads/Lifting/parallel_sn/12/[4,4,4]/[4,3]_[4,3]_[4,3].g";
fs := StringFile(f);
text := ReplacedString(fs, "\\\n", "");
groups := [];
for line in SplitString(text, "\n") do
    if Length(line) > 0 and line[1] = '[' then
        Add(groups, Group(EvalString(line)));
    fi;
od;
Print("Loaded ", Length(groups), " D_4^3 base subgroups\n");

# Enumerate subdirect V ≤ C_2^3
# V projects onto each C_2_i ⟺ V is not contained in {x_i = 0} for any i
# dim 1: V = ⟨(1,1,1)⟩
# dim 2: 4 of 7 dim-2 subspaces are subdirect
# dim 3: V = C_2^3
# Counts: dim1=1, dim2=4, dim3=1.

# Precompute |GL(F_2, e)|
gl_orders := [1, 6, 168];  # |GL(2,1)|=1, |GL(F_2,2)|=6, |GL(F_2,3)|=168
subdirect_counts := [1, 4, 1];  # # subdirect subspaces of dim e

# For each H, count contrib BEFORE Npart-dedup
# = sum_e (# normals M with H/M elementary abelian dim e) * subdirect_counts[e] * gl_orders[e]
# = sum_e #(H_ab → V) where V is subdirect of dim e, summed appropriately
# Wait, not quite. Let me re-derive.
#
# Count K ≤ H × C_2^3 subdirect on each C_2:
# K determined by:
# - L = K ∩ ({1} × C_2^3) ≤ C_2^3 (the C-side kernel)
# - V = proj_C(K) (subdirect subspace, V ⊇ L)
# - hom χ: H → V/L surjective
#
# Given L ≤ V ⊆ C_2^3 with V subdirect, count surj χ: H → V/L.
# Surj from H to V/L (elementary abelian of dim e := dim(V/L)) =
#   [number of surj F_2-linear from H_ab to F_2^e] * 1
# = product_{i=0..e-1} (|H_ab| - 2^i).
#
# Then for each (L, V): contrib = #surj(H, V/L).
#
# Total: sum over (L ≤ V ≤ C_2^3, V subdirect) of #surj(H, V/L).
# = sum over V subdirect of (sum over L ≤ V of #surj(H, V/L)).
# = sum over V subdirect of (sum over e=0..dim V of #(L of codim e in V) * #surj(H, F_2^e)).
# = sum over V subdirect of (sum over e=0..dim V of #(F_2^e -subspace of V) * #surj(H, F_2^e)).

# Number of e-dim subspaces of F_2^d (Gaussian binomial):
# [d, e]_2 = product_{i=0..e-1} (2^d - 2^i) / (2^e - 2^i)

GaussBin := function(d, e)
    local num, den, i;
    num := 1; den := 1;
    for i in [0..e-1] do
        num := num * (2^d - 2^i);
        den := den * (2^e - 2^i);
    od;
    return num / den;
end;

# Number of surjective F_2-linear maps from F_2^a to F_2^b (a >= b)
NumSurjF2 := function(a, b)
    local prod, i;
    if b > a then return 0; fi;
    prod := 1;
    for i in [0..b-1] do
        prod := prod * (2^a - 2^i);
    od;
    return prod;
end;

# Compute contrib(H) BEFORE Npart-dedup
# contrib(H) = sum over subdirect V ≤ C_2^3 of (sum over codim-e subspaces L ≤ V of #surj(H,V/L))
# Let dV = dim V, then sum over codim e (e=0..dV) of [dV, e]_2 * NumSurjF2(d_H, e).

# subdirect V counts: dim 1: 1 V; dim 2: 4 V; dim 3: 1 V

ContribPerH := function(d_H)
    local total, dV, count_V, e;
    total := 0;
    for dV in [1..3] do
        if dV = 1 then count_V := 1;
        elif dV = 2 then count_V := 4;
        else count_V := 1; fi;
        for e in [0..dV] do
            total := total + count_V * GaussBin(dV, e) * NumSurjF2(d_H, e);
        od;
    od;
    return total;
end;

# Apply BEFORE-dedup contrib for each H, then we need to dedup under N_S18(combo).
# But computing this dedup per H is hard. As a sanity check, let's first
# compute the total candidates count BEFORE dedup. If it matches the disk's
# "candidates: 1636520" then our formula is plausible.

cand_total := 0;
for i in [1..Length(groups)] do
    H := groups[i];
    d_H := Length(GeneratorsOfGroup(H/CommutatorSubgroup(H,H)));  # rough d_H via gen count
    # Actually d(H) = log2 of |H_ab / 2H_ab|. For 2-groups, H_ab is C_2^d.
    # For more accuracy, compute |H_ab| and check.
    H_ab := H / DerivedSubgroup(H);
    n_ab := Size(H_ab);
    # Dim over F_2: it's the number of generators in elementary abelian quotient
    if IsElementaryAbelian(H_ab) then
        d_H := LogInt(n_ab, 2);
    else
        # H_ab is abelian. Count F_2-rank: # invariants that are 2 (or even).
        # For 2-group H, H_ab is abelian of order 2^k. Maximum elementary abelian
        # quotient = H_ab / 2 H_ab. Dim of F_2 vector space = #2-torsion gens.
        d_H := Length(Filtered(AbelianInvariants(H_ab), x -> x mod 2 = 0));
    fi;
    cand_total := cand_total + ContribPerH(d_H);
    if i mod 50 = 0 then
        Print("  i=", i, " cand_total=", cand_total, "\n");
    fi;
od;
Print("\nTotal candidates (formula): ", cand_total, "\n");
Print("Disk candidates: 1,636,520\n");
Print("Disk deduped: 197,598\n");

LogTo();
QUIT;
