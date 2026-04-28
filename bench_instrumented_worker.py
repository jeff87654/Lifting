"""bench_instrumented_worker.py — faithful clone of production ProcessPair
with per-phase timing instrumentation.

Loads the live LEFT cache for [2,1]_[4,3]_[4,3]_[4,3] (n=14, partition [4,4,4,2]).
Builds the RIGHT cache for [4,1] = C_4 fresh.
Runs the H1xH2 loop using EXACTLY the production code paths from
predict_2factor_topt.py (ReconstructHData, EnsureHom, EnsureAutQ, BFS,
_GoursatBuildFiberProduct, EmitGenerators).

Adds a per-phase ms breakdown printed after every pair:
  reconstruct_ms   ReconstructHData for this H1
  match_iter_ms    iterating h1.orbits and looking up matching h2idxs
  iso_ms           IsomorphismGroups calls
  ensureautq_ms    EnsureAutQ (AutomorphismGroup + InducedAutoGens)
  isos_build_ms    List(AsList(AutQ), a -> a * isoTH)
  bfs_ms           the BFS loop body
  buildfp_ms       _GoursatBuildFiberProduct calls (per orbit rep)
  emit_ms          EmitGenerators
  pair_total_ms    sum of per-pair work

Output goes to bench_instrumented_tmp/bench.log.
"""
import argparse, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).parent
LIFTING_WS_CYG = "/cygdrive/c/Users/jeffr/Downloads/Lifting/lifting.ws"
CACHE_PATH = ROOT / "predict_species_tmp/_h_cache_topt/14/[4,4,4,2]/[2,1]_[4,3]_[4,3]_[4,3].g"
EMIT_PATH = ROOT / "bench_instrumented_tmp/emit.g"

