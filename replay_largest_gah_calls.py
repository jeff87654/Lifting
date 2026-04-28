"""Replay the N largest-|Q| GAH calls from v3 dump and compare GAH vs NSCR.

Usage:
    python replay_largest_gah_calls.py [N]   # default N=20

Reads diag_combo6_v3_allcalls.g, sorts by |Q| descending, takes top N where
source = 'GAH' (not HBC), runs both methods, reports counts.  This lets us
test the large-Q hypothesis without a full combo re-run.
"""
import subprocess, os, sys

N_TOP = int(sys.argv[1]) if len(sys.argv) > 1 else 20

LOG = "C:/Users/jeffr/Downloads/Lifting/replay_largest.log"
DUMP_ALL = "C:/Users/jeffr/Downloads/Lifting/diag_combo6_v3_allcalls.g"

code = f'''
LogTo("{LOG}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("{DUMP_ALL}");

# Filter to GAH calls only, sort by |Q| descending, take top N.
gah_calls := Filtered(GAH_ALL_CALLS, r -> r.source = "GAH");
SortBy(gah_calls, r -> -r.Q_size);
Print("[replay] total GAH calls dumped: ", Length(GAH_ALL_CALLS), "\\n");
Print("[replay] of which source=GAH: ", Length(gah_calls), "\\n");
Print("[replay] testing top {N_TOP} by |Q|...\\n\\n");

mismatches := [];
for i in [1..Minimum({N_TOP}, Length(gah_calls))] do
    r := gah_calls[i];
    Q := Group(r.Q_gens);
    M_bar := Group(r.M_bar_gens);
    SetSize(Q, r.Q_size);
    SetSize(M_bar, r.M_bar_size);

    # GAH count from the original run is r.gah_count.  Recompute NSCR.
    Print("[", i, "] |Q|=", r.Q_size, " |M_bar|=", r.M_bar_size,
          " |C|=", r.C_size, " idx=", r.idx,
          " GAH=", r.gah_count, " ", StringTime(Runtime()), "\\n");
    t0 := Runtime();
    nscr := NonSolvableComplementClassReps(Q, M_bar);
    Print("    NSCR=", Length(nscr), " (", Runtime()-t0, "ms)");
    if Length(nscr) <> r.gah_count then
        Print("  ! MISMATCH (delta=", Length(nscr) - r.gah_count, ")\\n");
        Add(mismatches, rec(rank := i,
                            Q_size := r.Q_size,
                            M_bar_size := r.M_bar_size,
                            C_size := r.C_size,
                            gah := r.gah_count,
                            nscr := Length(nscr),
                            Q_gens := r.Q_gens,
                            M_bar_gens := r.M_bar_gens,
                            nscr_reps := nscr));
    else
        Print("  ok\\n");
    fi;
od;

Print("\\n=== REPLAY RESULT ===\\n");
Print("[replay] tested ", Minimum({N_TOP}, Length(gah_calls)),
      " largest-|Q| GAH calls\\n");
Print("[replay] mismatches: ", Length(mismatches), "\\n");
for m in mismatches do
    Print("  rank ", m.rank, ": |Q|=", m.Q_size, " GAH=", m.gah,
          " NSCR=", m.nscr, " delta=", m.nscr - m.gah, "\\n");
od;

LogTo();
QUIT;
''';

tmp_path = r"C:\Users\jeffr\Downloads\Lifting\tmp_replay_largest.g"
with open(tmp_path, "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_replay_largest.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print(f"Log: {LOG}")
print(f"Note: only run this AFTER the v3 dumpall diag completes.")
