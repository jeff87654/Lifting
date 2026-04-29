
LogTo("/cygdrive/c/Users/jeffr/Downloads/Lifting/predict_species_tmp/_two_factor_topt/_batch/[2,1]_[4,3]_[4,3]_[4,3]_77cd7229e4a0/batch.log");
SizeScreen([100000, 24]);   # disable line wrapping in output

# Path to lifting_algorithm.g for _GoursatBuildFiberProduct.
if not IsBound(_GoursatBuildFiberProduct) then Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g"); fi;

# Common helpers (same as GAP_DRIVER).
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
    # Trivial-quotient orbit (always present; hom is fast for H/H).
    hom_triv := NaturalHomomorphismByNormalSubgroup(H, H);
    Add(res.orbits, rec(K := H, hom := hom_triv, Q := Range(hom_triv),
        qsize := 1, qid := SafeId(Range(hom_triv)),
        Stab := N, AutQ := fail, A_gens := [],
        H_ref := H));
    # Non-trivial orbits: hom and Q are deferred (computed lazily by EnsureHom).
    # NaturalHomomorphismByNormalSubgroup is the dominant cost for large H,
    # and most orbits never get paired against a matching RIGHT qid, so
    # deferring it is the dominant speed win.
    for orbit_data in entry.orbits do
        K := SafeGroup(orbit_data.K_H_gens, S_M);
        Stab := SafeGroup(orbit_data.Stab_NH_KH_gens, S_M);
        Add(res.orbits, rec(K := K, hom := fail, Q := fail,
            qsize := orbit_data.qsize, qid := orbit_data.qid,
            Stab := Stab, AutQ := fail, A_gens := [],
            H_ref := H));
    od;
    res.byqid := rec();
    for i in [1..Length(res.orbits)] do
        key := String(res.orbits[i].qid);
        if not IsBound(res.byqid.(key)) then res.byqid.(key) := []; fi;
        Add(res.byqid.(key), i);
    od;
    return res;
end;

# Lazily compute hom and Q for an orbit record.  Mutates the record.
# Idempotent: safe to call repeatedly.
EnsureHom := function(orb)
    if orb.hom <> fail then return; fi;
    orb.hom := NaturalHomomorphismByNormalSubgroup(orb.H_ref, orb.K);
    orb.Q := Range(orb.hom);
end;

# Lazily compute AutQ + A_gens for an orbit record.  Mutates the record.
EnsureAutQ := function(orb)
    if orb.AutQ <> fail then return; fi;
    if orb.qsize <= 1 then return; fi;   # trivial Q has no auto
    EnsureHom(orb);   # AutQ depends on Q
    orb.AutQ := AutomorphismGroup(orb.Q);
    orb.A_gens := InducedAutoGens(orb.Stab, orb.H_ref, orb.hom);
end;

# ---- block-wreath ambient for normalizer computation ------------------
# An FPF subgroup H of S_M with cycle-type [m_1, m_2, ...] preserves its own
# cycle decomposition, so N_{S_M}(H) is contained in the block-stabilizer
# Stab_S_M(blocks) = direct product over distinct sizes m of (S_m wr S_count(m)).
# For [4,4,4,4] this is S_4 wr S_4 (size 7.96M vs |S_16|=20.9T): ~3 billion
# times smaller search space for Schreier-Sims, with mathematically identical
# normalizer.
BlockWreathFromPartition := function(partition)
    local factors, i, j, m, mult;
    factors := [];
    i := 1;
    while i <= Length(partition) do
        m := partition[i];
        mult := 0;
        j := i;
        while j <= Length(partition) and partition[j] = m do
            mult := mult + 1;
            j := j + 1;
        od;
        if mult = 1 then
            Add(factors, SymmetricGroup(m));
        else
            Add(factors, WreathProduct(SymmetricGroup(m), SymmetricGroup(mult)));
        fi;
        i := j;
    od;
    if Length(factors) = 1 then return factors[1]; fi;
    return DirectProduct(factors);
end;

# ---- q-size-filtered H-cache helpers ----------------------------------
# An H-cache entry stores per-subgroup data needed for Goursat fiber-product
# enumeration: H_gens, N_H_gens (= Normalizer(S_M, H)), and a list of orbit
# records (one per N_H-orbit on { K normal in H : K <> H, |H/K| in filter }).
# `computed_q_sizes` tracks which Q-sizes are populated; lazy/incremental
# extension lets subsequent runs at higher target_n add the larger Q-sizes
# they need without rebuilding from scratch.  Sentinel `fail` = "all sizes".

