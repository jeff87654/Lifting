# c2_glue_path_writer.g — streaming C2-glue engine for distinguished combos
# whose RIGHT block forces the Goursat glue quotient set down to {1, C2}.
#
# Covers combos X_[d,t] where the (d,t) block has species-multiplicity 1 and
#   (d,t) = (2,1):  T = C2, glue in {1, C2} for ANY LEFT X.
#   (d,t) = (3,1):  T = C3, glue = {1} when 3 does not divide |H_L| (coprime).
#   (d,t) = (3,2):  T = S3, glue in {1, C2} (kernel A3) when 3 ∤ |H_L|.
#
# Because Aut(C2) is trivial, every Goursat pairing is entry-local:
#   per LEFT class B (one line of X's output .g):
#     1 direct-product class  B x T, plus
#     one fiber-product class per N(B)-orbit of index-2 kernels K of B
#       (paired with T's unique index-2 kernel K_T).
# No aut-saturation, no double cosets, no cross-pair dedup, hence NO LEFT
# H-cache: the source file is streamed line by line in O(1) memory.
#
# Class fusion / labelled math (matches the production HARVEST formula
# cs = M!/(NL*NR) in predict_2factor_topt.py):
#   N_{S_n}(B x T)    = N_{S_m}(B) x N_{S_d}(T)             (species mult 1
#   N_{S_n}(fiber_K)  = Stab_{N_{S_m}(B)}(K) x N_{S_d}(T)    fixes the RIGHT
#                                                            block setwise)
#   The T-side stabilizer of K_T is all of N_{S_d}(T) because K_T is the
#   unique index-2 kernel (characteristic).  Templated jobs are rejected if
#   T has more than one index-2 kernel.
#
# Per-line implementation (2026-07-02 opt2 rework, validated 7,304/7,304
# exact vs parallel_sn_opt0610 across all c2_glue/c3_glue-routed combos
# n=6..17; A/B 1.42x on the D8 family, 2.31x on [8,*]-block sources —
# memory `c2glue_perline_optimization`):
#   * Textual direct-product emit: the DP class line is the source line text
#     + shifted-T tail (the parsed gens ARE the source line; the fast_c3
#     textual path already relied on this format invariant).  Whitespace is
#     stripped so backslash-wrapped sources canonicalize as before.
#   * Kernel orbits on DUAL VECTORS: a hyperplane U <= A = F_2^d is the
#     kernel of a unique nonzero dual vector v; the subspace right-action
#     U -> rowspace(U*M) corresponds to v -> v*(M^-1)^T (an equivariant
#     bijection, so orbit counts and stabilizer sizes are unchanged), and
#     each orbit walks with plain vector*matrix steps instead of per-step
#     OnSubspacesByCanonicalBasis row reductions; the hyperplane basis is
#     reconstructed via NullspaceMat only for orbit REPRESENTATIVES.  The
#     representative choice within an orbit may differ from the pre-opt2
#     subspace-iteration choice — a different but equivalent class rep
#     (standing conjugate-freedom rule; deduped/class_sum invariant).
#   * b0 selection by dot product: g in K  <=>  coords(g Phi).dual_v = 0,
#     so no per-kernel stabilizer chain is built.
#   * Buffered emit: one WriteAll per source line.
#   The per-line Normalizer(W, B) is unchanged and remains the dominant
#   residual cost (31-37% pre-opt2, ~60-75% post); see the memory for the
#   ranked follow-ups ([3,2] file transform, .nl sidecars, M6).
#
# Tokens: __LOG__, __JOBS__
# JOBS entries: rec(combo, src, body, d, t, m, n, cs_src, xdeg := [..],
#                   xsp := [[d,t]..])
#   cs_src = the source file's `# class_sum:` header, or -1.  For a (3,1)
#   RIGHT (T = C3, no C2 quotient) a known cs_src enables the fast_c3 path:
#   cs = (n!/(m!*NT)) * cs_src in closed form, no per-line Normalizer; with
#   C2GLUE_CHECK off the job degrades to a pure textual line-append stream.
# Emits per job:  RESULT combo=... predicted=N candidates=N class_sum=CS
#                 n_src=N elapsed_ms=MS
# or              RESULT_NA combo=... reason=...   (caller falls back to the
#                                                   general engine)

