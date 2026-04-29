"""scan_full_aut_population.py — characterize the saturation distribution
on real production caches.

For each (cache, ML, right_d, right_t) target:
  Load LEFT cache + build RIGHT cache
  Walk H1 entries (sample SAMPLE_N), compute orbit-by-orbit (qsize, qid, |AutQ|, full_aut)
  For each (h1orb, h2orb) match: categorize as
    triv     - h1.qsize=1 (always saturates)
    q2       - h1.qsize=2 (Aut trivial, saturates)
    h2sat    - h2.full_aut=true (skip h1.AutQ in the optimization)
    h1sat    - h1.full_aut=true and not h2sat
    bfs      - both unsaturated (BFS or DoubleCosets needed)

For BFS-bound matches, also report the (qsize, |AutQ|) histogram so we can
see how big the unsaturated Auts are.

Output: scan_full_aut_population_tmp/scan.log
"""
import os, subprocess, time
from pathlib import Path

ROOT = Path(__file__).parent
LIFTING_WS_CYG = "/cygdrive/c/Users/jeffr/Downloads/Lifting/lifting.ws"

# (label, cache_path_relative, ML, right_d, right_t, sample_n)
TARGETS = [
    # 1. Slowest n=18 combo's LEFT (used in [2,1]_[4,2]_[4,3]_[4,3]_[4,3])
    ("n16_4444_AAA_x_A4",
     "predict_species_tmp/_h_cache_topt/16/[4,4,4,4]/[4,3]_[4,3]_[4,3]_[4,3].g",
     16, 4, 3, 200),
    # 2. Currently-running production LEFT vs V_4
    ("n15_44322_2123AA_x_V4",
     "predict_species_tmp/_h_cache_topt/15/[4,4,3,2,2]/[2,1]_[2,1]_[3,2]_[4,3]_[4,3].g",
     15, 4, 2, 200),
    # 3. Currently-running production LEFT vs A_4 (alternative right)
    ("n15_44322_2123AA_x_A4",
     "predict_species_tmp/_h_cache_topt/15/[4,4,3,2,2]/[2,1]_[2,1]_[3,2]_[4,3]_[4,3].g",
     15, 4, 3, 200),
    # 4. n=18 combo with [8,22] as RIGHT — LEFT uses pivot [8,22], so cache is [2,1]_[4,3]_[4,3]
    ("n10_442_21AA_x_TG822",
     "predict_species_tmp/_h_cache_topt/10/[4,4,2]/[2,1]_[4,3]_[4,3].g",
     10, 8, 22, 200),
    # 5. Same LEFT vs TG(8,35) (another slow-combo right)
    ("n10_442_21AA_x_TG835",
     "predict_species_tmp/_h_cache_topt/10/[4,4,2]/[2,1]_[4,3]_[4,3].g",
     10, 8, 35, 200),
]