# Q-iso classes (as group reps) the LEFT cache must cover when consumed
# against a RIGHT factor of degree M_R.  Returns list of GROUPS, or `fail`
# meaning "full coverage" (no filter).
#
# For M_R >= 6: the union of subgroup orders of TG(M_R, *) already spans
# most divisors of typical |H|, so the filter buys little and the cache is
# simpler/faster with `fail` (avoids per-Q GQuotients calls during
# enumeration and skips cache extension on later reads).
RequiredQGroups := function(M_R)
    local result, seen, t, T, K, Q, qid;
    if M_R >= 6 then return fail; fi;
    result := [];
    seen := Set([]);
    if M_R = 0 then return result; fi;
    for t in [1..NrTransitiveGroups(M_R)] do
        T := TransitiveGroup(M_R, t);
        for K in NormalSubgroups(T) do
            if Size(K) = Size(T) then continue; fi;
            Q := T / K;
            qid := SafeId(Q);
            if not (qid in seen) then
                AddSet(seen, qid);
                Add(result, Q);
            fi;
        od;
    od;
    return result;
end;

QIdsOfGroups := function(q_groups)
    if q_groups = fail then return fail; fi;
    return Set(List(q_groups, SafeId));
end;

QGroupsMissing := function(have_ids, want_groups)
    # want_groups = fail means "full coverage needed". have_ids = fail
    # means "already full coverage". Return values:
    #   []   -- nothing missing (no extension needed)
    #   fail -- need full extension (caller should extend to fail)
    #   list -- specific Q-groups to add via tiered enumeration
    if want_groups = fail then
        if have_ids = fail then return []; fi;
        return fail;
    fi;
    if have_ids = fail then return []; fi;
    return Filtered(want_groups, Q -> not (SafeId(Q) in have_ids));
end;

NormalizeHCacheEntry := function(entry)
    if not IsBound(entry.computed_q_ids) then
        entry.computed_q_ids := fail;
    fi;
    return entry;
end;

# TIERED-OPT enumeration: shared per-H setup + |Q| | |H| short-circuit.
# Per H: ONE DerivedSubgroup, ONE abel_hom call.  Per Q:
#   - |Q| ∤ |H|        -> skip (no surjection possible)
#   - prime Q          -> abelianization (cached A, MaximalSubgroupClassReps)
#   - abelian non-prime Q -> GQuotients(A, Q) on the smaller A
#   - non-abelian Q    -> GQuotients(H, Q) on H itself
#
# NormalSubgroups fast path: for H with few normal subgroups (e.g. S_n, A_n
# which have only 3 / 2 normals), enumerate all normals at once and filter
# by quotient iso-class.  This avoids expensive GQuotients(H, S_n) calls.
# Use this path for H that is simple-or-near-simple (NormalSubgroups is
# O(small) regardless of |H|), or for moderately-sized H.  For complex H
# like D_8^4 with thousands of normals, the tiered Q-by-Q path is preferred.
_EnumerateNormalsForQGroups := function(H, q_groups)
    local q_size_H, DH, abel_hom, A, result, Q, sz, p, max_subs, epi,
          qids_set, all_normals, K, qid_K, use_direct;
    if q_groups = fail then
        return Filtered(NormalSubgroups(H), K -> K <> H);
    fi;
    if Length(q_groups) = 0 then return []; fi;
    # Direct NormalSubgroups + Q-id filter is only cheaper than the smart
    # per-Q routing below when the largest Q is too big for GQuotients to
    # finish (|Q| > 200 in practice).  For everything else — and especially
    # for prime Q, where the fast path is just MaximalSubgroupClassReps(A)
    # on the abelianization — fall through to the per-Q routing.  This was
    # gated on |H| <= 10^6 by mistake, which silently sent every typical
    # H (|H|=4096, 1536, 768, ...) through the slow NS path.
    use_direct := Maximum(List(q_groups, Size)) > 200;
    if use_direct then
        qids_set := Set(List(q_groups, SafeId));
        all_normals := Filtered(NormalSubgroups(H), K -> K <> H);
        result := [];
        for K in all_normals do
            qid_K := SafeId(H/K);
            if qid_K in qids_set then Add(result, K); fi;
        od;
        return Set(result);
    fi;
    q_size_H := Size(H);
    DH := DerivedSubgroup(H);
    if Size(DH) = q_size_H then
        abel_hom := fail; A := fail;
    else
        abel_hom := NaturalHomomorphismByNormalSubgroup(H, DH);
        A := Range(abel_hom);
    fi;
    result := [];
    for Q in q_groups do
        sz := Size(Q);
        if q_size_H mod sz <> 0 then continue; fi;
        if IsPrimeInt(sz) then
            if abel_hom = fail then continue; fi;
            if Size(A) mod sz <> 0 then continue; fi;
            p := sz;
            max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = p);
            Append(result, List(max_subs, K -> PreImage(abel_hom, K)));
        elif IsAbelian(Q) then
            if abel_hom = fail then continue; fi;
            for epi in GQuotients(A, Q) do
                Add(result, PreImage(abel_hom, Kernel(epi)));
            od;
        else
            Append(result, Set(List(GQuotients(H, Q), Kernel)));
        fi;
    od;
    return Set(result);