LogTo("__LOG__");
SetPrintFormattingStatus("*stdout*", false);

Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_a.g");
Read("__JOBS__");

if not IsBound(C2GLUE_CHECK) then C2GLUE_CHECK := true; fi;

# Read one complete bracketed generator list from the stream, joining GAP
# backslash continuations and bracket-balancing across physical lines
# (matches parse_combo_file in predict_2factor_topt.py).  Returns the
# string, or fail at EOF.  Comment / blank lines before a list are skipped.
C2GlueReadGenList := function(src)
    local line, buf, depth, i, started;
    buf := ""; depth := 0; started := false;
    while true do
        line := ReadLine(src);
        if line = fail then
            if started then
                Error("c2_glue: EOF inside a generator list (corrupt source)");
            fi;
            return fail;
        fi;
        line := Chomp(line);
        if Length(line) > 0 and line[Length(line)] = '\r' then
            line := line{[1..Length(line)-1]};
        fi;
        if not started then
            if Length(line) = 0 or line[1] <> '[' then continue; fi;
            started := true;
        fi;
        if Length(line) > 0 and line[Length(line)] = '\\' then
            line := line{[1..Length(line)-1]};
        fi;
        Append(buf, line);
        for i in [1..Length(line)] do
            if line[i] = '[' then
                depth := depth + 1;
            elif line[i] = ']' then
                depth := depth - 1;
            fi;
        od;
        if depth = 0 then return buf; fi;
    od;
end;

# N(B)-orbit records of index-2 kernels of H, computed on dual vectors
# (see the header).  Each rec carries the kernel's generator list, the
# stabilizer ORDER (|N_H| / orbit length), and the dual vector dual_v used
# for the caller's b0 dot-product test.  gen_coords are the GF(2)
# coordinate vectors of H_gens in A = H/Phi (Phi <= K for every kernel K,
# so g in K  <=>  coords(g).dual_v = 0).
C2GlueKernelOrbits := function(H, N_H, H_gens)
    local A_data, action, mats, dual_mats, Mgrp, V, vecs, lift_v, orbits,
          recs, Phi_gens, NH_size, gen_coords;
    A_data := ElemAbPQuotient(H, 2);
    if A_data.d = 0 then
        return rec(d := 0, recs := [], gen_coords := []);
    fi;
    Phi_gens := GeneratorsOfGroup(A_data.Phi);
    gen_coords := List(H_gens, g ->
        ExponentsOfPcElement(A_data.pcgs, Image(A_data.hom, g)) * Z(2)^0);
    action := NHActionOnElemAb(N_H, A_data, 2);
    mats := action.mats;
    V := GF(2) ^ A_data.d;
    vecs := Filtered(Elements(V), v -> not IsZero(v));
    lift_v := function(v)
        local U_rep, U_gens, u, a_elem, K;
        U_rep := NullspaceMat(TransposedMat([v]));
        U_gens := [];
        for u in U_rep do
            a_elem := Product(List([1..A_data.d],
                i -> A_data.pcgs[i] ^ IntFFE(u[i])));
            Add(U_gens, PreImagesRepresentative(A_data.hom, a_elem));
        od;
        K := SubgroupNC(H, Concatenation(Phi_gens, U_gens));
        return GeneratorsOfGroup(K);
    end;
    NH_size := Size(N_H);
    if Length(mats) = 0 then
        return rec(d := A_data.d, gen_coords := gen_coords,
                   recs := List(vecs, v ->
            rec(K_H_gens := lift_v(v), dual_v := v,
                Stab_NH_KH_size := NH_size)));
    fi;
    dual_mats := List(mats, M -> TransposedMat(Inverse(M)));
    Mgrp := Group(dual_mats);
    orbits := OrbitsDomain(Mgrp, vecs, OnRight);
    recs := List(orbits, orb -> rec(
        K_H_gens := lift_v(orb[1]), dual_v := orb[1],
        Stab_NH_KH_size := NH_size / Length(orb)));
    return rec(d := A_data.d, recs := recs, gen_coords := gen_coords);
