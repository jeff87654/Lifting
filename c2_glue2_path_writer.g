# c2_glue2_path_writer.g — streaming C2^2-glue engine for peel_c2_pair combos
# (exactly TWO (2,1) blocks + a non-degree-2 cluster X).
#
# RIGHT cluster R on points {m+1..m+4}: two 2-blocks, block product
# P_R = <a> x <b> with a = (m+1,m+2), b = (m+3,m+4); W_R = N_{S_4}(P_R) = D8
# (order 8, includes the block swap).  The two FPF RIGHT classes and their
# kernel-orbit data under W_R are FIXED and tiny, so everything is
# entry-local per LEFT line B (streamed from X's output .g — no LEFT H-cache):
#
#   per LEFT class B (NL = |N_W(B)|, n! = Factorial(m+4)):
#     Q = 1 :  B x C2^2            cs += n!/(NL*8)
#              B x Delta(<ab>)     cs += n!/(NL*8)
#     Q = C2:  per N(B)-orbit of index-2 kernels K (stab s):
#              K_R = <a> (~ <b> under the swap; |Stab_{D8}| = 4)
#                                  cs += n!/(s*4)
#              K_R = <ab> (swap-fixed; |Stab_{D8}| = 8)
#                                  cs += n!/(s*8)
#              R = Delta, K_R = 1 (|Stab_{D8}| = 8)
#                                  cs += n!/(s*8)
#     Q = V4:  per N(B)-orbit of codim-2 kernels K (stab s, induced
#              A1 <= S3 = Aut(V4) on the 3 intermediate subgroups):
#              one class per double coset A1\S3/A2 with A2 = <(1,2)> (the
#              block swap a<->b, fixing ab); per double coset D:
#                                  cs += n!*|D|/(s*8)
#              (class count by |A1|: 6,3 -> 1; 2 -> 2; 1 -> 3.)
#
# The cs terms are the production HARVEST closed form n!*|A2 d A1|/(NL*NR)
# specialized to this RIGHT; the per-(K,K_R) totals sum to n!*|Aut(Q)|/(NL*NR).
# Verified by hand against the reference tree:
#   [2,1]_[2,1]_[4,3]: 14 classes, class_sum 12600  (= n!(2+12+6)/64, n=8).
#
# Per-line implementation (2026-07-02 opt rework, validated 2,089/2,089
# exact vs parallel_sn_opt0610 across all c2_glue2-routed combos n=8..17;
# A/B 2.15-2.50x on full real S22 combos — memory
# `c2glue_perline_optimization`):
#   * Textual direct-product emits: both Q=1 lines are the source line text
#     + a precomputed tail, whitespace-stripped (String(perm) never contains
#     spaces; wrapped sources canonicalize as before).
#   * C2 kernel orbits on DUAL VECTORS (hyperplane U = ker<v,.>; the
#     subspace action corresponds to v -> v*(M^-1)^T, an equivariant
#     bijection, so orbit counts and stabilizer sizes are unchanged);
#     b0 selection by dot product — no per-kernel stabilizer chain.
#   * V4 (codim-2) kernel orbits on DUAL 2-SPACES (U <-> its annihilator),
#     walking 2xd RREF mats instead of (d-2)xd; the stabilizer and induced
#     A1 <= S3 are computed in the MATRIX image Mgrp = rho(N_B) <= GL(d,2)
#     via OrbitStabilizer — ker(rho) acts trivially on A/U, so
#     rho(Stab_{N_B}(U)) = Stab_{Mgrp}(D) and the induced action is
#     identical.  This replaces Stabilizer(N_H, U, lift_act), whose action
#     callback rebuilt the full dxd action matrix on every evaluation.
#   * A = B/Phi and the N_B action matrices are computed once per line and
#     shared by the C2 and V4 enumerations.
#   * Buffered emit: one WriteAll per source line.
#   Kernel/fiber representative choice within an orbit may differ from the
#   pre-opt subspace-iteration choice — a different but equivalent class
#   representative (standing conjugate-freedom rule); a rep change
#   conjugates A1 within S3, and |A1\S3/A2| plus the |D|-multiset depend
#   only on |A1| (table above), so deduped/class_sum are invariant.  The
#   orbit-sum self-checks remain live.  The per-line Normalizer(W, B) is
#   unchanged and is the dominant residual cost.
#
# Tokens: __LOG__, __JOBS__
# JOBS entries: rec(combo, src, body, m, n, xdeg := [..], xsp := [[d,t]..])
# Emits per job:  RESULT combo=... predicted=N candidates=N class_sum=CS
#                 n_src=N elapsed_ms=MS
# or              RESULT_NA combo=... reason=...