end;

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
            qid := SafeId(Q_H)
        ));
    od;
    return orbits;
end;

ComputeHCacheEntry := function(H, S_M, q_groups)
    local N_H, normals;
    N_H := Normalizer(S_M, H);
    normals := _EnumerateNormalsForQGroups(H, q_groups);
    return rec(
        H_gens := GeneratorsOfGroup(H),
        N_H_gens := GeneratorsOfGroup(N_H),
        computed_q_ids := QIdsOfGroups(q_groups),
        orbits := _ComputeOrbitRecsFromKs(H, N_H, normals)
    );
end;

ExtendHCacheEntry := function(entry, S_M, additional_q_groups)
    local H, N_H, current, missing_groups, normals, new_orbits, all_normals;
    if entry.computed_q_ids = fail then return entry; fi;
    H := SafeGroup(entry.H_gens, S_M);
    N_H := SafeGroup(entry.N_H_gens, S_M);
    current := entry.computed_q_ids;
    if additional_q_groups = fail then
        # Extend to FULL coverage: enumerate ALL normals; add only the K's
        # whose quotient iso-class is not already in current.
        all_normals := Filtered(NormalSubgroups(H), K -> K <> H);
        normals := Filtered(all_normals, K -> not (SafeId(H/K) in current));
        new_orbits := _ComputeOrbitRecsFromKs(H, N_H, normals);
        Append(entry.orbits, new_orbits);
        entry.computed_q_ids := fail;
        return entry;
    fi;
    missing_groups := QGroupsMissing(current, additional_q_groups);
    if Length(missing_groups) = 0 then return entry; fi;
    normals := _EnumerateNormalsForQGroups(H, missing_groups);
    new_orbits := _ComputeOrbitRecsFromKs(H, N_H, normals);
    Append(entry.orbits, new_orbits);
    UniteSet(entry.computed_q_ids, QIdsOfGroups(missing_groups));
    return entry;
end;

SaveHCacheList := function(path, h_cache)
    local tmp;
    # Atomic write: PrintTo to a .tmp file, then `mv` to the final path.
    # Prevents corrupt-cache leftovers if the process is killed mid-write.
    # Unique tmp filename per call: prevents two GAP workers from clobbering
    # each other's PrintTo when racing on the same cache file.
    tmp := Concatenation(path, ".tmp.", String(Runtime()), ".",
                          String(Random([1..1000000])));
    PrintTo(tmp, "H_CACHE := ", h_cache, ";\n");
    Exec(Concatenation("mv -f -- '", tmp, "' '", path, "'"));
end;

# Read last ~200 bytes of a file and check it ends with "];" (the H_CACHE
# closing bracket).  Used as a corruption sentinel: if a previous run was
# killed mid-PrintTo, the file is truncated and won't end with "];".
IsValidCacheFile := function(path)
    local f, content, n, i;
    if not IsExistingFile(path) then return false; fi;
    f := InputTextFile(path);
    if f = fail then return false; fi;
    content := ReadAll(f);
    CloseStream(f);
    n := Length(content);
    if n < 20 then return false; fi;
    # Strip trailing whitespace.
    while n > 0 and content[n] in [' ', '\n', '\r', '\t'] do
        n := n - 1;
    od;
    if n < 2 then return false; fi;
    return content[n-1] = ']' and content[n] = ';';
end;

# ---- Load LEFT side (shared across all jobs in this batch) ----
ML := 14;
LEFT_PARTITION := [4,4,4,2];
SUBS_LEFT_PATH  := "/cygdrive/c/Users/jeffr/Downloads/Lifting/predict_species_tmp/_two_factor_topt/_batch/[2,1]_[4,3]_[4,3]_[4,3]_77cd7229e4a0/subs_left.g";
CACHE_LEFT_PATH := "/cygdrive/c/Users/jeffr/Downloads/Lifting/predict_species_tmp/_h_cache_topt/14/[4,4,4,2]/[2,1]_[4,3]_[4,3]_[4,3].g";

