"""bench_fp_construct.py — test rig for profiling _GoursatBuildFiberProduct
variants on the live n=18 heavy combo.

LEFT  : [2,1]_[4,3]_[4,3]_[4,3]  (n=14, partition [4,4,4,2])
RIGHT : [4,1]                    (= C_4)
target: n=18, combo = [2,1]_[4,1]_[4,3]_[4,3]_[4,3], partition [4,4,4,4,2]

Reuses the live LEFT H_CACHE at:
  predict_species_tmp/_h_cache_topt/14/[4,4,4,2]/[2,1]_[4,3]_[4,3]_[4,3].g

Defines 3 _GoursatBuildFiberProduct variants:
  V0_BASELINE   — exact current code (with Size(H) verification)
  V1_NO_VERIFY  — skip the Size(H) order check
  V2_HOIST_KER  — V1 + hoisted Kernel(hom2) generators

For the first N H1 pairs (default 5), times each variant on each pair
and reports per-pair / per-fp timing.
"""
import argparse, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).parent
LIFTING_WS_CYG = "/cygdrive/c/Users/jeffr/Downloads/Lifting/lifting.ws"
CACHE_PATH = ROOT / "predict_species_tmp/_h_cache_topt/14/[4,4,4,2]/[2,1]_[4,3]_[4,3]_[4,3].g"

