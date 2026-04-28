LogTo("C:/Users/jeffr/Downloads/Lifting/test_gq_perf_real.log");
Print("=== GQ-per-Q-type vs NormalSubgroups perf comparison ===\n\n");

# Q-types we care about for S18+S19+S20 builds
Q_C2 := CyclicGroup(IsPermGroup, 2);
Q_C3 := CyclicGroup(IsPermGroup, 3);
Q_S3 := SymmetricGroup(3);
Q_V4 := DirectProduct(CyclicGroup(IsPermGroup, 2), CyclicGroup(IsPermGroup, 2));
Q_C4 := CyclicGroup(IsPermGroup, 4);
Q_D8 := TransitiveGroup(4, 3);
Q_A4 := AlternatingGroup(4);
Q_S4 := SymmetricGroup(4);

# Pretend we are building for S20 (M_R=4): need all S_4 quotients
Q_TYPES := [Q_C2, Q_C3, Q_V4, Q_C4, Q_D8, Q_A4, Q_S4];

TotGQ := 0;  TotNS := 0;  TotH := 0;
NS_skipped := 0;  HuiltCorrupt := 0;

TimeOneH := function(H, ns_cap_ms)
    local t, gqs, kers, gq_total, gq_kers_total, ns, ns_time, q;
    gq_total := 0;
    gq_kers_total := 0;
    for q in Q_TYPES do
        t := Runtime();
        gqs := GQuotients(H, q);
        kers := Set(List(gqs, Kernel));
        gq_total := gq_total + (Runtime() - t);
        gq_kers_total := gq_kers_total + Length(kers);
    od;
    if Size(H) > 8000 then
        return rec(gq_ms := gq_total, gq_kers := gq_kers_total,
                   ns_ms := -1, ns_count := -1);
    fi;
    t := Runtime();
    ns := NormalSubgroups(H);
    ns_time := Runtime() - t;
    return rec(gq_ms := gq_total, gq_kers := gq_kers_total,
               ns_ms := ns_time, ns_count := Length(ns));
end;


Print("\n=== AGGREGATE ===\n");
Print("Total H:           ", TotH, "\n");
Print("Total GQ time (s): ", Float(TotGQ/1000.0), "\n");
Print("Total NS time (s): ", Float(TotNS/1000.0), "\n");
Print("NS skipped:        ", NS_skipped, "\n");
if TotGQ > 0 then
    Print("Avg GQ per H (ms): ", Float(TotGQ/TotH), "\n");
fi;
if TotNS > 0 then
    Print("Avg NS per H (ms): ", Float(TotNS / (TotH - NS_skipped)), "\n");
fi;
LogTo();
QUIT;
