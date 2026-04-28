"""Test whether bypassing GAP's random gen search in AllHomomorphismClasses
gives consistent (fast) timing.  If so, we replace the slow randomized
version inside GAH.
"""
import subprocess, os

LOG = "C:/Users/jeffr/Downloads/Lifting/test_fast_allhom.log"
DUMP = "C:/Users/jeffr/Downloads/Lifting/diag_combo6_v3_allcalls.g"

code = r'''
LogTo("__LOG__");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("__DUMP__");

# Custom Hom-class enumeration that bypasses GAP's random gen search.
FastAllHomClasses := function(H, G)
    local cl, gens, bi, params, k;
    if IsCyclic(H) then
        # Cyclic case: fast already in stock GAP.
        return AllHomomorphismClasses(H, G);
    fi;
    if IsSolvableGroup(H) and CanEasilyComputePcgs(H) then
        gens := MinimalGeneratingSet(H);
    else
        gens := SmallGeneratingSet(H);
    fi;
    cl := ConjugacyClasses(G);
    bi := List(gens, i -> Filtered(cl,
                j -> IsInt(Order(i) / Order(Representative(j)))));
    if ForAny(bi, i -> Length(i) = 0) then
        return [];
    fi;
    params := rec(gens := gens, from := H);
    return MorClassLoop(G, bi, params, 9);
end;

# Test on each |Q|=115200 record: stock vs Fast.
big := Filtered(GAH_ALL_CALLS, r -> r.source = "GAH" and r.Q_size = 115200);
Print("[fast] testing on ", Length(big), " |Q|=115200 records\n\n");

stock_times := [];
fast_times := [];
for i in [1..Length(big)] do
    r := big[i];
    Q := Group(r.Q_gens);
    M_bar := Group(r.M_bar_gens);
    SetSize(Q, r.Q_size);
    SetSize(M_bar, r.M_bar_size);
    C := Centralizer(Q, M_bar);

    t0 := Runtime();
    h_stock := AllHomomorphismClasses(C, M_bar);
    t_stock := Runtime() - t0;
    Add(stock_times, t_stock);

    t0 := Runtime();
    h_fast := FastAllHomClasses(C, M_bar);
    t_fast := Runtime() - t0;
    Add(fast_times, t_fast);

    Print("[fast] rec ", i,
          ": stock ", t_stock, "ms (", Length(h_stock), " classes)",
          " | fast ", t_fast, "ms (", Length(h_fast), " classes)\n");
od;

Print("\n[fast] stock total = ", Sum(stock_times), "ms",
      " | fast total = ", Sum(fast_times), "ms\n");
Print("[fast] stock max = ", Maximum(stock_times), "ms",
      " | fast max = ", Maximum(fast_times), "ms\n");
Print("[fast] stock counts = ", List(stock_times, x -> x), "\n");
Print("[fast] fast counts = ", List(fast_times, x -> x), "\n");

LogTo();
QUIT;
'''.replace("__LOG__", LOG).replace("__DUMP__", DUMP)

tmp_path = r"C:\Users\jeffr\Downloads\Lifting\tmp_test_fast_allhom.g"
with open(tmp_path, "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_test_fast_allhom.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print(f"Log: {LOG}")