GAP_DRIVER = r"""
LogTo("__LOG__");

# Load lifting_algorithm for original _GoursatBuildFiberProduct + helpers
if not IsBound(_GoursatBuildFiberProduct) then
    Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
fi;

ML := 14;
MR := 4;
N_PAIRS := __NPAIRS__;

Print("=== bench_fp_construct ===\n");
Print("ML=", ML, " MR=", MR, " N_PAIRS=", N_PAIRS, "\n");

# === Variant V0: exact baseline (current code) ===
BuildFP_V0 := function(T1, T2, hom1, hom2, phi, pts1, pts2)
    local gens, g, img_q, preimg, kerGens, n, H, expectedOrder;
    gens := [];
    for g in GeneratorsOfGroup(T1) do
        img_q := Image(phi, Image(hom1, g));
        preimg := PreImagesRepresentative(hom2, img_q);
        Add(gens, g * preimg);
    od;
    kerGens := GeneratorsOfGroup(Kernel(hom2));
    for n in kerGens do Add(gens, n); od;
    gens := Filtered(gens, g -> g <> ());
    if Length(gens) = 0 then H := Group(()); else H := Group(gens); fi;
    expectedOrder := Size(Kernel(hom1)) * Size(T2);
    if Size(H) <> expectedOrder then
        return fail;
    fi;
    return H;
end;

# === Variant V1: skip Size(H) verification ===
BuildFP_V1 := function(T1, T2, hom1, hom2, phi, pts1, pts2)
    local gens, g, img_q, preimg, kerGens, n, H;
    gens := [];
    for g in GeneratorsOfGroup(T1) do
        img_q := Image(phi, Image(hom1, g));
        preimg := PreImagesRepresentative(hom2, img_q);
        Add(gens, g * preimg);
    od;
    kerGens := GeneratorsOfGroup(Kernel(hom2));
    for n in kerGens do Add(gens, n); od;
    gens := Filtered(gens, g -> g <> ());
    if Length(gens) = 0 then return Group(()); fi;
    return Group(gens);
end;

# === Variant V2: V1 + precomputed kerGens ===
BuildFP_V2 := function(T1, T2, hom1, hom2, phi, pts1, pts2, ker2_gens)
    local gens, g, img_q, preimg, n, H;
    gens := [];
    for g in GeneratorsOfGroup(T1) do
        img_q := Image(phi, Image(hom1, g));
        preimg := PreImagesRepresentative(hom2, img_q);
        Add(gens, g * preimg);
    od;
    for n in ker2_gens do Add(gens, n); od;
    gens := Filtered(gens, g -> g <> ());
    if Length(gens) = 0 then return Group(()); fi;
    return Group(gens);
end;

# === Helpers from predict_2factor_topt.py ===
SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;

# Reconstruct full H data (H, N_H, orbits with hom/Q/AutQ/A_gens) from cache entry
ReconstructHData := function(entry, S_M)
    local H, N_H, orbits, orec, K, hom, Q, Stab_NH_KH, AutQ, byqid, key, qid;
    H := Group(entry.H_gens);
    N_H := Group(entry.N_H_gens);
    orbits := [];
    byqid := rec();
    for orec in entry.orbits do
        K := Group(orec.K_H_gens);
        hom := NaturalHomomorphismByNormalSubgroup(H, K);
        Q := Range(hom);
        Stab_NH_KH := Group(orec.Stab_NH_KH_gens);
        # A_gens: induced action of N_H-stabilizer on Q
        # For simplicity in this benchmark, skip AutQ derivation; we use trivial A_gens
        # (this skews V0/V1/V2 timings only insofar as fp construction; orbit BFS uses A_gens but we're not benching that)
        Add(orbits, rec(H := H, K := K, hom := hom, Q := Q,
                       qsize := Size(Q), qid := orec.qid,
                       Stab_NH_KH := Stab_NH_KH));
        key := String(orec.qid);
        if not IsBound(byqid.(key)) then byqid.(key) := []; fi;
        Add(byqid.(key), Length(orbits));
    od;
    return rec(H := H, N_H := N_H, orbits := orbits, byqid := byqid);
end;

# Load LEFT cache
Print("loading LEFT cache from disk... ");
t0 := Runtime();
Read("__CACHE__");
Print(Runtime() - t0, "ms; ", Length(H_CACHE), " H entries\n");

# Build W_ML (block wreath for [4,4,4,2])
W_ML := SymmetricGroup(ML);  # close enough for fp construction; partition normalizer not needed for bench

# Reconstruct first N_PAIRS LEFT H entries
Print("reconstructing first ", N_PAIRS, " LEFT H entries... ");
t0 := Runtime();
H1_DATA := List([1..N_PAIRS], i -> ReconstructHData(H_CACHE[i], W_ML));
Print(Runtime() - t0, "ms\n");

# Build RIGHT side: T = TG(4,1) = C_4
T_R := TransitiveGroup(4, 1);
S_MR := SymmetricGroup(MR);
N_TR := Normalizer(S_MR, T_R);

# Compute RIGHT cache: normal subgroups of C_4 (excluding T_R itself), grouped by N_TR-orbits
Print("building RIGHT cache for C_4... ");
t0 := Runtime();
RIGHT_NORMALS := Filtered(NormalSubgroups(T_R), K -> K <> T_R);
RIGHT_ORBITS := [];
RIGHT_BYQID := rec();
for K in RIGHT_NORMALS do
    hom := NaturalHomomorphismByNormalSubgroup(T_R, K);
    Q := Range(hom);
    qid := SafeId(Q);
    Add(RIGHT_ORBITS, rec(H := T_R, K := K, hom := hom, Q := Q,
                          qsize := Size(Q), qid := qid,
                          Stab_NH_KH := T_R));
    key := String(qid);
    if not IsBound(RIGHT_BYQID.(key)) then RIGHT_BYQID.(key) := []; fi;
    Add(RIGHT_BYQID.(key), Length(RIGHT_ORBITS));
od;
H2DATA := rec(H := T_R, N_H := N_TR, orbits := RIGHT_ORBITS, byqid := RIGHT_BYQID);
Print(Runtime() - t0, "ms; ", Length(RIGHT_ORBITS), " RIGHT orbits\n");
Print("RIGHT qids: ");
for o in RIGHT_ORBITS do Print(o.qid, " "); od;
Print("\n");

# Shift R into [ML+1..ML+MR]
shift_R := MappingPermListList([1..MR], [ML+1..ML+MR]);
T_R_shifted := T_R^shift_R;

# Bench loop: for each H1 pair, find matching K's with RIGHT and time fp construction
Print("\n=== timing per pair ===\n");
pad := function(x, w) local s; s := String(x); while Length(s) < w do s := Concatenation(" ", s); od; return s; end;
Print(pad("i",5), pad("|H1|",7), pad("n_match",10), pad("fps",6), pad("V0_ms",9), pad("V1_ms",9), pad("V2_ms",9), pad("vs_V0",8), pad("OK",6), "\n");

total_v0 := 0; total_v1 := 0; total_v2 := 0; total_fps := 0;

for i in [1..N_PAIRS] do
    H1d := H1_DATA[i];
    H1 := H1d.H;
    n_match := 0;
    fps_v0 := []; fps_v1 := []; fps_v2 := [];

    t0 := Runtime();
    for h1orb in H1d.orbits do
        key := String(h1orb.qid);
        if not IsBound(H2DATA.byqid.(key)) then continue; fi;
        for h2idx in H2DATA.byqid.(key) do
            h2orb := H2DATA.orbits[h2idx];
            if h2orb.qsize <> h1orb.qsize then continue; fi;

            isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
            if isoTH = fail then continue; fi;

            # For benchmark, use just a single iso (no Aut(Q) BFS — that's not what we're profiling)
            # Compose the right-shift into hom2
            hom2_shifted := CompositionMapping(h2orb.hom, ConjugatorIsomorphism(T_R_shifted, shift_R^-1));
            # Note: to apply hom2 we need T_R_shifted. h2orb.hom takes input from T_R, need to shift back.
            # Actually simpler: hom2 takes T_R_shifted -> Q via inverse-shift-then-hom.

            n_match := n_match + 1;
            fp_v0 := BuildFP_V0(H1, T_R_shifted, h1orb.hom, hom2_shifted,
                                InverseGeneralMapping(isoTH),
                                [1..ML], [ML+1..ML+MR]);
            Add(fps_v0, fp_v0);
        od;
    od;
    t_v0 := Runtime() - t0;

    t0 := Runtime();
    for h1orb in H1d.orbits do
        key := String(h1orb.qid);
        if not IsBound(H2DATA.byqid.(key)) then continue; fi;
        for h2idx in H2DATA.byqid.(key) do
            h2orb := H2DATA.orbits[h2idx];
            if h2orb.qsize <> h1orb.qsize then continue; fi;
            isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
            if isoTH = fail then continue; fi;
            hom2_shifted := CompositionMapping(h2orb.hom, ConjugatorIsomorphism(T_R_shifted, shift_R^-1));
            fp_v1 := BuildFP_V1(H1, T_R_shifted, h1orb.hom, hom2_shifted,
                                InverseGeneralMapping(isoTH),
                                [1..ML], [ML+1..ML+MR]);
            Add(fps_v1, fp_v1);
        od;
    od;
    t_v1 := Runtime() - t0;

    t0 := Runtime();
    for h1orb in H1d.orbits do
        key := String(h1orb.qid);
        if not IsBound(H2DATA.byqid.(key)) then continue; fi;
        for h2idx in H2DATA.byqid.(key) do
            h2orb := H2DATA.orbits[h2idx];
            if h2orb.qsize <> h1orb.qsize then continue; fi;
            isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
            if isoTH = fail then continue; fi;
            hom2_shifted := CompositionMapping(h2orb.hom, ConjugatorIsomorphism(T_R_shifted, shift_R^-1));
            ker2_gens := GeneratorsOfGroup(Kernel(hom2_shifted));
            fp_v2 := BuildFP_V2(H1, T_R_shifted, h1orb.hom, hom2_shifted,
                                InverseGeneralMapping(isoTH),
                                [1..ML], [ML+1..ML+MR],
                                ker2_gens);
            Add(fps_v2, fp_v2);
        od;
    od;
    t_v2 := Runtime() - t0;

    # Correctness: V1 and V2 should produce groups equal in size to V0's (V0 verifies & returns)
    ok := true;
    for j in [1..Length(fps_v0)] do
        if fps_v0[j] = fail then ok := false; break; fi;
        if Size(fps_v0[j]) <> Size(fps_v1[j]) then ok := false; break; fi;
        if Size(fps_v0[j]) <> Size(fps_v2[j]) then ok := false; break; fi;
    od;

    if ok then m_str := "OK"; else m_str := "DIFF"; fi;
    speedup := String(Float(t_v0) / Float(Maximum(t_v2, 1)));
    Print(pad(i,5), pad(Size(H1),7), pad(n_match,10), pad(Length(fps_v0),6),
          pad(t_v0,9), pad(t_v1,9), pad(t_v2,9), pad(speedup{[1..Minimum(7,Length(speedup))]},8), pad(m_str,6), "\n");

    total_v0 := total_v0 + t_v0;
    total_v1 := total_v1 + t_v1;
    total_v2 := total_v2 + t_v2;
    total_fps := total_fps + Length(fps_v0);
od;

Print("\n=== summary ===\n");
Print("total fps  : ", total_fps, "\n");
Print("V0 total ms: ", total_v0, "  (", Float(total_v0)/Float(Maximum(total_fps,1)), " ms/fp)\n");
Print("V1 total ms: ", total_v1, "  (", Float(total_v1)/Float(Maximum(total_fps,1)), " ms/fp)\n");
Print("V2 total ms: ", total_v2, "  (", Float(total_v2)/Float(Maximum(total_fps,1)), " ms/fp)\n");
Print("speedup V1/V0: ", Float(total_v0)/Float(Maximum(total_v1,1)), "\n");
Print("speedup V2/V0: ", Float(total_v0)/Float(Maximum(total_v2,1)), "\n");

LogTo();
QUIT;
"""

