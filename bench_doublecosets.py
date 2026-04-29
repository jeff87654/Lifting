"""bench_doublecosets.py — micro-benchmark BFS vs DoubleCosets for Aut(Q)-orbit
counting on representative (h1, h2, isoTH) tuples from a real cache.

Tests the optimization of replacing the BFS over |Aut(Q)| isomorphisms with
a direct DoubleCosets computation.

Loads a real LEFT cache (e.g., [2,1]_[3,2]_[4,3]_[4,3] = n=14, 635 H1's),
pairs it against RIGHT=[4,2]=V_4, samples N H1's, and times both methods on
each (h1_orbit × h2_orbit) match.
"""
import os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).parent
LIFTING_WS_CYG = "/cygdrive/c/Users/jeffr/Downloads/Lifting/lifting.ws"
CACHE_PATH = ROOT / "predict_species_tmp/_h_cache_topt/14/[4,4,3,2]/[2,1]_[3,2]_[4,3]_[4,3].g"

GAP_DRIVER = r"""
LogTo("__LOG__");
if not IsBound(_GoursatBuildFiberProduct) then
    Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
fi;

ML := 14; MR := 4;
N_PAIRS := __NPAIRS__;

Print("=== bench_doublecosets ===\n");

# Helpers
ConjAction := function(K, g) return K^g; end;
SafeId := function(G)
    local n; n := Size(G);
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
SafeSub := function(parent, gens)
    if Length(gens) = 0 then return TrivialSubgroup(parent); fi;
    return Subgroup(parent, gens);
end;

ReconstructHData := function(entry, S_M)
    local H, N, res, orbit_data, K, Stab, i, key, hom_triv;
    H := SafeGroup(entry.H_gens, S_M);
    N := SafeGroup(entry.N_H_gens, S_M);
    res := rec(H := H, N := N, orbits := []);
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N, AutQ := fail, A_gens := [], full_aut := fail, H_ref := H));
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
    if orb.qsize <= 1 then return; fi;
    EnsureHom(orb);
    orb.AutQ := AutomorphismGroup(orb.Q);
    orb.A_gens := InducedAutoGens(orb.Stab, orb.H_ref, orb.hom);
end;

# === Method A: BFS (current production approach) ===
CountOrbitsBFS := function(h1, h2, isoTH)
    local isos, n, gensQ, KeyOf, idx, i, seen, orbit_id, n_orb, queue, j, phi,
          alpha, beta, neighbor, nkey, k, t0, t_setup, t_bfs;
    t0 := Runtime();
    isos := List(AsList(h2.AutQ), a -> a * isoTH);
    n := Length(isos);
    gensQ := GeneratorsOfGroup(h2.Q);
    KeyOf := function(p) return List(gensQ, q -> Image(p, q)); end;
    idx := rec();
    for i in [1..n] do idx.(String(KeyOf(isos[i]))) := i; od;
    t_setup := Runtime() - t0;
    t0 := Runtime();
    seen := ListWithIdenticalEntries(n, false);
    orbit_id := ListWithIdenticalEntries(n, 0);
    n_orb := 0;
    for i in [1..n] do
        if seen[i] then continue; fi;
        n_orb := n_orb + 1;
        seen[i] := true; orbit_id[i] := n_orb;
        queue := [i];
        while Length(queue) > 0 do
            j := Remove(queue);
            phi := isos[j];
            for alpha in h1.A_gens do
                neighbor := phi * alpha;
                nkey := String(KeyOf(neighbor));
                if IsBound(idx.(nkey)) then
                    k := idx.(nkey);
                    if not seen[k] then
                        seen[k] := true; orbit_id[k] := n_orb; Add(queue, k);
                    fi;
                fi;
            od;
            for beta in h2.A_gens do
                neighbor := InverseGeneralMapping(beta) * phi;
                nkey := String(KeyOf(neighbor));
                if IsBound(idx.(nkey)) then
                    k := idx.(nkey);
                    if not seen[k] then
                        seen[k] := true; orbit_id[k] := n_orb; Add(queue, k);
                    fi;
                fi;
            od;
        od;
    od;
    t_bfs := Runtime() - t0;
    return rec(n_orb := n_orb, t_setup := t_setup, t_bfs := t_bfs);
end;

# === Method B: DoubleCosets (proposed) ===
CountOrbitsDC := function(h1, h2, isoTH)
    local A1, A2_conj_gens, A2_in_h1, dcosets, t0, t_total;
    t0 := Runtime();
    A1 := SafeSub(h1.AutQ, h1.A_gens);
    # A2' = isoTH * A2 * isoTH^-1 (conjugate of A2 in Aut(h1.Q))
    # In automorphism algebra: alpha * beta means beta then alpha (left action),
    # so A2 acts on isos by phi -> phi * beta^-1, translating to alpha -> alpha * (isoTH * beta^-1 * isoTH^-1).
    # We want the GROUP A2' = isoTH * A2 * isoTH^-1, computed as conjugates of A2 generators.
    A2_conj_gens := List(h2.A_gens,
        b -> InverseGeneralMapping(isoTH) * b * isoTH);
    A2_in_h1 := SafeSub(h1.AutQ, A2_conj_gens);
    dcosets := DoubleCosets(h1.AutQ, A1, A2_in_h1);
    t_total := Runtime() - t0;
    return rec(n_orb := Length(dcosets), t_total := t_total);
end;

# Load cache + sample H1's
Print("loading cache: __CACHE__\n");
S_ML := SymmetricGroup(ML); S_MR := SymmetricGroup(MR);
Read("__CACHE__");
Print("H_CACHE: ", Length(H_CACHE), " entries\n");

# Build RIGHT (V_4 = TG(4,2))
T_R := TransitiveGroup(MR, 2);
N_TR := Normalizer(S_MR, T_R);
RIGHT_NORMALS := Filtered(NormalSubgroups(T_R), K -> K <> T_R);
RIGHT_CACHE := rec(
    H_gens := GeneratorsOfGroup(T_R),
    N_H_gens := GeneratorsOfGroup(N_TR),
    orbits := List(RIGHT_NORMALS, K -> rec(
        K_H_gens := GeneratorsOfGroup(K),
        Stab_NH_KH_gens := GeneratorsOfGroup(Stabilizer(N_TR, K, ConjAction)),
        qsize := Index(T_R, K), qid := SafeId(T_R / K))));
H2DATA := ReconstructHData(RIGHT_CACHE, S_MR);

Print("\nSampling ", N_PAIRS, " H1 entries; for each, find one (h1.orbit, h2.orbit) match with non-trivial Aut(Q) and benchmark.\n\n");
pad := function(x, w) local s; s := String(x); while Length(s) < w do s := Concatenation(" ", s); od; return s; end;
Print(pad("h1_idx",7), pad("|H1|",6), pad("|Aut(Q)|",10), pad("|A1|",6), pad("|A2|",6),
      pad("BFS_setup",11), pad("BFS_bfs",10), pad("BFS_total",11), pad("DC_total",10),
      pad("speedup",9), pad("n_orb",7), pad("match",6), "\n");

t_bfs_total := 0; t_dc_total := 0; n_pairs_tested := 0;
for h1_idx in [1..N_PAIRS] do
    h1data := ReconstructHData(H_CACHE[h1_idx], S_ML);
    # Find first non-trivial (qsize >= 2) h1.orbit that matches an H2 orbit
    for h1_orb_idx in [2..Length(h1data.orbits)] do
        h1orb := h1data.orbits[h1_orb_idx];
        if h1orb.qsize <= 2 then continue; fi;  # skip trivial-Q and qsize=2 (handled by direct path)
        key := String(h1orb.qid);
        if not IsBound(H2DATA.byqid.(key)) then continue; fi;
        for h2idx in H2DATA.byqid.(key) do
            h2orb := H2DATA.orbits[h2idx];
            if h2orb.qsize <> h1orb.qsize then continue; fi;
            EnsureHom(h1orb); EnsureHom(h2orb);
            isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
            if isoTH = fail then continue; fi;
            EnsureAutQ(h1orb); EnsureAutQ(h2orb);
            # Bench both
            r_bfs := CountOrbitsBFS(h1orb, h2orb, isoTH);
            r_dc  := CountOrbitsDC(h1orb, h2orb, isoTH);
            speedup := Float(r_bfs.t_setup + r_bfs.t_bfs) / Float(Maximum(r_dc.t_total, 1));
            ok := When(r_bfs.n_orb = r_dc.n_orb, "OK", "DIFF!");
            speedup_str := String(speedup);
            Print(pad(h1_idx,7), pad(Size(h1data.H),6), pad(Size(h1orb.AutQ),10),
                  pad(Length(h1orb.A_gens),6), pad(Length(h2orb.A_gens),6),
                  pad(r_bfs.t_setup,11), pad(r_bfs.t_bfs,10),
                  pad(r_bfs.t_setup + r_bfs.t_bfs,11), pad(r_dc.t_total,10),
                  pad(speedup_str{[1..Minimum(7,Length(speedup_str))]},9),
                  pad(r_bfs.n_orb,7), pad(ok,6), "\n");
            t_bfs_total := t_bfs_total + r_bfs.t_setup + r_bfs.t_bfs;
            t_dc_total := t_dc_total + r_dc.t_total;
            n_pairs_tested := n_pairs_tested + 1;
            break;
        od;
        if n_pairs_tested >= h1_idx then break; fi;
    od;
od;

Print("\n=== summary ===\n");
Print("pairs tested: ", n_pairs_tested, "\n");
Print("BFS total: ", t_bfs_total, "ms\n");
Print("DC  total: ", t_dc_total, "ms\n");
if t_dc_total > 0 then
    Print("speedup: ", Float(t_bfs_total) / Float(t_dc_total), "x\n");
fi;

LogTo();
QUIT;
"""

