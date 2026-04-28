"""
Re-run the 3 skipped combos from [14,2] using direct fiber product construction.

For G1 x C2 where G1 = TransitiveGroup(14,k):
- FPF subdirects = {full product} ∪ {fiber product H_K : K is index-2 subgroup of G1}
- All of these are FPF (projection onto each factor is surjective + transitive)
- They are non-conjugate under P (index-2 subgroups are normal)
- So #classes = 1 + #index_2_subgroups(G1)

To find index-2 subgroups without NaturalHomomorphismByNormalSubgroup:
- Convert G1 to FP group, compute abelian invariants from relator matrix
- Count r = #even invariants, giving 2^r - 1 index-2 subgroups
- Find the actual subgroups via kernel of sign-like homomorphisms
"""

import subprocess
import os
import sys
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
OUTPUT_DIR = os.path.join(LIFTING_DIR, "parallel_s16")

log_file = os.path.join(OUTPUT_DIR, "skipped_combos.log").replace("\\", "/")
result_file = os.path.join(OUTPUT_DIR, "skipped_combos_results.txt").replace("\\", "/")
gens_file = os.path.join(OUTPUT_DIR, "gens", "gens_14_2_skipped.txt").replace("\\", "/")

gap_code = f'''
LogTo("{log_file}");
Print("Skipped combos retry (direct method) at ", StringTime(Runtime()), "\\n");

# We do NOT load the lifting code - we construct FPF subdirects directly
# to avoid any NaturalHomomorphismByNormalSubgroup calls.

skippedIDs := [54, 55, 57];

totalNew := 0;
PrintTo("{gens_file}", "");  # Clear previous

for tid in skippedIDs do
    Print("\\n========================================\\n");
    G1 := TransitiveGroup(14, tid);
    Print("TransitiveGroup(14,", tid, "), |G1| = ", Size(G1), "\\n");

    # Step 1: Find index-2 subgroups of G1 without forming quotient
    # Method: convert to FP group, compute abelianization via Smith normal form,
    # then find the actual kernels by testing generator images.

    D := DerivedSubgroup(G1);
    idx := Size(G1) / Size(D);
    Print("  [G1:G1'] = ", idx, "\\n");

    if idx mod 2 <> 0 then
        # No index-2 subgroups => only the full product is FPF
        Print("  No index-2 subgroups (abelianization has odd order)\\n");

        # The full product G1 x C2 is the only FPF subdirect
        # Construct it as a permutation group on {{1..16}}
        gens16 := List(GeneratorsOfGroup(G1), g -> g);  # Already acts on {{1..14}}
        Add(gens16, (15,16));
        H := Group(gens16);

        gensH := List(GeneratorsOfGroup(H), g -> ListPerm(g, 16));
        AppendTo("{gens_file}", String(gensH), "\\n");

        totalNew := totalNew + 1;
        Print("  => 1 FPF class (full product only)\\n");
    else
        # Find ALL index-2 subgroups by testing sign assignments on generators
        gens := GeneratorsOfGroup(G1);
        k := Length(gens);
        Print("  ", k, " generators, testing 2^", k, " = ", 2^k, " sign assignments\\n");

        idx2subs := [];

        # For each non-zero assignment of signs to generators:
        # b = [b_1, ..., b_k] where b_i in {{0,1}}
        # Define phi: G1 -> C2 by phi(g_i) = b_i
        # Check if phi is a homomorphism:
        #   phi(g_i * g_j) = phi(g_i) + phi(g_j) mod 2 for all i,j
        #   We verify by checking phi is well-defined on all elements
        #   reachable from generators.
        # Simpler: compute the kernel K = <g_i : b_i=0, g_i*g_j : b_i=b_j=1, ...>
        # and check if [G1:K] = 2.

        # Actually, the cleanest method:
        # For each candidate phi (non-trivial), define:
        #   K = Subgroup(G1, [g_i*g_j : b_i=b_j=1] union [g_i : b_i=0])
        # If K has index 2, it's a valid kernel.
        # But more directly: we compute all index-2 subgroups.

        # METHOD: Use the fact that Hom(G, C2) = Hom(G/G', C2).
        # G/G' is abelian. Instead of forming the quotient, work with coset reps.
        # For each generator g_i, its image in G/G' is the coset g_i * G'.
        # A homomorphism G/G' -> C2 sends each coset to 0 or 1.
        # The constraint is: if g_i * G' has order n_i in G/G',
        # then b_i * n_i = 0 mod 2, so b_i = 0 if n_i is odd.

        # Compute the order of each generator mod G'
        genOrders := [];
        for i in [1..k] do
            g := gens[i];
            ord := 1;
            h := g;
            while not h in D do
                h := h * g;
                ord := ord + 1;
            od;
            Add(genOrders, ord);
        od;
        Print("  Generator orders mod G': ", genOrders, "\\n");

        # For each generator with even order mod G', we can set b_i = 0 or 1.
        # For odd order mod G', we MUST set b_i = 0.
        # This gives us the assignments that are at least potentially valid.

        # But we also need to check consistency: the map must be a homomorphism.
        # For generators g_i, g_j with even orders, we need:
        #   phi(g_i * g_j) = phi(g_i) + phi(g_j) mod 2
        # where phi(g_i * g_j) is determined by the coset of g_i * g_j in G/G'.

        # Simpler approach: just iterate over all 2^k - 1 non-trivial assignments,
        # compute the kernel as a subgroup, and check its index.

        for bits in [1..2^k - 1] do
            # Build candidate kernel generators
            kernelGens := [];
            cosetRep := fail;  # An element NOT in the kernel

            for i in [1..k] do
                bi := RemInt(QuoInt(bits, 2^(i-1)), 2);
                if bi = 0 then
                    # g_i maps to 0 (identity in C2), so g_i is in kernel
                    Add(kernelGens, gens[i]);
                else
                    # g_i maps to 1, so g_i is NOT in kernel
                    if cosetRep = fail then
                        cosetRep := gens[i];
                    else
                        # g_i * cosetRep^(-1) IS in kernel (both map to 1)
                        Add(kernelGens, gens[i] * cosetRep^(-1));
                    fi;
                fi;
            od;

            if cosetRep = fail then
                continue;  # All generators map to 0 => trivial homomorphism
            fi;

            # Also add squares of non-kernel generators (they map to 0)
            Add(kernelGens, cosetRep^2);

            K := Subgroup(G1, kernelGens);

            if Index(G1, K) = 2 then
                # Valid index-2 subgroup found!
                # Check if we already have it
                isNew := true;
                for prevK in idx2subs do
                    if K = prevK then
                        isNew := false;
                        break;
                    fi;
                od;
                if isNew then
                    Add(idx2subs, K);
                fi;
            fi;
        od;

        numIdx2 := Length(idx2subs);
        Print("  Found ", numIdx2, " index-2 subgroups\\n");

        # Now construct all FPF subdirects:
        # 1. Full product G1 x C2
        gens16 := List(GeneratorsOfGroup(G1), g -> g);
        Add(gens16, (15,16));
        H_full := Group(gens16);
        gensH := List(GeneratorsOfGroup(H_full), g -> ListPerm(g, 16));
        AppendTo("{gens_file}", String(gensH), "\\n");

        # 2. For each index-2 subgroup K, construct fiber product
        for K in idx2subs do
            fiberGens := List(GeneratorsOfGroup(K), g -> g);  # Kernel elements: (k, id)

            # Find a coset representative: any g in G1 \\ K
            for g in GeneratorsOfGroup(G1) do
                if not g in K then
                    Add(fiberGens, g * (15,16));  # Non-kernel: (g, swap)
                    break;
                fi;
            od;

            H_fiber := Group(fiberGens);
            gensH := List(GeneratorsOfGroup(H_fiber), g -> ListPerm(g, 16));
            AppendTo("{gens_file}", String(gensH), "\\n");
        od;

        totalNew := totalNew + 1 + numIdx2;
        Print("  => ", 1 + numIdx2, " FPF classes\\n");
    fi;
od;

Print("\\n========================================\\n");
Print("Total new FPF classes from skipped combos: ", totalNew, "\\n");
PrintTo("{result_file}", "SKIPPED_TOTAL ", String(totalNew), "\\n");

LogTo();
QUIT;
'''

