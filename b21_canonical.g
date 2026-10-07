################################################################################
# b21_canonical.g
#
# nauty-style canonical labeling for the colored line-hypergraph
# H_M = (V, M, L) where V = F_2^d \ {0}, M is the vertex coloring, L is the
# set of "lines" {v, w, v XOR w}. Aut(H_M) is precisely the GL_d-stabilizer of M.
#
# Canonical labeling is the lex-min over the search tree of leaves of:
#   - vertex color sequence (M-values in canonical label order)
#   - edge set (lines {v, w, v+w} mapped to label-triples and sorted)
#
# Two M's are GL_d-equivalent iff their canonical labelings agree on BOTH.
################################################################################

BitXor := function(a, b)
    local r, p;
    r := 0; p := 1;
    while a > 0 or b > 0 do
        if (a mod 2) <> (b mod 2) then r := r + p; fi;
        a := QuoInt(a, 2); b := QuoInt(b, 2);
        p := 2 * p;
    od;
    return r;
end;

EncodingOf := function(v)
    local i, s;
    s := 0;
    for i in [1..Length(v)] do
        if not IsZero(v[i]) then s := s + 2^(i-1); fi;
    od;
    return s;
end;

DecodingOf := function(enc, d)
    local v, i, e;
    v := []; e := enc;
    for i in [1..d] do
        if (e mod 2) = 1 then Add(v, One(GF(2))); else Add(v, Zero(GF(2))); fi;
        e := QuoInt(e, 2);
    od;
    return v;
end;

# Cache lines of PG(d-1, 2): unordered triples {v_1, v_2, v_1 XOR v_2}.
LINES_CACHE := rec();
GetLines := function(d)
    local key, n, lines, v1, v2, v3;
    key := String(d);
    if IsBound(LINES_CACHE.(key)) then return LINES_CACHE.(key); fi;
    n := 2^d - 1;
    lines := [];
    for v1 in [1..n] do
        for v2 in [v1+1..n] do
            v3 := BitXor(v1, v2);
            if v3 > v2 then Add(lines, [v1, v2, v3]); fi;
        od;
    od;
    LINES_CACHE.(key) := lines;
    return lines;
end;

# 1-WL color refinement using triangle (line) structure:
# sig(v) = (color(v), sorted multiset of (color(w), color(v XOR w)) for w != v).
ColorRefine := function(color, d)
    local n, V, sigs, v, w, vw, sorted_sigs, new_color;
    n := 2^d - 1;
    V := [1..n];
    repeat
        sigs := [];
        for v in V do
            sigs[v] := [color[v], []];
            for w in V do
                if w = v then continue; fi;
                vw := BitXor(v, w);
                Add(sigs[v][2], [color[w], color[vw]]);
            od;
            Sort(sigs[v][2]);
        od;
        sorted_sigs := SortedList(Set(sigs));
        new_color := List(V, v -> PositionSorted(sorted_sigs, sigs[v]));
        if new_color = color then break; fi;
        color := new_color;
    until false;
    return color;
end;

IsDiscreteColoring := function(color)
    return Length(color) = Length(Set(color));
end;

# Canonical readoff: vertex color sequence + edge set in canonical labels.
ReadOffCanonical := function(M, color, d)
    local n, pi_inv, j, vertex_seq, edge_set, lines, line;
    n := Length(M);
    pi_inv := ListWithIdenticalEntries(n, 0);
    for j in [1..n] do pi_inv[color[j]] := j; od;
    vertex_seq := List([1..n], j -> M[pi_inv[j]]);
    lines := GetLines(d);
    edge_set := List(lines, line ->
        SortedList([color[line[1]], color[line[2]], color[line[3]]]));
    Sort(edge_set);
    return [vertex_seq, edge_set];
end;

# Find smallest non-singleton cell. Tie-break by smallest cell color
# (which is GL_d-invariant after refinement). Returns rec(color, vertices).
FindBranchingCell := function(color)
    local byColor, k, c, bestColor, bestSize, currentCell, intColor, c_int;
    byColor := rec();
    for k in [1..Length(color)] do
        c := String(color[k]);
        if not IsBound(byColor.(c)) then byColor.(c) := []; fi;
        Add(byColor.(c), k);
    od;
    bestColor := fail;
    bestSize := infinity;
    for c in RecNames(byColor) do
        currentCell := byColor.(c);
        c_int := Int(c);
        if Length(currentCell) >= 2 then
            if Length(currentCell) < bestSize
                or (Length(currentCell) = bestSize and c_int < bestColor)
            then
                bestColor := c_int;
                bestSize := Length(currentCell);
            fi;
        fi;
    od;
    if bestColor = fail then return fail; fi;
    return byColor.(String(bestColor));
end;

# Recursive nauty-style canonical search.
NautySearch := function(M, d, color, best)
    local cell, v, color_ind, color_refined, key;
    if IsDiscreteColoring(color) then
        key := ReadOffCanonical(M, color, d);
        if best.value = fail or key < best.value then
            best.value := key;
        fi;
        return;
    fi;
    cell := FindBranchingCell(color);
    for v in cell do
        color_ind := ShallowCopy(color);
        color_ind[v] := Maximum(color) + 1;
        color_refined := ColorRefine(color_ind, d);
        NautySearch(M, d, color_refined, best);
    od;
end;

# Top-level: lex-min canonical (vertex_seq, edge_set) over leaves.
NautyCanonicalForm := function(M, d)
    local color, best;
    color := ColorRefine(ShallowCopy(M), d);
    best := rec(value := fail);
    NautySearch(M, d, color, best);
    return best.value;
end;