# Load JOBS array first so we can compute the LEFT q-size filter from the
# union of m_right's across all jobs in this batch.
JOBS := [
  rec(m_right := 4, burnside_m2 := 0, output_path := "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_sn_topt/18/[4,4,4,4,2]/[2,1]_[4,2]_[4,3]_[4,3]_[4,3].g", combo_header := "# combo: [ [ 2, 1 ], [ 4, 2 ], [ 4, 3 ], [ 4, 3 ], [ 4, 3 ] ]", combo_str := "[2,1]_[4,2]_[4,3]_[4,3]_[4,3]", mode_str := "distinguished", right_tg_d := 4, right_tg_t := 2, subs_right := "", cache_right := "")
];

S_ML := SymmetricGroup(ML);
W_ML := BlockWreathFromPartition(LEFT_PARTITION);
batch_t0 := Runtime();

LEFT_Q_GROUPS := [];
seen_qids := Set([]);
for job_idx in [1..Length(JOBS)] do
    rq := RequiredQGroups(JOBS[job_idx].m_right);
    if rq = fail then
        # Any job with M_R >= 6 forces full coverage for the whole batch.
        LEFT_Q_GROUPS := fail;
        break;
    fi;
    for Q in rq do
        if not (SafeId(Q) in seen_qids) then
            AddSet(seen_qids, SafeId(Q));
            Add(LEFT_Q_GROUPS, Q);
        fi;
    od;
od;
# Holt-split augmentation: also union in Q-iso classes from each RIGHT
# source's subgroups (RIGHTs that aren't TG factors).  RequiredQGroups(MR)
# only covers TG(MR) quotients, but holt_split RIGHTs are non-transitive
# subdirect products with quotient iso-classes outside that universe.
# Skip augmentation if LEFT_Q_GROUPS = fail (full coverage already).
if LEFT_Q_GROUPS <> fail then
    seen_subs_paths := Set([]);
    for job_idx in [1..Length(JOBS)] do
        if JOBS[job_idx].subs_right <> "" and
           not (JOBS[job_idx].subs_right in seen_subs_paths) then
            AddSet(seen_subs_paths, JOBS[job_idx].subs_right);
            Read(JOBS[job_idx].subs_right);
            for R in SUBGROUPS do
                for K in NormalSubgroups(R) do
                    if Size(K) = Size(R) then continue; fi;
                    Q := R/K;
                    qid := SafeId(Q);
                    if not (qid in seen_qids) then
                        AddSet(seen_qids, qid);
                        Add(LEFT_Q_GROUPS, Q);
                    fi;
                od;
            od;
        fi;
    od;
fi;
if LEFT_Q_GROUPS = fail then
    Print("[t+", Runtime() - batch_t0, "ms] LEFT Q-groups: full coverage\n");
else
    Print("[t+", Runtime() - batch_t0, "ms] LEFT Q-groups: ",
          Length(LEFT_Q_GROUPS), " types, max |Q|=",
          Maximum(Concatenation([0], List(LEFT_Q_GROUPS, Size))), "\n");
fi;

H_CACHE := fail;
if CACHE_LEFT_PATH <> "" and IsValidCacheFile(CACHE_LEFT_PATH) then
    Print("[t+", Runtime() - batch_t0, "ms] reading H_CACHE from disk: ",
          CACHE_LEFT_PATH, "\n");
    Read(CACHE_LEFT_PATH);
    Print("[t+", Runtime() - batch_t0, "ms] H_CACHE read complete: ",
          Length(H_CACHE), " entries\n");
fi;
if H_CACHE <> fail then
    for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
    extend_needed := false;
    for hi in [1..Length(H_CACHE)] do
        missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
        if missing = fail or Length(missing) > 0 then
            extend_needed := true;
        fi;
    od;
    if extend_needed then
        Print("[t+", Runtime() - batch_t0,
              "ms] extending H_CACHE for new Q-sizes...\n");
        for hi in [1..Length(H_CACHE)] do
            missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
            if missing = fail then
                ExtendHCacheEntry(H_CACHE[hi], W_ML, fail);
            elif Length(missing) > 0 then
                ExtendHCacheEntry(H_CACHE[hi], W_ML, missing);
            fi;
        od;
        if CACHE_LEFT_PATH <> "" then
            SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
        fi;
        Print("[t+", Runtime() - batch_t0, "ms] extension done\n");
    fi;
