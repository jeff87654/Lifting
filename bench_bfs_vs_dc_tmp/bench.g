
LogTo("C:/Users/jeffr/Downloads/Lifting/bench_bfs_vs_dc_tmp/bench.log");
if not IsBound(_GoursatBuildFiberProduct) then
    Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
fi;

ML := 10;
SAMPLE_N := 78;

Print("=== bench_bfs_vs_dc ===\n");
Print("ML=", ML, "  SAMPLE_N=", SAMPLE_N, "\n");

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
SafeSub := function(G, gens)
    if Length(gens) = 0 then return TrivialSubgroup(G); fi;
    return Subgroup(G, gens);
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

# ---- BFS implementation (faithful to production) ----
CountOrbitsBFS := function(h1orb, h2orb, isoTH)
    local isos, n, gensQ, KeyOf, idx, i, seen, n_orb, queue, j, phi,
          alpha, beta, neighbor, nkey, k, t0;
    t0 := NanosecondsSinceEpoch();
    isos := List(AsList(h2orb.AutQ), a -> a * isoTH);
    n := Length(isos);
    gensQ := GeneratorsOfGroup(h2orb.Q);
    KeyOf := function(phi) return List(gensQ, q -> Image(phi, q)); end;
    idx := rec();
    for i in [1..n] do idx.(String(KeyOf(isos[i]))) := i; od;
    seen := ListWithIdenticalEntries(n, false);
    n_orb := 0;
    for i in [1..n] do
        if seen[i] then continue; fi;
        n_orb := n_orb + 1;
        seen[i] := true; queue := [i];
        while Length(queue) > 0 do
            j := Remove(queue); phi := isos[j];
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
    return rec(n_orb := n_orb, t_us := Int((NanosecondsSinceEpoch() - t0)/1000));
end;

# ---- DoubleCosets implementation ----
# Orbits of (A1 × A2) acting on isos {h2.Q -> h1.Q} via (β, γ) · φ = β⁻¹ ∘ φ ∘ γ
# Parametrize isos by α ∈ Aut(h1.Q): φ = α ∘ isoTH.
# Action becomes α ↦ β⁻¹ α γ' where γ' = isoTH ∘ γ ∘ isoTH⁻¹ ∈ Aut(h1.Q).
# Orbit count = |A1 \ Aut(h1.Q) / A2'|.
CountOrbitsDC := function(h1orb, h2orb, isoTH)
    local A1, A2_in_h1_gens, A2_in_h1, dc, t0;
    t0 := NanosecondsSinceEpoch();
    A1 := SafeSub(h1orb.AutQ, h1orb.A_gens);
    A2_in_h1_gens := List(h2orb.A_gens,
        b -> InverseGeneralMapping(isoTH) * b * isoTH);
    A2_in_h1 := SafeSub(h1orb.AutQ, A2_in_h1_gens);
    dc := DoubleCosets(h1orb.AutQ, A1, A2_in_h1);
    return rec(n_orb := Length(dc), t_us := Int((NanosecondsSinceEpoch() - t0)/1000));
end;

# ---- target builder ----
BuildRight := function(MR, right_t)
    local S_MR, T_R, N_TR, _ComputeOrbitRecsFromKs, all_normals,
          H_CACHE_ENTRY_PROD, H2DATA, h2orb;
    S_MR := SymmetricGroup(MR);
    T_R := TransitiveGroup(MR, right_t);
    N_TR := Normalizer(S_MR, T_R);
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
    return H2DATA;
end;