GAP_DRIVER = r"""
LogTo("__LOG__");
if not IsBound(_GoursatBuildFiberProduct) then
    Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
fi;

ML := 14;
MR := 4;
N_PAIRS := __NPAIRS__;
EMIT_GENS_PATH := "__EMIT__";

Print("=== bench_instrumented_worker ===\n");
Print("ML=", ML, " MR=", MR, " N_PAIRS=", N_PAIRS, "\n\n");

# ---- helpers (verbatim from predict_2factor_topt.py) ------------------------
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
        Stab := N, AutQ := fail, A_gens := [], H_ref := H));
    for orbit_data in entry.orbits do
        K := SafeGroup(orbit_data.K_H_gens, S_M);
        Stab := SafeGroup(orbit_data.Stab_NH_KH_gens, S_M);
        Add(res.orbits, rec(K := K, hom := fail, Q := fail,
            qsize := orbit_data.qsize, qid := orbit_data.qid,
            Stab := Stab, AutQ := fail, A_gens := [], H_ref := H));
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

# ---- emit setup --------------------------------------------------------------
PrintTo(EMIT_GENS_PATH, "");
EmitGenerators := function(F)
    local gens, s;
    gens := GeneratorsOfGroup(F);
    if Length(gens) > 0 then
        s := JoinStringsWithSeparator(List(gens, String), ",");
    else
        s := "";
    fi;
    AppendTo(EMIT_GENS_PATH, "[", s, "]\n");
end;

# ---- load cache + build right side ------------------------------------------
S_ML := SymmetricGroup(ML);
S_MR := SymmetricGroup(MR);

t0 := Runtime();
Read("__CACHE__");
Print("loaded LEFT cache in ", Runtime()-t0, "ms (", Length(H_CACHE), " entries)\n");

T_R := TransitiveGroup(MR, 1);   # C_4
N_TR := Normalizer(S_MR, T_R);

# Build RIGHT cache entry the way the live code does (one entry per N_TR-orbit
# of normal subgroups of T_R), then ReconstructHData on it.
RIGHT_NORMALS := Filtered(NormalSubgroups(T_R), K -> K <> T_R);
RIGHT_CACHE_ENTRY := rec(
    H_gens := GeneratorsOfGroup(T_R),
    N_H_gens := GeneratorsOfGroup(N_TR),
    orbits := List(RIGHT_NORMALS, K -> rec(
        K_H_gens := GeneratorsOfGroup(K),
        Stab_NH_KH_gens := GeneratorsOfGroup(Stabilizer(N_TR, K, ConjAction)),
        qsize := Index(T_R, K),
        qid := SafeId(T_R / K)
    ))
);
H2DATA := ReconstructHData(RIGHT_CACHE_ENTRY, S_MR);
Print("RIGHT cache: ", Length(H2DATA.orbits), " orbits (incl. trivial)\n\n");

shift_R := MappingPermListList([1..MR], [ML+1..ML+MR]);

# ---- per-pair benchmark with phase timing -----------------------------------
Print("per-pair phase breakdown (ms):\n");
pad := function(x, w) local s; s := String(x); while Length(s) < w do s := Concatenation(" ", s); od; return s; end;
hdr := function() Print(pad("i",4), pad("|H1|",6), pad("nmatch",7), pad("fps",6),
                       pad("recon",7), pad("iso",6), pad("autq",6), pad("isos",6),
                       pad("bfs",6), pad("buildfp",8), pad("emit",6), pad("pair_total",11), "\n"); end;
hdr();

for i in [1..N_PAIRS] do
    # --- reconstruct H1 from cache entry ---
    t_pair := Runtime();
    t0 := Runtime();
    H1data := ReconstructHData(H_CACHE[i], S_ML);
    t_recon := Runtime() - t0;
    H1 := H1data.H;

    # state for this pair
    n_match := 0; total_orb := 0;
    t_iso := 0; t_autq := 0; t_isos_build := 0; t_bfs := 0;
    t_buildfp := 0; t_emit := 0;

    # --- mimic ProcessPair general path (qsize >= 3 logic, also handles qsize=2 SAFE PATH for MR>2) ---
    for h1_orb_idx in [2..Length(H1data.orbits)] do   # skip trivial-Q at idx 1 for clarity
        h1orb := H1data.orbits[h1_orb_idx];
        key := String(h1orb.qid);
        if not IsBound(H2DATA.byqid.(key)) then continue; fi;
        for h2idx in H2DATA.byqid.(key) do
            h2orb := H2DATA.orbits[h2idx];
            if h2orb.qsize <> h1orb.qsize then continue; fi;
            if h1orb.qsize = 1 then continue; fi;   # trivial handled separately in real code; skip here

            n_match := n_match + 1;

            # IsomorphismGroups
            t0 := Runtime(); EnsureHom(h1orb); EnsureHom(h2orb);
            isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
            t_iso := t_iso + (Runtime() - t0);
            if isoTH = fail then continue; fi;

            # EnsureAutQ for both
            t0 := Runtime(); EnsureAutQ(h1orb); EnsureAutQ(h2orb);
            t_autq := t_autq + (Runtime() - t0);

            # build isos list
            t0 := Runtime();
            isos := List(AsList(h2orb.AutQ), a -> a * isoTH);
            n := Length(isos);
            gensQ := GeneratorsOfGroup(h2orb.Q);
            KeyOf := function(phi) return List(gensQ, q -> Image(phi, q)); end;
            idx := rec();
            for j in [1..n] do idx.(String(KeyOf(isos[j]))) := j; od;
            t_isos_build := t_isos_build + (Runtime() - t0);

            # BFS / aut-saturation shortcut
            t0 := Runtime();
            if Length(h1orb.A_gens) > 0 and
               Size(Subgroup(h1orb.AutQ, h1orb.A_gens)) = Size(h1orb.AutQ) then
                n_orb := 1; orbit_reps_phi := [isos[1]];
            elif Length(h2orb.A_gens) > 0 and
                 Size(Subgroup(h2orb.AutQ, h2orb.A_gens)) = Size(h2orb.AutQ) then
                n_orb := 1; orbit_reps_phi := [isos[1]];
            else
                seen := ListWithIdenticalEntries(n, false);
                n_orb := 0; orbit_reps_phi := [];
                for j in [1..n] do
                    if seen[j] then continue; fi;
                    n_orb := n_orb + 1; Add(orbit_reps_phi, isos[j]);
                    seen[j] := true; queue := [j];
                    while Length(queue) > 0 do
                        jj := Remove(queue); phi := isos[jj];
                        for alpha in h1orb.A_gens do
                            neighbor := phi * alpha;
                            nkey := String(KeyOf(neighbor));
                            if IsBound(idx.(nkey)) then
                                k := idx.(nkey);
                                if not seen[k] then seen[k] := true; Add(queue, k); fi;
                            fi;
                        od;
                        for beta in h2orb.A_gens do
                            neighbor := InverseGeneralMapping(beta) * phi;
                            nkey := String(KeyOf(neighbor));
                            if IsBound(idx.(nkey)) then
                                k := idx.(nkey);
                                if not seen[k] then seen[k] := true; Add(queue, k); fi;
                            fi;
                        od;
                    od;
                od;
            fi;
            t_bfs := t_bfs + (Runtime() - t0);

            total_orb := total_orb + n_orb;

            # build fp + emit per orbit rep
            H2_shifted := h2orb.H_ref^shift_R;
            for j in [1..n_orb] do
                t0 := Runtime();
                fp := _GoursatBuildFiberProduct(
                    H1, H2_shifted,
                    h1orb.hom,
                    CompositionMapping(h2orb.hom,
                        ConjugatorIsomorphism(H2_shifted, shift_R^-1)),
                    InverseGeneralMapping(orbit_reps_phi[j]),
                    [1..ML], [ML+1..ML+MR]);
                t_buildfp := t_buildfp + (Runtime() - t0);
                if fp <> fail then
                    t0 := Runtime(); EmitGenerators(fp); t_emit := t_emit + (Runtime() - t0);
                fi;
            od;
        od;
    od;

    pair_total := Runtime() - t_pair;
    Print(pad(i,4), pad(Size(H1),6), pad(n_match,7), pad(total_orb,6),
          pad(t_recon,7), pad(t_iso,6), pad(t_autq,6), pad(t_isos_build,6),
          pad(t_bfs,6), pad(t_buildfp,8), pad(t_emit,6), pad(pair_total,11), "\n");
od;

Print("\n=== done ===\n");
LogTo();
QUIT;
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npairs", type=int, default=3)
    args = ap.parse_args()
    sandbox = ROOT / "bench_instrumented_tmp"
    sandbox.mkdir(exist_ok=True)
    log = sandbox / "bench.log"
    if log.exists(): log.unlink()
    emit = EMIT_PATH
    if emit.exists(): emit.unlink()
    g = (GAP_DRIVER
         .replace("__LOG__", str(log).replace("\\", "/"))
         .replace("__EMIT__", str(emit).replace("\\", "/"))
         .replace("__CACHE__", str(CACHE_PATH).replace("\\", "/"))
         .replace("__NPAIRS__", str(args.npairs)))
    g_path = sandbox / "bench.g"
    g_path.write_text(g, encoding="utf-8")
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    g_cyg = "/cygdrive/c/" + str(g_path)[3:].replace("\\", "/")
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    cmd = (f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
           f'./gap.exe -q -o 0 -L "{LIFTING_WS_CYG}" "{g_cyg}"')
    print(f"running instrumented bench (npairs={args.npairs})...")
    t0 = time.time()
    proc = subprocess.run([bash_exe, "--login", "-c", cmd], env=env,
                          capture_output=True, text=True, timeout=4*3600)
    print(f"done in {time.time()-t0:.0f}s")
    if log.exists(): print("--- log ---"); print(log.read_text())
    if proc.stderr: print("--- stderr ---"); print(proc.stderr[-1500:])

if __name__ == "__main__":
    main()
