LogTo("C:/Users/jeffr/Downloads/Lifting/bench_s17_origins.log");
SetInfoLevel(InfoWarning, 0);
Read("C:/Users/jeffr/Downloads/Lifting/_load_s17.g");
Print("Loaded ", Length(ALL), " groups\n");

OriginOf := function(gens)
    local H, orbs, sortedOrbs, partition, factors, o, len, action, ti;
    if Length(gens) = 0 or ForAll(gens, IsOne) then
        return [List([1..18], i -> 1), List([1..18], i -> [1, 1])];
    fi;
    H := Group(gens);
    orbs := Orbits(H, [1..18]);
    sortedOrbs := ShallowCopy(orbs);
    Sort(sortedOrbs, function(a, b)
        if Length(a) <> Length(b) then return Length(a) > Length(b); fi;
        return Minimum(a) < Minimum(b);
    end);
    partition := List(sortedOrbs, Length);
    factors := [];
    for o in sortedOrbs do
        len := Length(o);
        if len = 1 then Add(factors, [1, 1]);
        elif len = 2 then Add(factors, [2, 1]);
        else
            action := Action(H, o);
            Add(factors, [len, TransitiveIdentification(action)]);
        fi;
    od;
    return [partition, factors];
end;

# Benchmark: process N samples spread across the file
N := 1000;
step := QuoInt(Length(ALL), N);
t0 := Runtime();
for i in [1..N] do
    idx := 1 + (i-1) * step;
    if idx > Length(ALL) then idx := Length(ALL); fi;
    res := OriginOf(ALL[idx]);
od;
elapsed := (Runtime() - t0) / 1000.0;
Print("Processed ", N, " spread samples in ", elapsed, "s\n");
Print("Avg ", elapsed*1000.0/N, " ms/group\n");
Print("Estimated total time: ", Int(Length(ALL) * elapsed / N), "s = ",
      Length(ALL) * elapsed / N / 60.0, " min\n");

LogTo();
QUIT;
