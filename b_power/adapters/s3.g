# b_power/adapters/s3.g — pure S_3^k enumeration.
#
# Cross-characteristic: S_3 = C_3 ⋊ C_2 has an F_3 module layer and an F_2
# sign layer linked by the semidirect action.  Enumeration kernel is
# B2G3_SD_EnumerateClusterS3Fast (in b_2group_adapters/_semidirect_engine.g);
# materializer body copied from B2G3_CC_S3_MaterializeK2 (b_2group_v3_cross.g)
# so this file has no dependency on the heavy v3_cross / tower / fold stack.

# Materialize an S_3-cluster K from its orbit record.  Q is the F_2 sign
# subspace; M_F3_tuple is the per-class F_3 RREF tuple; info groups blocks by
# Q-character class.  Q-basis rows lift to per-block transpositions (1,2);
# F_3-module rows lift to per-block 3-cycles (1,2,3) (element 1) or (1,3,2)
# (element 2 = -1).  3*k point support [1..3k].
B2GPower_S3_Materialize := function(orbit, k)
    local F2, F3, gens, j, shift, gen_p, v, class_idx, row, full_row,
          block_pos, a_int, mod_basis, info;
    F2 := GF(2);
    F3 := GF(3);
    info := orbit.info;
    mod_basis := [];
    for class_idx in [1..Length(info.classes)] do
        for row in orbit.M_F3_tuple[class_idx] do
            full_row := ListWithIdenticalEntries(k, Zero(F3));
            for j in [1..Length(info.classes[class_idx])] do
                block_pos := info.classes[class_idx][j];
                full_row[block_pos] := row[j];
            od;
            Add(mod_basis, full_row);
        od;
    od;
    gens := [];
    if Dimension(orbit.Q) > 0 then
        for v in AsList(Basis(orbit.Q)) do
            gen_p := ();
            for j in [1..k] do
                if v[j] = One(F2) then
                    shift := MappingPermListList([1..3],
                                                 [3*(j-1)+1..3*j]);
                    gen_p := gen_p * ((1, 2) ^ shift);
                fi;
            od;
            Add(gens, gen_p);
        od;
    fi;
    for v in mod_basis do
        gen_p := ();
        for j in [1..k] do
            a_int := IntFFE(v[j]);
            if a_int <> 0 then
                shift := MappingPermListList([1..3],
                                             [3*(j-1)+1..3*j]);
                if a_int = 1 then
                    gen_p := gen_p * ((1, 2, 3) ^ shift);
                else
                    gen_p := gen_p * ((1, 3, 2) ^ shift);
                fi;
            fi;
        od;
        Add(gens, gen_p);
    od;
    if Length(gens) = 0 then return Group(()); fi;
    return Subgroup(SymmetricGroup(3 * k), gens);
end;

B2GPower_S3_Count := function(k)
    return Length(B2G3_SD_EnumerateClusterS3Fast(k));
end;

B2GPower_S3_Emit := function(k, out_path)
    local orbits, fout, t0, total, orbit, K, gens, t_hb, write_idx;
    t0 := Runtime();
    orbits := B2G3_SD_EnumerateClusterS3Fast(k);
    total := Length(orbits);
    fout := B2GPower_OpenOutput(out_path);
    B2GPower_WriteHeader(fout, 3, 2, k, total, Runtime() - t0);
    t_hb := Runtime();
    for write_idx in [1..total] do
        orbit := orbits[write_idx];
        K := B2GPower_S3_Materialize(orbit, k);
        gens := GeneratorsOfGroup(K);
        PrintTo(fout, B2GPower_FormatGenList(gens), "\n");
        if Runtime() - t_hb >= 30000 or write_idx = total then
            Print("[b_power:S3] materialized ", write_idx, "/", total,
                  " (elapsed_ms=", Runtime() - t0, ")\n");
            t_hb := Runtime();
        fi;
    od;
    CloseStream(fout);
    return total;
end;

B2G_POWER_ADAPTERS.("3_2") := rec(
    key := "3_2",
    name := "S3",
    d := 3,
    t := 2,
    Count := B2GPower_S3_Count,
    Emit := B2GPower_S3_Emit
);