def main():
    if not CACHE_PATH.exists():
        # Try to find a similar cache
        candidates = list(Path("predict_species_tmp/_h_cache_topt/14").rglob("*.g"))
        if not candidates:
            print(f"ERROR: cache not found at {CACHE_PATH} and no n=14 caches available")
            return
        cache = candidates[0]
        print(f"using cache: {cache}")
    else:
        cache = CACHE_PATH
    sandbox = ROOT / "bench_dc_tmp"
    sandbox.mkdir(exist_ok=True)
    log = sandbox / "bench.log"
    if log.exists(): log.unlink()
    g = (GAP_DRIVER
         .replace("__LOG__", str(log).replace("\\", "/"))
         .replace("__CACHE__", str(cache).replace("\\", "/"))
         .replace("__NPAIRS__", "12"))
    g_path = sandbox / "bench.g"
    g_path.write_text(g, encoding="utf-8")
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    g_cyg = "/cygdrive/c/" + str(g_path)[3:].replace("\\", "/")
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    cmd = (f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
           f'./gap.exe -q -o 0 -L "{LIFTING_WS_CYG}" "{g_cyg}"')
    print("running...")
    t0 = time.time()
    proc = subprocess.run([bash_exe, "--login", "-c", cmd], env=env,
                          capture_output=True, text=True, timeout=3600)
    print(f"done in {time.time()-t0:.0f}s")
    if log.exists(): print("\n--- log ---"); print(log.read_text())
    if proc.stderr: print("\n--- stderr ---"); print(proc.stderr[-1500:])

if __name__ == "__main__":
    main()