end;

# Compact one-line generator list, identity gens dropped (format matches the
# production emit: "[(1,2),(3,4,5,6)]").
C2GlueGenListString := function(gens)
    local parts;
    parts := List(Filtered(gens, g -> g <> ()), String);
    if Length(parts) = 0 then
        Error("C2GlueGenListString: trivial generator list (corrupt source?)");
    fi;
    return Concatenation("[",
        JoinStringsWithSeparator(parts, ","), "]\n");
end;

C2GlueProcessJob := function(job)
    local t0, T, shift, T_gens_s, NT, t2kers, K_T, KT_gens_s, t_coset_s,
          S_M, src, out, line, deduped, cs, n_lines, fact_n, gens, B, N_B,
          NL, recs, r, contrib, orb_sum, n_hyp, d0, dt,
          first_line, osizes, P, W, P_gens, orb, g, ko, fast_c3, tail_s, ln,
          n_skipped, buf, b0, gi;
    t0 := Runtime();

    # ---- RIGHT block: T = TransitiveGroup(d,t) on points m+1..m+d ----
    T := TransitiveGroup(job.d, job.t);
    shift := MappingPermListList([1..job.d], [job.m+1..job.m+job.d]);
    T_gens_s := List(GeneratorsOfGroup(T), g -> g^shift);
    NT := Size(Normalizer(SymmetricGroup(job.d), T));

    # Coprime precheck for d=3 RIGHTs: 3 | |H_L| would admit C3/S3 glue,
    # which this path does not enumerate.  |H_L| divides the product of the
    # X species orders, so "no species order divisible by 3" is sufficient.
    if job.d = 3 then
        for dt in job.xsp do
            if Size(TransitiveGroup(dt[1], dt[2])) mod 3 = 0 then
                Print("RESULT_NA combo=", job.combo,
                      " reason=left_species_order_divisible_by_3\n");
                return;
            fi;
        od;
    fi;

    # ---- C2-glue data on the T side ----
    t2kers := Filtered(NormalSubgroups(T), N -> Index(T, N) = 2);
    if Length(t2kers) > 1 then
        Print("RESULT_NA combo=", job.combo,
              " reason=multiple_T_c2_kernels\n");
        return;
    fi;
    if Length(t2kers) = 1 then
        K_T := t2kers[1];
        KT_gens_s := List(GeneratorsOfGroup(K_T), g -> g^shift);
        t_coset_s := First(GeneratorsOfGroup(T), g -> not g in K_T)^shift;
    else
        K_T := fail;   # T has no C2 quotient (C3): direct products only.
    fi;

    # Closed-form class_sum for a no-C2-quotient RIGHT (C3): every emitted
    # class is the direct product B x T with N_{S_n}(B x T) = N_{S_m}(B) x
    # N_{S_d}(T), so cs = Sum_i n!/(NL_i*NT) = (n!/(m!*NT)) * cs_src where
    # cs_src = Sum_i m!/NL_i is the SOURCE file's # class_sum header.  The
    # per-line Normalizer(W, B) — the only expensive step on this path — is
    # then never needed, and with C2GLUE_CHECK off the stream degrades to a
    # pure textual append of the shifted T generators.
    fast_c3 := (K_T = fail) and IsBound(job.cs_src) and job.cs_src >= 0;
    tail_s := Concatenation(",",
        JoinStringsWithSeparator(List(T_gens_s, String), ","), "]");

    # Optional line-range shard (mirrors c2_glue2_path_writer.g): process
    # only source lines line_lo..line_hi (1-based, inclusive; 0 = open).
    # The per-line work is entry-local, so shard counts merge exactly.
    if not IsBound(job.line_lo) then job.line_lo := 0; fi;
    if not IsBound(job.line_hi) then job.line_hi := 0; fi;
    if fast_c3 and (job.line_lo > 1 or job.line_hi > 0) then
        # The closed-form cs is whole-file; a windowed job must fall back
        # to the per-line normalizer path (callers shouldn't shard (3,1)
        # RIGHTs anyway — the textual stream is I/O-bound).
        fast_c3 := false;
    fi;

    # ---- stream the LEFT source ----
    src := InputTextFile(job.src);
    if src = fail then
        Print("RESULT_NA combo=", job.combo, " reason=source_unreadable\n");
        return;
    fi;
    out := OutputTextFile(job.body, false);
    SetPrintFormattingStatus(out, false);

    S_M := SymmetricGroup(job.m);
    fact_n := Factorial(job.n);
    deduped := 0; cs := 0; n_lines := 0; first_line := true;

    n_skipped := 0;
    while n_skipped < job.line_lo - 1 do
        line := C2GlueReadGenList(src);
        if line = fail then break; fi;
        n_skipped := n_skipped + 1;
    od;

    line := C2GlueReadGenList(src);
    while line <> fail do
        if job.line_hi > 0 and n_skipped + n_lines >= job.line_hi then
            break;
        fi;
        if fast_c3 and not C2GLUE_CHECK and not first_line then
            # Pure textual stream: direct product = source line + shifted T
            # generators; no parse, no group objects.  (Line 1 still goes
            # through the parsed path below for the orbit sanity check.)
            ln := Length(line);
            while ln > 0 and (line[ln] = ' ' or line[ln] = '\t') do
                ln := ln - 1;
            od;
            if ln = 0 or line[ln] <> ']' then
                Error("c2_glue: malformed source line ", n_lines + 1);
            fi;
            WriteAll(out, Concatenation(line{[1..ln-1]}, tail_s, "\n"));
            deduped := deduped + 1;
            n_lines := n_lines + 1;
            line := C2GlueReadGenList(src);
            continue;
        fi;
            gens := EvalString(line);
            B := Group(gens);

            if job.d = 3 and Size(B) mod 3 = 0 then
                # belt-and-braces (precheck above should make this dead code)
                CloseStream(src); CloseStream(out);
                Print("RESULT_NA combo=", job.combo,
                      " reason=left_order_divisible_by_3\n");
                return;
            fi;
            if first_line then
                # Source sanity: B's orbits must realize X's block degrees.
                osizes := SortedList(List(Orbits(B, [1..job.m]), Length));
                if osizes <> SortedList(job.xdeg) then
                    CloseStream(src); CloseStream(out);
                    Print("RESULT_NA combo=", job.combo,
                          " reason=source_orbit_mismatch\n");
                    return;
                fi;
                # Block-product group P = prod_i T_i in the source layout
                # (the constituents of any subdirect class are exactly the
                # block transitive groups).  Every class in the file is a
                # subgroup of P, and N_{S_m}(B) <= N_{S_m}(P) =: W, so the
                # per-line normalizer can be computed inside the small W
                # instead of S_m — same group, much cheaper backtrack
                # (mirrors the production engine's Normalizer(W_ML, H)).
                P_gens := [];
                for orb in Orbits(B, [1..job.m]) do
                    Append(P_gens, Filtered(
                        List(gens, x -> RestrictedPerm(x, orb)),
                        x -> x <> ()));
                od;
                P := Group(P_gens);
                if not fast_c3 then
                    # W is only consumed by the per-line Normalizer(W, B);
                    # the fast C3 path never needs it (closed-form cs).
                    W := Normalizer(S_M, P);
                fi;
                first_line := false;
            fi;
            if C2GLUE_CHECK then
                # Layout consistency: every class must be subdirect in the
                # SAME block-product P (else W-relative normalizers and the
                # whole fusion math would silently be wrong).
                for g in gens do
                    if not g in P then
                        Error("c2_glue: source line ", n_lines + 1,
                              " not inside the block product P");
                    fi;
                od;
            fi;

            if fast_c3 then
                # Direct product only; cs comes from the closed form after
                # the loop.  Textual emit: line text + tail (identical
                # output to the String round-trip on production sources).
                line := Filtered(line, ch -> ch <> ' ' and ch <> '\t');
                ln := Length(line);
                if ln = 0 or line[ln] <> ']' then
                    Error("c2_glue: malformed source line ", n_lines + 1);
                fi;
                WriteAll(out, Concatenation(line{[1..ln-1]}, tail_s, "\n"));
                deduped := deduped + 1;
                n_lines := n_lines + 1;
                line := C2GlueReadGenList(src);
                continue;
            fi;

            N_B := Normalizer(W, B);
            NL := Size(N_B);

            # Q = 1: direct product — textual emit (source text + tail).
            # Strip ALL whitespace first: GAP String(perm) never contains
            # spaces, but a backslash-wrapped source (bootstrap files) joins
            # with interior indentation the String round-trip would have
            # normalized away.
            line := Filtered(line, ch -> ch <> ' ' and ch <> '\t');
            ln := Length(line);
            if ln = 0 or line[ln] <> ']' then
                Error("c2_glue: malformed source line ", n_lines + 1);
            fi;
            buf := Concatenation(line{[1..ln-1]}, tail_s, "\n");
            deduped := deduped + 1;
            contrib := fact_n / (NL * NT);
            if not IsInt(contrib) then
                Error("c2_glue: non-integer class_sum contribution (direct)");
            fi;
            cs := cs + contrib;

            # Q = C2: one fiber product per N(B)-orbit of index-2 kernels.
            if K_T <> fail then
                ko := C2GlueKernelOrbits(B, N_B, gens);
                recs := ko.recs;
                if C2GLUE_CHECK then
                    # Orbit-stabilizer identity: orbit sizes must sum to the
                    # total number of index-2 kernels, 2^d0 - 1.
                    d0 := ko.d;
                    n_hyp := 2^d0 - 1;
                    orb_sum := Sum(recs, x -> NL / x.Stab_NH_KH_size);
                    if orb_sum <> n_hyp then
                        Error("c2_glue: kernel orbit-sum check failed: ",
                              orb_sum, " <> ", n_hyp, " at source line ",
                              n_lines + 1);
                    fi;
                fi;
                for r in recs do
                    # b0 = first source gen outside the kernel;
                    # g in K <=> coords(g Phi).dual_v = 0 (dot product).
                    b0 := fail;
                    for gi in [1..Length(gens)] do
                        if ko.gen_coords[gi] * r.dual_v <> 0 * Z(2) then
                            b0 := gens[gi];
                            break;
                        fi;
                    od;
                    if b0 = fail then
                        Error("c2_glue: no generator outside kernel U");
                    fi;
                    Append(buf, C2GlueGenListString(Concatenation(
                        Filtered(r.K_H_gens, g -> g <> ()),
                        KT_gens_s, [b0 * t_coset_s])));
                    deduped := deduped + 1;
                    contrib := fact_n / (r.Stab_NH_KH_size * NT);
                    if not IsInt(contrib) then
                        Error("c2_glue: non-integer class_sum contribution");
                    fi;
                    cs := cs + contrib;
                od;
            fi;
            # One WriteAll per source line (DP + all fiber lines).
            WriteAll(out, buf);
            n_lines := n_lines + 1;
        line := C2GlueReadGenList(src);
    od;
    CloseStream(src);
    CloseStream(out);

    if n_lines = 0 then
        Print("RESULT_NA combo=", job.combo, " reason=empty_source\n");
        return;
    fi;

    if fast_c3 then
        # cs = Sum_i n!/(NL_i*NT) = (n!/(m!*NT)) * Sum_i m!/NL_i
        #    = (n!/(m!*NT)) * cs_src.
        cs := fact_n * job.cs_src / (NT * Factorial(job.m));
        if not IsInt(cs) then
            Error("c2_glue: non-integer closed-form class_sum (cs_src=",
                  job.cs_src, ")");
        fi;
    fi;

    Print("RESULT combo=", job.combo, " predicted=", deduped,
          " candidates=", deduped, " class_sum=", cs,
          " n_src=", n_lines, " elapsed_ms=", Runtime() - t0, "\n");
end;

for _job in JOBS do
    C2GlueProcessJob(_job);
od;

Print("ALL_JOBS_DONE\n");
LogTo();
QUIT;