script_file = os.path.join(OUTPUT_DIR, "skipped_combos.g")
with open(script_file, "w") as f:
    f.write(gap_code)

# Clear previous output
for fn in [os.path.join(OUTPUT_DIR, "skipped_combos_results.txt"),
           os.path.join(OUTPUT_DIR, "gens", "gens_14_2_skipped.txt")]:
    if os.path.exists(fn):
        os.remove(fn)

script_cygwin = script_file.replace("C:\\", "/cygdrive/c/").replace("\\", "/")

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print(f"Launching skipped combos (direct method)...")
print(f"Log: {log_file}")

process = subprocess.Popen(
    cmd,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    env=env,
    cwd=GAP_RUNTIME
)

print(f"PID: {process.pid}")
print(f"Monitoring...")

for i in range(60):  # Monitor for up to 5 minutes
    time.sleep(5)
    rc = process.poll()
    if rc is not None:
        print(f"Process exited with code {rc}")
        break

    log_path = os.path.join(OUTPUT_DIR, "skipped_combos.log")
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            lines = f.readlines()
        if lines:
            last = lines[-1].strip()
            print(f"  [{(i+1)*5}s] ({len(lines)} lines) {last}")
    else:
        print(f"  [{(i+1)*5}s] No log yet...")

# Check results
result_path = os.path.join(OUTPUT_DIR, "skipped_combos_results.txt")
if os.path.exists(result_path):
    with open(result_path, "r") as f:
        print(f"\nResults: {f.read().strip()}")

log_path = os.path.join(OUTPUT_DIR, "skipped_combos.log")
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        lines = f.readlines()
    print(f"\nLog tail:")
    for line in lines[-20:]:
        print(f"  {line.rstrip()}")