fi;
if H_CACHE = fail then
    Print("[t+", Runtime() - batch_t0, "ms] no cache; reading subs\n");
    Read(SUBS_LEFT_PATH);
    SUBGROUPS_LEFT_RAW := SUBGROUPS;
    Print("[t+", Runtime() - batch_t0, "ms] computing left H_CACHE for ",
          Length(SUBGROUPS_LEFT_RAW), " subgroups (in W_ML)...\n");
    last_hb := Runtime();
    last_hb_count := 0;
    H_CACHE := [];
    for hi in [1..Length(SUBGROUPS_LEFT_RAW)] do
        if hi = 1 or hi - last_hb_count >= 500
           or Runtime() - last_hb >= 60000 then
            Print("  [t+", Runtime() - batch_t0, "ms] H_CACHE starting ",
                  hi, "/", Length(SUBGROUPS_LEFT_RAW),
                  " |H|=", Size(SUBGROUPS_LEFT_RAW[hi]), "\n");
            last_hb := Runtime();
            last_hb_count := hi;
        fi;
        Add(H_CACHE, ComputeHCacheEntry(SUBGROUPS_LEFT_RAW[hi], W_ML, LEFT_Q_GROUPS));
    od;
    Print("[t+", Runtime() - batch_t0, "ms] H_CACHE compute done\n");
    if CACHE_LEFT_PATH <> "" then
        SaveHCacheList(CACHE_LEFT_PATH, H_CACHE);
    fi;
fi;
H_CACHE_L := H_CACHE;
Print("[t+", Runtime() - batch_t0, "ms] starting ReconstructHData on ",
      Length(H_CACHE_L), " entries...\n");
last_hb := Runtime();
H1DATA_LIST := [];
for hi in [1..Length(H_CACHE_L)] do
    Add(H1DATA_LIST, ReconstructHData(H_CACHE_L[hi], S_ML));
    if Runtime() - last_hb >= 60000 then
        Print("  [t+", Runtime() - batch_t0, "ms] ReconstructHData ",
              hi, "/", Length(H_CACHE_L), "\n");
        last_hb := Runtime();
    fi;
od;
Print("[t+", Runtime() - batch_t0, "ms] ReconstructHData done; LEFT loaded: ",
      Length(H_CACHE_L), " entries\n");

# JOBS array was loaded above the LEFT cache build (we needed m_right's to
# determine the q-size filter).
Print("JOBS: ", Length(JOBS), " jobs to run\n");