LogTo("__LOG__");
SetPrintFormattingStatus("*stdout*", false);

Read("C:/Users/jeffr/Downloads/Lifting/prototype_stage_a.g");
Read("__JOBS__");

if not IsBound(C2GLUE_CHECK) then C2GLUE_CHECK := true; fi;

C2Glue2ReadGenList := function(src)
    local line, buf, depth, i, started;
    buf := ""; depth := 0; started := false;
    while true do
        line := ReadLine(src);
        if line = fail then
            if started then
                Error("c2_glue2: EOF inside a generator list (corrupt source)");
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

C2Glue2GenListString := function(gens)
    local parts;
    parts := List(Filtered(gens, g -> g <> ()), String);
    if Length(parts) = 0 then
        Error("C2Glue2GenListString: trivial generator list (corrupt source?)");
    fi;
    return Concatenation("[",
        JoinStringsWithSeparator(parts, ","), "]\n");
end;

# Index-2 kernel orbits on dual vectors (same as c2_glue_path_writer.g).
C2Glue2KernelOrbits := function(H, N_H, H_gens, A_data, mats)
    local dual_mats, Mgrp, V, vecs, lift_v, orbits, recs, Phi_gens,
          NH_size, gen_coords;
    if A_data.d = 0 then
        return rec(d := 0, recs := [], gen_coords := []);
    fi;
    Phi_gens := GeneratorsOfGroup(A_data.Phi);
    gen_coords := List(H_gens, g ->
        ExponentsOfPcElement(A_data.pcgs, Image(A_data.hom, g)) * Z(2)^0);
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