GAP_DRIVER = r"""
LogTo("__LOG__");
if not IsBound(_GoursatBuildFiberProduct) then
    Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
fi;

# ---- helpers ----
ConjAction := function(K, g) return K^g; end;
SafeId := function(G)
    local n;
    n := Size(G);
    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;
    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];
end;
InducedAutoGens := function(stab, G, hom)
    return List(GeneratorsOfGroup(stab),
        s -> InducedAutomorphism(hom, ConjugatorAutomorphism(G, s)));
end;
SafeGroup := function(gens, default_amb)
    if Length(gens) = 0 then return TrivialSubgroup(default_amb); fi;
    return Group(gens);
end;
ReconstructHData := function(entry, S_M)
    local H, N, res, orbit_data, K, Stab, i, key, hom_triv;
    H := SafeGroup(entry.H_gens, S_M);
    N := SafeGroup(entry.N_H_gens, S_M);
    res := rec(H := H, N := N, orbits := []);
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N, AutQ := fail, A_gens := [], full_aut := true, H_ref := H));
    for orbit_data in entry.orbits do
        K := SafeGroup(orbit_data.K_H_gens, S_M);
        Stab := SafeGroup(orbit_data.Stab_NH_KH_gens, S_M);
        Add(res.orbits, rec(K := K, hom := fail, Q := fail,
            qsize := orbit_data.qsize, qid := orbit_data.qid,
            Stab := Stab, AutQ := fail, A_gens := [], full_aut := fail, H_ref := H));
    od;
    res.byqid := rec();
    for i in [1..Length(res.orbits)] do
        key := String(res.orbits[i].qid);
        if not IsBound(res.byqid.(key)) then res.byqid.(key) := []; fi;
        Add(res.byqid.(key), i);
    od;
    return res;
end;
EnsureHom := function(orb)
    if orb.hom <> fail then return; fi;
    orb.hom := NaturalHomomorphismByNormalSubgroup(orb.H_ref, orb.K);
    orb.Q := Range(orb.hom);
end;
EnsureAutQ := function(orb)
    if orb.AutQ <> fail then return; fi;
    if orb.qsize <= 1 then orb.full_aut := true; return; fi;
    if orb.qsize = 2 then orb.full_aut := true; return; fi;
    EnsureHom(orb);
    orb.AutQ := AutomorphismGroup(orb.Q);
    orb.A_gens := InducedAutoGens(orb.Stab, orb.H_ref, orb.hom);
    orb.full_aut := (Size(Subgroup(orb.AutQ, orb.A_gens)) = Size(orb.AutQ));
end;

# ---- per-target driver ----
RunTarget := function(label, cache_path, ML, right_d, right_t, sample_n)
    local S_ML, S_MR, T_R, N_TR, all_normals, _ComputeOrbitRecsFromKs,
          H_CACHE_ENTRY_PROD, H2DATA, H_CACHE, n_pairs, indices, i, idx, e,
          h1data, key, h1orb, h2idx, h2orb, t_load,
          n_triv, n_q2, n_h2sat, n_h1sat, n_bfs, bfs_hist, bfs_key,
          h1_orbit_summary, h2_orbit_summary;
    Print("\n=== ", label, " ===\n");
    Print("cache: ", cache_path, "\n");
    Print("RIGHT: TG(", right_d, ",", right_t, ")\n");

    S_ML := SymmetricGroup(ML);
    S_MR := SymmetricGroup(right_d);
    T_R := TransitiveGroup(right_d, right_t);
    N_TR := Normalizer(S_MR, T_R);
    Print("  T_R = ", T_R, " size ", Size(T_R), "  N_TR/T_R index ",
          Index(N_TR, T_R), "\n");

    _ComputeOrbitRecsFromKs := function(H, N_H, normals_to_orbit)
        local K_orbit, K_H, hom_H, Q_H, Stab_NH_KH, orbits;
        orbits := [];
        for K_orbit in Orbits(N_H, normals_to_orbit, ConjAction) do
            K_H := K_orbit[1];
            hom_H := NaturalHomomorphismByNormalSubgroup(H, K_H);
            Q_H := Range(hom_H);
            Stab_NH_KH := Stabilizer(N_H, K_H, ConjAction);
            Add(orbits, rec(
                K_H_gens := GeneratorsOfGroup(K_H),
                Stab_NH_KH_gens := GeneratorsOfGroup(Stab_NH_KH),
                qsize := Size(Q_H),
                qid := SafeId(Q_H)));
        od;
        return orbits;
    end;
    all_normals := Filtered(NormalSubgroups(T_R), K -> K <> T_R);
    H_CACHE_ENTRY_PROD := rec(
        H_gens := GeneratorsOfGroup(T_R),
        N_H_gens := GeneratorsOfGroup(N_TR),
        orbits := _ComputeOrbitRecsFromKs(T_R, N_TR, all_normals));
    H2DATA := ReconstructHData(H_CACHE_ENTRY_PROD, S_MR);
    for h2orb in H2DATA.orbits do EnsureAutQ(h2orb); od;
    Print("  RIGHT orbits: ", Length(H2DATA.orbits), "  saturation:");
    for h2orb in H2DATA.orbits do
        if h2orb.qsize <= 1 then Print(" [triv]");
        elif h2orb.qsize = 2 then Print(" [qs=2 |Aut|=1 full=true]");
        else Print(" [qs=", h2orb.qsize, " |Aut|=", Size(h2orb.AutQ),
                   " full=", h2orb.full_aut, "]"); fi;
    od;
    Print("\n");

    # Load LEFT cache
    t_load := Runtime();
    Read(cache_path);
    Print("  LEFT cache: ", Length(H_CACHE), " entries (loaded in ",
          Runtime() - t_load, "ms)\n");

    n_pairs := Length(H_CACHE);
    if sample_n >= n_pairs then
        indices := [1..n_pairs];
    else
        # uniform spread
        indices := List([1..sample_n],
            k -> 1 + Int((k-1) * (n_pairs - 1) / (sample_n - 1)));
    fi;

    n_triv := 0; n_q2 := 0; n_h2sat := 0; n_h1sat := 0; n_bfs := 0;
    bfs_hist := rec();   # key -> count

    for idx in indices do
        e := H_CACHE[idx];
        h1data := ReconstructHData(e, S_ML);
        for h1orb in h1data.orbits do
            key := String(h1orb.qid);
            if not IsBound(H2DATA.byqid.(key)) then continue; fi;
            for h2idx in H2DATA.byqid.(key) do
                h2orb := H2DATA.orbits[h2idx];
                if h2orb.qsize <> h1orb.qsize then continue; fi;
                if h1orb.qsize = 1 then n_triv := n_triv + 1; continue; fi;
                if h1orb.qsize = 2 then n_q2 := n_q2 + 1; continue; fi;
                # general path
                if h2orb.full_aut = true then
                    n_h2sat := n_h2sat + 1;
                else
                    EnsureAutQ(h1orb);
                    if h1orb.full_aut = true then
                        n_h1sat := n_h1sat + 1;
                    else
                        n_bfs := n_bfs + 1;
                        bfs_key := Concatenation("qs=", String(h1orb.qsize),
                                    " h1aut=", String(Size(h1orb.AutQ)),
                                    " h2aut=", String(Size(h2orb.AutQ)),
                                    " h1A=", String(Size(Subgroup(h1orb.AutQ, h1orb.A_gens))),
                                    " h2A=", String(Size(Subgroup(h2orb.AutQ, h2orb.A_gens))));
                        if IsBound(bfs_hist.(bfs_key)) then
                            bfs_hist.(bfs_key) := bfs_hist.(bfs_key) + 1;
                        else
                            bfs_hist.(bfs_key) := 1;
                        fi;
                    fi;
                fi;
            od;
        od;
    od;

    Print("  sampled ", Length(indices), " H1 entries\n");
    Print("  triv (qsize=1) matches: ", n_triv, "\n");
    Print("  q2   (qsize=2) matches: ", n_q2, "\n");
    Print("  h2-saturating matches:  ", n_h2sat, "\n");
    Print("  h1-saturating matches:  ", n_h1sat, "\n");
    Print("  BFS-bound matches:      ", n_bfs, "\n");
    if n_bfs > 0 then
        Print("  BFS-bound histogram (qsize, |AutQ|, |⟨A_gens⟩|):\n");
        for bfs_key in RecNames(bfs_hist) do
            Print("    ", bfs_key, "  ->  ", bfs_hist.(bfs_key), "\n");
        od;
    fi;
end;

# ---- run all targets ----
__TARGETS_CALL__

Print("\n=== done ===\n");
LogTo();
QUIT;
"""

