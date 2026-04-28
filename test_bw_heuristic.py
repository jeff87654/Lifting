"""Test: pre-compute the AllHomomorphismClasses search-space estimate (bw)
and see if it correlates with measured time.  If yes, we can skip GAH
when bw is large.
"""
import subprocess, os

LOG = "C:/Users/jeffr/Downloads/Lifting/test_bw_heuristic.log"
DUMP = "C:/Users/jeffr/Downloads/Lifting/diag_combo6_v3_allcalls.g"

code = r'''
LogTo("__LOG__");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("__DUMP__");

# Compute bw estimate (the search-space size GAP would use).
EstimateBw := function(C, M_bar)
    local gens, cl_M, bw;
    if IsSolvableGroup(C) and CanEasilyComputePcgs(C) then
        gens := MinimalGeneratingSet(C);
    else
        gens := SmallGeneratingSet(C);
    fi;
    cl_M := ConjugacyClasses(M_bar);
    bw := Product(List(gens,
            g -> Sum(Filtered(cl_M,
                    j -> IsInt(Order(g) / Order(Representative(j)))),
                Size)));
    return bw;
end;

big := Filtered(GAH_ALL_CALLS, r -> r.source = "GAH" and r.Q_size = 115200);
Print("[bw] testing on ", Length(big), " |Q|=115200 records\n\n");

for i in [1..Length(big)] do
    r := big[i];
    Q := Group(r.Q_gens);
    M_bar := Group(r.M_bar_gens);
    SetSize(Q, r.Q_size);
    SetSize(M_bar, r.M_bar_size);
    C := Centralizer(Q, M_bar);

    bw := EstimateBw(C, M_bar);
    t0 := Runtime();
    h := AllHomomorphismClasses(C, M_bar);
    t := Runtime() - t0;
    Print("[bw] rec ", i, ": |C|=", Size(C),
          " gens orders = ", List(GeneratorsOfGroup(C), Order),
          " | bw = ", bw,
          " | AllHomClass = ", t, "ms (", Length(h), " classes)\n");
od;

LogTo();
QUIT;
'''.replace("__LOG__", LOG).replace("__DUMP__", DUMP)

tmp_path = r"C:\Users\jeffr\Downloads\Lifting\tmp_test_bw.g"
with open(tmp_path, "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_test_bw.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print(f"Log: {LOG}")
