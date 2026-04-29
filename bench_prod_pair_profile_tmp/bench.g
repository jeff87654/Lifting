
LogTo("C:/Users/jeffr/Downloads/Lifting/bench_prod_pair_profile_tmp/bench.log");
if not IsBound(_GoursatBuildFiberProduct) then
    Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
fi;

ML := 15;
MR := 4;
START_IDX := 915;
N_PAIRS := 5;
EMIT_GENS_PATH := "C:/Users/jeffr/Downloads/Lifting/bench_prod_pair_profile_tmp/emit.g";

Print("=== bench_prod_pair_profile ===\n");
Print("ML=", ML, " MR=", MR, " START_IDX=", START_IDX, " N_PAIRS=", N_PAIRS, "\n\n");

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
    orb.full_aut := (Size(Subgroup(orb.AutQ, orb.A_gens)) = Size(orb.AutQ));
end;

# ---- emit setup --------------------------------------------------------------
PrintTo(EMIT_GENS_PATH, "");
fp_lines := [];
EmitGenerators := function(F)
    local gens, s;
    gens := GeneratorsOfGroup(F);
    if Length(gens) > 0 then
        s := JoinStringsWithSeparator(List(gens, String), ",");
    else
        s := "";
    fi;
    Add(fp_lines, Concatenation("[", s, "]"));
end;

# ---- load LEFT cache + build right side -------------------------------------
S_ML := SymmetricGroup(ML);
S_MR := SymmetricGroup(MR);

t0 := Runtime();
Read("C:/Users/jeffr/Downloads/Lifting/predict_species_tmp/_h_cache_topt/15/[4,4,3,2,2]/[2,1]_[2,1]_[3,2]_[4,3]_[4,3].g");
Print("loaded LEFT cache in ", Runtime()-t0, "ms (", Length(H_CACHE), " entries)\n");

T_R := TransitiveGroup(MR, 2);
Print("RIGHT = TransitiveGroup(", MR, ",", 2, ") = ", T_R, " size ", Size(T_R), "\n");
N_TR := Normalizer(S_MR, T_R);

# Production-style RIGHT cache (filter normals to qids in LEFT)
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

Print("RIGHT cache: ", Length(H2DATA.orbits), " orbits\n");
Print("  qids/qsizes: ");
for orec in H2DATA.orbits do Print("[", orec.qid, ":", orec.qsize, "] "); od;
Print("\n\n");

shift_R := MappingPermListList([1..MR], [ML+1..ML+MR]);

# Pre-fill EnsureAutQ for all H2DATA orbits so we can see h2.full_aut state
for orec in H2DATA.orbits do EnsureAutQ(orec); od;
Print("RIGHT full_aut flags: ");
for orec in H2DATA.orbits do
    if orec.qsize <= 1 then Print("[triv] ");
    elif orec.full_aut then Print("[Y/", Size(orec.AutQ),"] ");
    else Print("[N/", Size(orec.AutQ),"] "); fi;
od;
Print("\n\n");

# ---- per-pair benchmark with phase timing -----------------------------------
Print("per-pair phase breakdown (ms):\n");
pad := function(x, w) local s; s := String(x); while Length(s) < w do s := Concatenation(" ", s); od; return s; end;
hdr := function() Print(pad("i",5), pad("|H1|",7), pad("nm",4), pad("nshort",7), pad("nbfs",5),
                       pad("fps",6), pad("recon",7), pad("iso",6), pad("autq",6),
                       pad("isos",6), pad("bfs",6), pad("buildfp",8),
                       pad("emit",6), pad("pair_total",11), "\n"); end;
hdr();