def main():
    sandbox = ROOT / "scan_full_aut_population_tmp"
    sandbox.mkdir(exist_ok=True)
    log = sandbox / "scan.log"
    if log.exists(): log.unlink()
    targets_calls = "\n".join(
        f'RunTarget("{label}", "{(ROOT/path).as_posix()}", {ml}, {rd}, {rt}, {sn});'
        for (label, path, ml, rd, rt, sn) in TARGETS
    )
    g = (GAP_DRIVER
         .replace("__LOG__", str(log).replace("\\", "/"))
         .replace("__TARGETS_CALL__", targets_calls))
    g_path = sandbox / "scan.g"
    g_path.write_text(g, encoding="utf-8")
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    g_cyg = "/cygdrive/c/" + str(g_path)[3:].replace("\\", "/")
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    cmd = (f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
           f'./gap.exe -q -o 0 -L "{LIFTING_WS_CYG}" "{g_cyg}"')
    print(f"running scan over {len(TARGETS)} targets...")
    t0 = time.time()
    proc = subprocess.run([bash_exe, "--login", "-c", cmd], env=env,
                          capture_output=True, text=True, timeout=4*3600)
    print(f"done in {time.time()-t0:.0f}s")
    if log.exists():
        print("--- log ---")
        print(log.read_text())
    if proc.stderr:
        print("--- stderr (last 2k) ---")
        print(proc.stderr[-2000:])

if __name__ == "__main__":
    main()