# ---- V4 (codim-2) kernel orbits, dual-2-space + matrix-stabilizer form ----
# Per N_H-orbit of codim-2 subspaces U <= A (represented by the annihilator
# D = U-perp, a 2-dim dual subspace in RREF):
#   K_gens    = preimage generators of U (+ Phi gens),
#   x1, x2    = preimages of the two complement unit directions of U,
#   Stab_size = |N_H| / orbit length,
#   A1        = induced subgroup of S3 on the 3 nonzero vectors of A/U in
#               the order [e1, e2, e1+e2], computed from the stabilizer of
#               D in the matrix image (see the header).
C2Glue2V4KernelOrbits := function(H, N_H, A_data, mats)
    local d, Phi_gens, V, dual2, dual_mats, Mdgrp, safe_act, orbits, recs,
          NH_size, orb, D, U, U_rows, pivots, row, j, comp, reduce,
          lift_vec, K_gens, x1, x2, os, A1_perms, M, vecidx, e1, e2,
          red1, red2;
    d := A_data.d;
    if d < 2 then
        return rec(d := d, n_codim2 := 0, recs := []);
    fi;
    Phi_gens := GeneratorsOfGroup(A_data.Phi);
    V := GF(2) ^ d;
    # all 2-dim dual subspaces in RREF (annihilators of codim-2 subspaces)
    dual2 := List(Subspaces(V, 2), function(s)
        local bv;
        bv := BasisVectors(Basis(s));
        return TriangulizedMat(List(bv, ShallowCopy));
    end);
    safe_act := function(D2, mat)
        return OnSubspacesByCanonicalBasis(D2, mat);
    end;
    lift_vec := function(v)
        local a_elem;
        a_elem := Product(List([1..d], i -> A_data.pcgs[i] ^ IntFFE(v[i])));
        return PreImagesRepresentative(A_data.hom, a_elem);
    end;
    NH_size := Size(N_H);
    if Length(mats) = 0 then
        orbits := List(dual2, D2 -> [D2]);
        dual_mats := [];
    else
        dual_mats := List(mats, M2 -> TransposedMat(Inverse(M2)));
        Mdgrp := Group(dual_mats);
        orbits := OrbitsDomain(Mdgrp, dual2, safe_act);
    fi;
    recs := [];
    for orb in orbits do
        D := orb[1];
        # primal codim-2 subspace: U = annihilator of D, in RREF
        U_rows := NullspaceMat(TransposedMat(D));
        if Length(U_rows) = 0 then
            U := [];
        else
            U := TriangulizedMat(List(U_rows, ShallowCopy));
        fi;
        pivots := [];
        for row in U do
            for j in [1..d] do
                if not IsZero(row[j]) then Add(pivots, j); break; fi;
            od;
        od;
        comp := Filtered([1..d], j -> not (j in pivots));
        if Length(comp) <> 2 then
            Error("c2_glue2: RREF complement is not 2-dimensional");
        fi;
        reduce := function(v)
            local w, i2;
            w := ShallowCopy(v);
            for i2 in [1..Length(U)] do
                if not IsZero(w[pivots[i2]]) then
                    w := w - U[i2];
                fi;
            od;
            return [w[comp[1]], w[comp[2]]];
        end;
        K_gens := [];
        for row in U do
            Add(K_gens, lift_vec(row));
        od;
        Append(K_gens, Phi_gens);
        x1 := lift_vec(IdentityMat(d, GF(2))[comp[1]]);
        x2 := lift_vec(IdentityMat(d, GF(2))[comp[2]]);
        # induced A1 from the stabilizer of D in the DUAL matrix group;
        # each dual stab matrix's PRIMAL partner is its inverse-transpose,
        # and the induced action on A/U is read off through reduce().
        vecidx := function(c)
            if c = [One(GF(2)), Zero(GF(2))] then return 1;
            elif c = [Zero(GF(2)), One(GF(2))] then return 2;
            elif c = [One(GF(2)), One(GF(2))] then return 3;
            else Error("c2_glue2: zero image in quotient action"); fi;
        end;
        A1_perms := [];
        if Length(dual_mats) > 0 then
            os := OrbitStabilizer(Mdgrp, D, safe_act);
            e1 := IdentityMat(d, GF(2))[comp[1]];
            e2 := IdentityMat(d, GF(2))[comp[2]];
            for M in GeneratorsOfGroup(os.stabilizer) do
                red1 := reduce(e1 * TransposedMat(Inverse(M)));
                red2 := reduce(e2 * TransposedMat(Inverse(M)));
                AddSet(A1_perms, PermList([vecidx(red1), vecidx(red2),
                    vecidx([red1[1]+red2[1], red1[2]+red2[2]])]));
            od;
        fi;
        Add(recs, rec(
            K_gens := K_gens,
            x1 := x1, x2 := x2,
            Stab_size := NH_size / Length(orb),
            A1 := Group(Concatenation(A1_perms, [()]))));
    od;
    return rec(d := d,
               n_codim2 := Length(dual2),
               recs := recs);
end;