# ---- driver ----
RunTarget := function(label, MR, right_t)
    local S_ML, H2DATA, n_pairs, indices, idx, e, h1data, h1orb, h2idx, h2orb,
          key, isoTH, bfs_res, dc_res, bucket_key, bucket, mismatch, total_bfs_us,
          total_dc_us, n_match, n_mismatch, sums;
    Print("\n=== ", label, "  RIGHT=TG(", MR, ",", right_t, ") ===\n");
    S_ML := SymmetricGroup(ML);
    H2DATA := BuildRight(MR, right_t);
    Print("  RIGHT orbits:");
    for h2orb in H2DATA.orbits do
        if h2orb.qsize <= 1 then Print(" [triv]");
        elif h2orb.qsize = 2 then Print(" [qs=2 sat]");
        else Print(" [qs=", h2orb.qsize, " |Aut|=", Size(h2orb.AutQ),
                   " full=", h2orb.full_aut, "]"); fi;
    od;
    Print("\n");

    # H_CACHE is global from Read
    n_pairs := Length(H_CACHE);
    if SAMPLE_N >= n_pairs then indices := [1..n_pairs];
    else indices := List([1..SAMPLE_N],
        k -> 1 + Int((k-1) * (n_pairs - 1) / (SAMPLE_N - 1))); fi;

    sums := rec();
    n_match := 0; n_mismatch := 0;
    total_bfs_us := 0; total_dc_us := 0;
    for idx in indices do
        e := H_CACHE[idx];
        h1data := ReconstructHData(e, S_ML);
        for h1orb in h1data.orbits do
            key := String(h1orb.qid);
            if not IsBound(H2DATA.byqid.(key)) then continue; fi;
            for h2idx in H2DATA.byqid.(key) do
                h2orb := H2DATA.orbits[h2idx];
                if h2orb.qsize <> h1orb.qsize then continue; fi;
                if h1orb.qsize <= 2 then continue; fi;
                EnsureAutQ(h1orb);
                if h1orb.full_aut = true or h2orb.full_aut = true then continue; fi;
                # We have a BFS-bound match
                EnsureHom(h1orb); EnsureHom(h2orb);
                isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
                if isoTH = fail then continue; fi;

                bfs_res := CountOrbitsBFS(h1orb, h2orb, isoTH);
                dc_res  := CountOrbitsDC (h1orb, h2orb, isoTH);

                n_match := n_match + 1;
                total_bfs_us := total_bfs_us + bfs_res.t_us;
                total_dc_us := total_dc_us + dc_res.t_us;
                if bfs_res.n_orb <> dc_res.n_orb then
                    n_mismatch := n_mismatch + 1;
                fi;
                bucket_key := Concatenation("qs=", String(h1orb.qsize),
                              " |A|=", String(Size(h1orb.AutQ)),
                              " A1=", String(Size(SafeSub(h1orb.AutQ, h1orb.A_gens))),
                              " A2=", String(Size(SafeSub(h2orb.AutQ, h2orb.A_gens))));
                if not IsBound(sums.(bucket_key)) then
                    sums.(bucket_key) := rec(n := 0, bfs_us := 0, dc_us := 0,
                                             n_orb_bfs := 0, n_orb_dc := 0,
                                             mismatches := 0);
                fi;
                bucket := sums.(bucket_key);
                bucket.n := bucket.n + 1;
                bucket.bfs_us := bucket.bfs_us + bfs_res.t_us;
                bucket.dc_us := bucket.dc_us + dc_res.t_us;
                bucket.n_orb_bfs := bucket.n_orb_bfs + bfs_res.n_orb;
                bucket.n_orb_dc := bucket.n_orb_dc + dc_res.n_orb;
                if bfs_res.n_orb <> dc_res.n_orb then
                    bucket.mismatches := bucket.mismatches + 1;
                fi;
            od;
        od;
    od;
    Print("  BFS-bound matches: ", n_match, "  mismatches: ", n_mismatch, "\n");
    Print("  total BFS time: ", total_bfs_us, "us\n");
    Print("  total DC  time: ", total_dc_us, "us\n");
    if total_dc_us > 0 then
        Print("  ratio BFS/DC: ", total_bfs_us * 100 / total_dc_us, "/100\n");
    fi;
    Print("  per-bucket (n, bfs_avg_us, dc_avg_us, ratio, n_orb_bfs, n_orb_dc):\n");
    for bucket_key in RecNames(sums) do
        bucket := sums.(bucket_key);
        Print("    ", bucket_key, "  n=", bucket.n,
              "  bfs_avg=", Int(bucket.bfs_us / bucket.n),
              "us  dc_avg=", Int(bucket.dc_us / bucket.n),
              "us  ratio=", Int(bucket.bfs_us * 100 / Maximum(1, bucket.dc_us)), "/100",
              "  n_orb_bfs=", bucket.n_orb_bfs, "  n_orb_dc=", bucket.n_orb_dc);
        if bucket.mismatches > 0 then
            Print("  MISMATCHES=", bucket.mismatches);
        fi;
        Print("\n");
    od;
end;

# Load LEFT cache once (global H_CACHE)
Print("loading LEFT cache...\n");
Read("C:/Users/jeffr/Downloads/Lifting/predict_species_tmp/_h_cache_topt/10/[4,4,2]/[2,1]_[4,3]_[4,3].g");
Print("  loaded ", Length(H_CACHE), " entries\n");

RunTarget("D_4", 4, 3);
RunTarget("TG(8,22)", 8, 22);
RunTarget("TG(8,35)", 8, 35);

Print("\n=== done ===\n");
LogTo();
QUIT;