# Per-job processing.
for job_idx in [1..Length(JOBS)] do
    JOB := JOBS[job_idx];
    job_t0 := Runtime();

    MR := JOB.m_right;
    BURNSIDE_M2 := JOB.burnside_m2;
    OUTPUT_PATH := JOB.output_path;
    COMBO_HEADER := JOB.combo_header;
    Print("\n>> JOB ", job_idx, "/", Length(JOBS),
          " combo=", JOB.combo_str,
          " mode=", JOB.mode_str, " m_right=", MR,
          " burnside_m2=", BURNSIDE_M2, "\n");

    S_MR := SymmetricGroup(MR);
    shift_R := MappingPermListList([1..MR], [ML+1..ML+MR]);

    # ---- Load RIGHT for this job ----
    # TG factors: small, just compute fresh (no cache file).
    # Source-list RIGHT: read cache, extend to LEFT_Q_GROUPS coverage if needed.
    if JOB.right_tg_d > 0 then
        T_orig_j := TransitiveGroup(JOB.right_tg_d, JOB.right_tg_t);
        H_CACHE_R := [ComputeHCacheEntry(T_orig_j, S_MR, fail)];
    else
        H_CACHE := fail;
        if JOB.cache_right <> "" and IsValidCacheFile(JOB.cache_right) then
            Read(JOB.cache_right);
            for hi in [1..Length(H_CACHE)] do NormalizeHCacheEntry(H_CACHE[hi]); od;
            extend_needed := false;
            for hi in [1..Length(H_CACHE)] do
                missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
                if missing = fail or Length(missing) > 0 then
                    extend_needed := true;
                fi;
            od;
            if extend_needed then
                Print("    [t+", Runtime() - job_t0,
                      "ms] extending RIGHT H_CACHE for new Q-types...\n");
                for hi in [1..Length(H_CACHE)] do
                    missing := QGroupsMissing(H_CACHE[hi].computed_q_ids, LEFT_Q_GROUPS);
                    if missing = fail then
                        ExtendHCacheEntry(H_CACHE[hi], S_MR, fail);
                    elif Length(missing) > 0 then
                        ExtendHCacheEntry(H_CACHE[hi], S_MR, LEFT_Q_GROUPS);
                    fi;
                od;
                if JOB.cache_right <> "" then
                    SaveHCacheList(JOB.cache_right, H_CACHE);
                fi;
            fi;
        fi;
        if H_CACHE = fail then
            Read(JOB.subs_right);
            SUBGROUPS_RIGHT_RAW := SUBGROUPS;
            H_CACHE := List(SUBGROUPS_RIGHT_RAW, H -> ComputeHCacheEntry(H, S_MR, LEFT_Q_GROUPS));
            if JOB.cache_right <> "" then
                SaveHCacheList(JOB.cache_right, H_CACHE);
            fi;
        fi;
        H_CACHE_R := H_CACHE;
    fi;
    H2DATA := List(H_CACHE_R, e -> ReconstructHData(e, S_MR));

    # ---- Goursat counting + collect generator lines for emission ----
    fp_lines := [];

    # In burnside_m2 mode, the ordered-pair iteration visits both (a, b) and
    # (b, a) of each non-diagonal orbit-pair.  These produce S_n-conjugate fp's
    # via swap_perm.  Rather than dedup post-hoc (which requires a fragile
    # GAP `=` test on Group objects without StabChain), we emit only the
    # CANONICAL iteration: h2_orb_idx >= h1_orb_idx.  This gives exactly one
    # rep per unordered orbit-pair {a, b}.  The PREDICTED count
    # (TOTAL_ORB + TOTAL_FIX)/2 from Burnside still uses ALL ordered iterations.

    EmitGen := function(F)
        local gens, s;
        gens := GeneratorsOfGroup(F);
        if Length(gens) > 0 then
            s := JoinStringsWithSeparator(List(gens, String), ",");
        else
            s := "";
        fi;
        Add(fp_lines, Concatenation("[", s, "]"));
    end;

    ProcessPairBatch := function(H1data, H2data, H1, H2)
        local total, swap_fixed, h1orb, h2idxs, h2idx, h2orb, key, isoTH,
              isos, n, gensQ, KeyOf, idx, seen, n_orb, queue, j, phi,
              alpha, beta, neighbor, nkey, k, fp, orbit_id, i, swap_phi,
              swap_key, swap_iso_idx, swap_orbit_id,
              h1_orb_idx, orbit_reps_phi, h_0, t_0, swap_orb_id_arr;
        total := 0; swap_fixed := 0;
        for h1_orb_idx in [1..Length(H1data.orbits)] do
            h1orb := H1data.orbits[h1_orb_idx];
            key := String(h1orb.qid);
            if not IsBound(H2data.byqid.(key)) then continue; fi;
            h2idxs := H2data.byqid.(key);

            # Canonical-emission gate for burnside_m2: only emit when
            # h2idx >= h1_orb_idx so each unordered orbit-pair {a,b} is
            # emitted exactly once.  Counters increment on ALL ordered pairs
            # (so PREDICTED via Burnside formula remains correct).
            if h1orb.qsize = 1 then
                for h2idx in h2idxs do
                    h2orb := H2data.orbits[h2idx];
                    if h2orb.qsize = 1 then
                        total := total + 1;
                        if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                            # direct product output
                            fp := Group(Concatenation(GeneratorsOfGroup(H1),
                                                      GeneratorsOfGroup(H2)));
                            EmitGen(fp);
                        fi;
                        if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                            swap_fixed := swap_fixed + 1;
                        fi;
                    fi;
                od;
                continue;
            fi;

            if h1orb.qsize = 2 then
                if MR = 2 then
                    # FAST PATH: RIGHT is C_2 (TG(2,1)) directly. Aut(C_2)
                    # trivial, iso unique. burnside_m2 cannot apply here
                    # (combo [2,1]^2 routes to c2_fast, never reaches here).
                    # F = <gens(K_H), gens(K_T)^shift_R, h_0 * (t_0)^shift_R>
                    for h2idx in h2idxs do
                        h2orb := H2data.orbits[h2idx];
                        if h2orb.qsize <> 2 then continue; fi;
                        total := total + 1;
                        h_0 := First(GeneratorsOfGroup(H1),
                                     g -> not (g in h1orb.K));
                        t_0 := First(GeneratorsOfGroup(H2data.H),
                                     g -> not (g in h2orb.K));
                        fp := Group(Concatenation(
                            Filtered(GeneratorsOfGroup(h1orb.K), g -> g <> ()),
                            List(Filtered(GeneratorsOfGroup(h2orb.K),
                                          g -> g <> ()),
                                 g -> g^shift_R),
                            [h_0 * t_0^shift_R]));
                        EmitGen(fp);
                    od;
                else
                    # SAFE PATH for MR > 2 (covers burnside_m2 self-pair).
                    for h2idx in h2idxs do
                        h2orb := H2data.orbits[h2idx];
                        if h2orb.qsize <> 2 then continue; fi;
                        total := total + 1;
                        if BURNSIDE_M2 = 0 or h2idx >= h1_orb_idx then
                            EnsureHom(h1orb); EnsureHom(h2orb);
                            isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
                            if isoTH <> fail then
                                fp := _GoursatBuildFiberProduct(
                                    H1, H2, h1orb.hom,
                                    CompositionMapping(h2orb.hom,
                                        ConjugatorIsomorphism(H2, shift_R^-1)),
                                    InverseGeneralMapping(isoTH),
                                    [1..ML], [ML+1..ML+MR]);
                                if fp <> fail then EmitGen(fp); fi;
                            fi;
                        fi;
                        if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                            swap_fixed := swap_fixed + 1;
                        fi;
                    od;
                fi;
                continue;
            fi;

            for h2idx in h2idxs do
                h2orb := H2data.orbits[h2idx];
                if h2orb.qsize <> h1orb.qsize then continue; fi;
                EnsureHom(h1orb); EnsureHom(h2orb);
                isoTH := IsomorphismGroups(h2orb.Q, h1orb.Q);
                if isoTH = fail then continue; fi;
                # Lazy compute AutQ + A_gens (skipped if RIGHT only has Q's
                # of size <=2, which use fast paths).
                EnsureAutQ(h1orb);
                EnsureAutQ(h2orb);

                isos := List(AsList(h2orb.AutQ), a -> a * isoTH);
                n := Length(isos);
                gensQ := GeneratorsOfGroup(h2orb.Q);
                KeyOf := function(phi) return List(gensQ, q -> Image(phi, q)); end;
                idx := rec();
                for i in [1..n] do idx.(String(KeyOf(isos[i]))) := i; od;

                seen := ListWithIdenticalEntries(n, false);
                orbit_id := ListWithIdenticalEntries(n, 0);
                n_orb := 0;
                orbit_reps_phi := [];
                for i in [1..n] do
                    if seen[i] then continue; fi;
                    n_orb := n_orb + 1;
                    Add(orbit_reps_phi, isos[i]);
                    seen[i] := true; orbit_id[i] := n_orb;
                    queue := [i];
                    while Length(queue) > 0 do
                        j := Remove(queue);
                        phi := isos[j];
                        for alpha in h1orb.A_gens do
                            neighbor := phi * alpha;
                            nkey := String(KeyOf(neighbor));
                            if IsBound(idx.(nkey)) then
                                k := idx.(nkey);
                                if not seen[k] then
                                    seen[k] := true; orbit_id[k] := n_orb; Add(queue, k);
                                fi;
                            fi;
                        od;
                        for beta in h2orb.A_gens do
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
                total := total + n_orb;

                # Compute swap-orbit-id per orbit rep (used for both within-pair
                # canonical emission gate and swap_fixed counter).
                # In burnside_m2 self-pair, orbit rep i may be swap-paired with
                # rep j (where j = swap_orb_id_arr[i]).  Emit only when i <= j.
                swap_orb_id_arr := ListWithIdenticalEntries(n_orb, -1);
                if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                    for i in [1..n_orb] do
                        phi := orbit_reps_phi[i];
                        swap_phi := InverseGeneralMapping(phi);
                        swap_key := String(KeyOf(swap_phi));
                        if IsBound(idx.(swap_key)) then
                            swap_orb_id_arr[i] := orbit_id[idx.(swap_key)];
                        fi;
                    od;
                fi;

                # Emit orbit reps (canonical-gated).
                if BURNSIDE_M2 = 0 or h2idx > h1_orb_idx then
                    # Non-self canonical: emit all orbit reps
                    for i in [1..n_orb] do
                        fp := _GoursatBuildFiberProduct(
                            H1, H2, h1orb.hom,
                            CompositionMapping(h2orb.hom,
                                ConjugatorIsomorphism(H2, shift_R^-1)),
                            InverseGeneralMapping(orbit_reps_phi[i]),
                            [1..ML], [ML+1..ML+MR]);
                        if fp <> fail then EmitGen(fp); fi;
                    od;
                elif BURNSIDE_M2 = 1 and h2idx = h1_orb_idx then
                    # Self-pair: within-pair canonical (i <= swap_orb_id[i]).
                    for i in [1..n_orb] do
                        if swap_orb_id_arr[i] >= i then
                            fp := _GoursatBuildFiberProduct(
                                H1, H2, h1orb.hom,
                                CompositionMapping(h2orb.hom,
                                    ConjugatorIsomorphism(H2, shift_R^-1)),
                                InverseGeneralMapping(orbit_reps_phi[i]),
                                [1..ML], [ML+1..ML+MR]);
                            if fp <> fail then EmitGen(fp); fi;
                        fi;
                    od;
                fi;

                # Burnside swap-fix counter (uses precomputed swap_orb_id_arr).
                if BURNSIDE_M2 = 1 and h1orb.K = h2orb.K then
                    for i in [1..n_orb] do
                        if swap_orb_id_arr[i] = i then
                            swap_fixed := swap_fixed + 1;
                        fi;
                    od;
                fi;
            od;
        od;
        return rec(orbits := total, swap_fixed := swap_fixed);
    end;

    TOTAL_ORB := 0;
    TOTAL_FIX := 0;
    last_hb_ms := Runtime() - job_t0;
    n_pairs_done := 0;
    n_pairs_total := Length(H1DATA_LIST) * Length(H2DATA);
    Print("    [t+", Runtime() - job_t0, "ms] starting H1xH2 loop: ",
          Length(H1DATA_LIST), " x ", Length(H2DATA),
          " = ", n_pairs_total, " pairs\n");
    for i in [1..Length(H1DATA_LIST)] do
        H1data_j := H1DATA_LIST[i];
        H1_j := H1data_j.H;
        # For burnside_m2: override H2DATA[1] with H1data so K = K comparison works.
        if BURNSIDE_M2 = 1 then
            H2DATA[1] := H1data_j;
        fi;
        for j in [1..Length(H2DATA)] do
            H2data_j := H2DATA[j];
            H2_j := H2data_j.H^shift_R;
            res_pair := ProcessPairBatch(H1data_j, H2data_j, H1_j, H2_j);
            TOTAL_ORB := TOTAL_ORB + res_pair.orbits;
            TOTAL_FIX := TOTAL_FIX + res_pair.swap_fixed;
            n_pairs_done := n_pairs_done + 1;
            if (Runtime() - job_t0) - last_hb_ms >= 30000 then
                Print("    [t+", Runtime() - job_t0, "ms] pair ",
                      n_pairs_done, "/", n_pairs_total,
                      " (i=", i, "/", Length(H1DATA_LIST),
                      ", j=", j, "/", Length(H2DATA), ") ",
                      "orb_so_far=", TOTAL_ORB, "\n");
                last_hb_ms := Runtime() - job_t0;
            fi;
        od;
    od;

    if BURNSIDE_M2 = 1 then
        PREDICTED := (TOTAL_ORB + TOTAL_FIX) / 2;
    else
        PREDICTED := TOTAL_ORB;
    fi;

    elapsed_ms := Runtime() - job_t0;

    # Atomic per-combo write: write to OUTPUT_PATH.tmp, then mv to final path.
    # This prevents partial-file corruption if GAP crashes mid-write; the
    # final file only appears once all gens + sentinel are flushed.
    TMP_OUT := Concatenation(OUTPUT_PATH, ".tmp");
    PrintTo(TMP_OUT, COMBO_HEADER, "\n");
    AppendTo(TMP_OUT, "# candidates: ", PREDICTED, "\n");
    AppendTo(TMP_OUT, "# deduped: ", PREDICTED, "\n");
    AppendTo(TMP_OUT, "# elapsed_ms: ", elapsed_ms, "\n");
    for line in fp_lines do
        AppendTo(TMP_OUT, line, "\n");
    od;
    Exec(Concatenation("mv -f -- '", TMP_OUT, "' '", OUTPUT_PATH, "'"));

    Print("RESULT idx=", job_idx, " predicted=", PREDICTED,
          " orbits=", TOTAL_ORB, " swap_fixed=", TOTAL_FIX,
          " elapsed_ms=", elapsed_ms, "\n");
od;

LogTo();
QUIT;