def run_bench(npairs, log_path, gap_path):
    g = (GAP_DRIVER
         .replace("__LOG__", str(log_path).replace("\\", "/"))
         .replace("__CACHE__", str(CACHE_PATH).replace("\\", "/"))
         .replace("__NPAIRS__", str(npairs)))
    gap_path.write_text(g, encoding="utf-8")

    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    g_cyg = "/cygdrive/c/" + str(gap_path)[3:].replace("\\", "/")
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"

    cmd = (f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
           f'./gap.exe -q -o 0 -L "{LIFTING_WS_CYG}" "{g_cyg}"')
    print(f"running bench (npairs={npairs})...")
    t0 = time.time()
    proc = subprocess.run([bash_exe, "--login", "-c", cmd],
                          env=env, capture_output=True, text=True,
                          timeout=4*3600)
    print(f"done in {time.time()-t0:.0f}s")
    if log_path.exists():
        print("--- log ---")
        print(log_path.read_text())
    if proc.stderr:
        print("--- stderr ---")
        print(proc.stderr[-1500:])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--npairs", type=int, default=3)
    args = ap.parse_args()
    sandbox = ROOT / "bench_fp_construct_tmp"
    sandbox.mkdir(exist_ok=True)
    log_path = sandbox / "bench.log"
    if log_path.exists(): log_path.unlink()
    gap_path = sandbox / "bench.g"
    run_bench(args.npairs, log_path, gap_path)