C2Glue2ProcessJob := function(job)
    local t0, a_s, b_s, ab_s, S_M, src, out, line, deduped, cs, n_lines,
          fact_n, gens, B, N_B, NL, r, b0, contrib, orb_sum, d0,
          first_line, osizes, P, W, P_gens, orb, g, ko, vk, A2, dcs, S3all,
          seen, x, dcset, dc, drep, rimgs, n_codim2_expected, dt, n_skipped,
          A_data, action_mats, tail_dp1, tail_dp2, buf, ln, gi, act;
    t0 := Runtime();

    # X must contain no degree-2 blocks (route guarantees exactly two (2,1)
    # blocks total, both peeled here).
    for dt in job.xsp do
        if dt[1] = 2 then
            Print("RESULT_NA combo=", job.combo,
                  " reason=left_contains_degree2_block\n");
            return;
        fi;
    od;

    # ---- RIGHT cluster: fixed structure on points m+1..m+4 ----
    a_s := (job.m+1, job.m+2);
    b_s := (job.m+3, job.m+4);
    ab_s := a_s * b_s;

    # Precomputed textual tails for the two direct-product lines.
    tail_dp1 := Concatenation(",", String(a_s), ",", String(b_s), "]\n");
    tail_dp2 := Concatenation(",", String(ab_s), "]\n");

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

    # A2 = block swap acting on involution order [a, b, ab]; S3 on 3 points.
    A2 := Group((1,2));
    S3all := Elements(SymmetricGroup(3));

    # Line-range sharding (job.line_lo/line_hi, 1-based inclusive, 0 = open):
    # per-line work is independent, so shard counts are additive and the
    # merge is body-concat + header-sum (run_c2_glue2_path.py --merge).
    # NOTE: P/W come from the first line IN RANGE — consistent across shards
    # because every source line lies in the same block product (checked).
    if not IsBound(job.line_lo) then job.line_lo := 0; fi;
    if not IsBound(job.line_hi) then job.line_hi := 0; fi;
    n_skipped := 0;
    while n_skipped < job.line_lo - 1 do
        line := C2Glue2ReadGenList(src);
        if line = fail then break; fi;
        n_skipped := n_skipped + 1;
    od;

    line := C2Glue2ReadGenList(src);
    while line <> fail do
            if job.line_hi > 0 and n_skipped + n_lines >= job.line_hi then
                break;
            fi;
            gens := EvalString(line);
            B := Group(gens);

            if first_line then
                osizes := SortedList(List(Orbits(B, [1..job.m]), Length));
                if osizes <> SortedList(job.xdeg) then
                    CloseStream(src); CloseStream(out);
                    Print("RESULT_NA combo=", job.combo,
                          " reason=source_orbit_mismatch\n");
                    return;
                fi;
                P_gens := [];
                for orb in Orbits(B, [1..job.m]) do
                    Append(P_gens, Filtered(
                        List(gens, x -> RestrictedPerm(x, orb)),
                        x -> x <> ()));
                od;
                P := Group(P_gens);
                W := Normalizer(S_M, P);
                first_line := false;
            fi;
            if C2GLUE_CHECK then
                for g in gens do
                    if not g in P then
                        Error("c2_glue2: source line ", n_lines + 1,
                              " not inside the block product P");
                    fi;
                od;
            fi;

            N_B := Normalizer(W, B);
            NL := Size(N_B);

            # A = B/Phi and the N_B action matrices, computed ONCE per line
            # and shared by the C2 and V4 kernel enumerations.
            A_data := ElemAbPQuotient(B, 2);
            if A_data.d = 0 then
                act := rec(mats := []);
            else
                act := NHActionOnElemAb(N_B, A_data, 2);
            fi;
            action_mats := act.mats;

            # ---- Q = 1: two direct products (textual emit) ----
            line := Filtered(line, ch -> ch <> ' ' and ch <> '\t');
            ln := Length(line);
            if ln = 0 or line[ln] <> ']' then
                Error("c2_glue2: malformed source line ", n_lines + 1);
            fi;
            buf := Concatenation(line{[1..ln-1]}, tail_dp1);
            Append(buf, Concatenation(line{[1..ln-1]}, tail_dp2));
            deduped := deduped + 2;
            contrib := fact_n / (NL * 8) + fact_n / (NL * 8);
            if not IsInt(contrib) then
                Error("c2_glue2: non-integer class_sum (direct)");
            fi;
            cs := cs + contrib;

            # ---- Q = C2: three classes per kernel orbit ----
            ko := C2Glue2KernelOrbits(B, N_B, gens, A_data, action_mats);
            if C2GLUE_CHECK then
                d0 := ko.d;
                orb_sum := Sum(ko.recs, x -> NL / x.Stab_NH_KH_size);
                if orb_sum <> 2^d0 - 1 then
                    Error("c2_glue2: C2 kernel orbit-sum check failed at ",
                          "source line ", n_lines + 1);
                fi;
            fi;
            for r in ko.recs do
                # b0 = first source gen outside the kernel
                # (g in K <=> coords(g Phi).dual_v = 0).
                b0 := fail;
                for gi in [1..Length(gens)] do
                    if ko.gen_coords[gi] * r.dual_v <> 0 * Z(2) then
                        b0 := gens[gi];
                        break;
                    fi;
                od;
                if b0 = fail then
                    Error("c2_glue2: no generator outside kernel U");
                fi;
                # K_R = <a>-type (swap-orbit {<a>,<b>}; Stab_{D8} = 4)
                Append(buf, C2Glue2GenListString(Concatenation(
                    Filtered(r.K_H_gens, g -> g <> ()),
                    [a_s, b0 * b_s])));
                # K_R = <ab> (swap-fixed; Stab_{D8} = 8)
                Append(buf, C2Glue2GenListString(Concatenation(
                    Filtered(r.K_H_gens, g -> g <> ()),
                    [ab_s, b0 * a_s])));
                # R = Delta, K_R = 1 (Stab_{D8} = 8)
                Append(buf, C2Glue2GenListString(Concatenation(
                    Filtered(r.K_H_gens, g -> g <> ()),
                    [b0 * ab_s])));
                deduped := deduped + 3;
                contrib := fact_n / (r.Stab_NH_KH_size * 4)
                         + fact_n / (r.Stab_NH_KH_size * 8)
                         + fact_n / (r.Stab_NH_KH_size * 8);
                if not IsInt(contrib) then
                    Error("c2_glue2: non-integer class_sum (C2 glue)");
                fi;
                cs := cs + contrib;
            od;

            # ---- Q = V4: double cosets A1\S3/A2 per codim-2 kernel orbit ----
            vk := C2Glue2V4KernelOrbits(B, N_B, A_data, action_mats);
            if C2GLUE_CHECK and vk.d >= 2 then
                orb_sum := Sum(vk.recs, x -> NL / x.Stab_size);
                n_codim2_expected := (2^vk.d - 1) * (2^(vk.d - 1) - 1) / 3;
                if orb_sum <> n_codim2_expected
                   or vk.n_codim2 <> n_codim2_expected then
                    Error("c2_glue2: V4 kernel orbit-sum check failed at ",
                          "source line ", n_lines + 1);
                fi;
            fi;
            rimgs := [a_s, b_s, ab_s];   # involution order [a, b, ab]
            for r in vk.recs do
                # partition S3 into double cosets A1 g A2 (brute force, 6 elts)
                seen := [];
                dcs := [];
                for x in S3all do
                    if not (x in seen) then
                        dcset := Set(List(Cartesian(Elements(r.A1),
                                                    Elements(A2)),
                                          p -> p[1] * x * p[2]));
                        Add(dcs, dcset);
                        UniteSet(seen, dcset);
                    fi;
                od;
                for dc in dcs do
                    drep := dc[1];
                    # fiber gens: K + x1 paired with invol drep(1),
                    #                 x2 paired with invol drep(2)
                    Append(buf, C2Glue2GenListString(Concatenation(
                        Filtered(r.K_gens, g -> g <> ()),
                        [r.x1 * rimgs[1^drep], r.x2 * rimgs[2^drep]])));
                    deduped := deduped + 1;
                    contrib := fact_n * Length(dc) / (r.Stab_size * 8);
                    if not IsInt(contrib) then
                        Error("c2_glue2: non-integer class_sum (V4 glue)");
                    fi;
                    cs := cs + contrib;
                od;
            od;

            # One WriteAll per source line.
            WriteAll(out, buf);
            n_lines := n_lines + 1;
        line := C2Glue2ReadGenList(src);
    od;
    CloseStream(src);
    CloseStream(out);

    if n_lines = 0 then
        Print("RESULT_NA combo=", job.combo, " reason=empty_source\n");
        return;
    fi;

    Print("RESULT combo=", job.combo, " predicted=", deduped,
          " candidates=", deduped, " class_sum=", cs,
          " n_src=", n_lines, " elapsed_ms=", Runtime() - t0, "\n");
end;

for _job in JOBS do
    C2Glue2ProcessJob(_job);
od;

Print("ALL_JOBS_DONE\n");
LogTo();
QUIT;
