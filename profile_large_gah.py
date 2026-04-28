"""Profile GAH on the large-Q calls (|Q|=115200) from v3 dump.  Identifies
where time is spent: AllHomomorphismClasses, validTaus loop, K-build,
cross-hom dedup.
"""
import subprocess, os

LOG = "C:/Users/jeffr/Downloads/Lifting/profile_large_gah.log"
DUMP = "C:/Users/jeffr/Downloads/Lifting/diag_combo6_v3_allcalls.g"

code = r'''
LogTo("__LOG__");

USE_GENERAL_AUT_HOM := true;
GENERAL_AUT_HOM_VERBOSE := true;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("__DUMP__");

# Time each |Q|=115200 record's GAH and AllHomomorphismClasses to find slow ones.
big := Filtered(GAH_ALL_CALLS, r -> r.source = "GAH" and r.Q_size = 115200);
Print("[prof] ", Length(big), " records with |Q|=115200\n\n");

# Time AllHomomorphismClasses on each (cheap part) and full GAH on first 5.
# (Doing full GAH on all is too slow.)
for i in [1..Length(big)] do
    r := big[i];
    Q := Group(r.Q_gens);
    M_bar := Group(r.M_bar_gens);
    SetSize(Q, r.Q_size);
    SetSize(M_bar, r.M_bar_size);
    t0 := Runtime();
    C := Centralizer(Q, M_bar);
    t_C := Runtime() - t0;
    t0 := Runtime();
    homs := AllHomomorphismClasses(C, M_bar);
    t_homs := Runtime() - t0;
    Print("[prof] rec ", i, ": |C|=", Size(C),
          " |gensC|=", Length(GeneratorsOfGroup(C)),
          " gah_count=", r.gah_count,
          " | Centralizer ", t_C, "ms",
          " | AllHomClass ", t_homs, "ms (", Length(homs), " classes)\n");
od;

# Now run full GAH on the slowest AllHomClass case.
Print("\n[prof] === Full GAH on slowest case ===\n");
slowest := big[1];
slowest_t := 0;
for i in [1..Length(big)] do
    r := big[i];
    Q := Group(r.Q_gens);
    M_bar := Group(r.M_bar_gens);
    SetSize(Q, r.Q_size);
    SetSize(M_bar, r.M_bar_size);
    C := Centralizer(Q, M_bar);
    t0 := Runtime();
    homs := AllHomomorphismClasses(C, M_bar);
    t := Runtime() - t0;
    if t > slowest_t then
        slowest := r;
        slowest_t := t;
    fi;
od;
Print("[prof] slowest AllHomClass: |C|=", slowest.C_size,
      " gah_count=", slowest.gah_count, " AllHomClass=", slowest_t, "ms\n");

GENERAL_AUT_HOM_VERBOSE := true;
Q := Group(slowest.Q_gens);
M_bar := Group(slowest.M_bar_gens);
SetSize(Q, slowest.Q_size);
SetSize(M_bar, slowest.M_bar_size);
C := Centralizer(Q, M_bar);

t0 := Runtime();
result := GeneralAutHomComplements(Q, M_bar, C);
Print("[prof] full GAH on slowest: ", Length(result), " complements in ",
      Runtime()-t0, "ms\n");

LogTo();
QUIT;
'''.replace("__LOG__", LOG).replace("__DUMP__", DUMP)

tmp_path = r"C:\Users\jeffr\Downloads\Lifting\tmp_profile_large.g"
with open(tmp_path, "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_profile_large.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print(f"Log: {LOG}")
