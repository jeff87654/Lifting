# b_power/power_utils_emit.g
#
# Output helpers shared across pure-power adapters.  Produces the legacy
# combo-file format read by runner/route.py and predict_full_general_wreath:
#
#   # combo: [ [ d, t ], [ d, t ], ... ]
#   # candidates: N
#   # deduped: N
#   # elapsed_ms: M
#   [gen1,gen2,...]
#   ...
#
# Generator format is GAP cycle notation, joined by commas, wrapped in [].

B2GPower_FormatGenList := function(gens)
    return Concatenation("[",
        JoinStringsWithSeparator(List(gens, g -> String(g)), ","),
        "]");
end;

B2GPower_OpenOutput := function(path)
    local fout;
    fout := OutputTextFile(path, false);
    SetPrintFormattingStatus(fout, false);
    return fout;
end;

B2GPower_WriteHeader := function(fout, d, t, k, total, elapsed_ms)
    local combo_pairs;
    combo_pairs := List([1..k], i -> [d, t]);
    PrintTo(fout, "# combo: ", combo_pairs, "\n");
    PrintTo(fout, "# candidates: ", total, "\n");
    PrintTo(fout, "# deduped: ", total, "\n");
    PrintTo(fout, "# elapsed_ms: ", elapsed_ms, "\n");
end;