for i in [START_IDX..(START_IDX + N_PAIRS - 1)] do
    if i > Length(H_CACHE) then break; fi;
    t_pair := Runtime();
    t0 := Runtime();
    H1data := ReconstructHData(H_CACHE[i], S_ML);
    t_recon := Runtime() - t0;
    H1 := H1data.H;

    n_match := 0; total_orb := 0; n_short := 0; n_bfs_real := 0;
    t_iso := 0; t_autq := 0; t_isos_build := 0; t_bfs := 0;
    t_buildfp := 0; t_emit := 0;
    fp_lines := [];

    for h1_orb_idx in [1..Length(H1data.orbits)] do
        h1orb := H1data.orbits[h1_orb_idx];
        key := String(h1orb.qid);
        if not IsBound(H2DATA.byqid.(key)) then continue; fi;

        if h1orb.qsize = 1 then
            for h2idx in H2DATA.byqid.(key) do
                h2orb := H2DATA.orbits[h2idx];
                if h2orb.qsize <> 1 then continue; fi;
                n_match := n_match + 1;
                t0 := Runtime();
                fp := Group(Concatenation(GeneratorsOfGroup(H1),
                                          GeneratorsOfGroup(h2orb.H_ref^shift_R)));
                t_buildfp := t_buildfp + (Runtime() - t0);
                t0 := Runtime(); EmitGenerators(fp); t_emit := t_emit + (Runtime() - t0);
                total_orb := total_orb + 1;
            od;
            continue;
        fi;

        if h1orb.qsize = 2 and MR > 2 then
            for h2idx in H2DATA.byqid.(key) do
                h2orb := H2DATA.orbits[h2idx];
                if h2orb.qsize <> 2 then continue; fi;
                n_match := n_match + 1;
                t0 := Runtime(); EnsureHom(h1orb); EnsureHom(h2orb);
                isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
                t_iso := t_iso + (Runtime() - t0);
                if isoTH = fail then continue; fi;
                t0 := Runtime();
                H2_shifted := h2orb.H_ref^shift_R;
                fp := _GoursatBuildFiberProduct(
                    H1, H2_shifted, h1orb.hom,
                    CompositionMapping(h2orb.hom,
                        ConjugatorIsomorphism(H2_shifted, shift_R^-1)),
                    InverseGeneralMapping(isoTH),
                    [1..ML], [ML+1..ML+MR]);
                t_buildfp := t_buildfp + (Runtime() - t0);
                if fp <> fail then
                    t0 := Runtime(); EmitGenerators(fp); t_emit := t_emit + (Runtime() - t0);
                fi;
                total_orb := total_orb + 1;
            od;
            continue;
        fi;

        # General path for qsize >= 3
        for h2idx in H2DATA.byqid.(key) do
            h2orb := H2DATA.orbits[h2idx];
            if h2orb.qsize <> h1orb.qsize then continue; fi;
            if h1orb.qsize = 1 then continue; fi;

            n_match := n_match + 1;

            t0 := Runtime(); EnsureHom(h1orb); EnsureHom(h2orb);
            isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
            t_iso := t_iso + (Runtime() - t0);
            if isoTH = fail then continue; fi;

            t0 := Runtime(); EnsureAutQ(h1orb); EnsureAutQ(h2orb);
            t_autq := t_autq + (Runtime() - t0);

            # saturation shortcut FIRST (before building isos table)
            t0 := Runtime();
            if (h1orb.full_aut = true) or (h2orb.full_aut = true) then
                n_orb := 1; orbit_reps_phi := [isoTH];
                n_short := n_short + 1;
                t_bfs := t_bfs + (Runtime() - t0);
            else
                n_bfs_real := n_bfs_real + 1;
                t_bfs := t_bfs + (Runtime() - t0);

                t0 := Runtime();
                isos := List(AsList(h2orb.AutQ), a -> a * isoTH);
                n := Length(isos);
                gensQ := GeneratorsOfGroup(h2orb.Q);
                KeyOf := function(phi) return List(gensQ, q -> Image(phi, q)); end;
                idx := rec();
                for j in [1..n] do idx.(String(KeyOf(isos[j]))) := j; od;
                t_isos_build := t_isos_build + (Runtime() - t0);

                t0 := Runtime();
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
                t_bfs := t_bfs + (Runtime() - t0);
            fi;

            total_orb := total_orb + n_orb;

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
    Print(pad(i,5), pad(Size(H1),7), pad(n_match,4), pad(n_short,7), pad(n_bfs_real,5),
          pad(total_orb,6), pad(t_recon,7), pad(t_iso,6), pad(t_autq,6),
          pad(t_isos_build,6), pad(t_bfs,6), pad(t_buildfp,8),
          pad(t_emit,6), pad(pair_total,11), "\n");
od;

Print("\n=== done ===\n");
LogTo();
QUIT;
