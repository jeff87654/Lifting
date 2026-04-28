"""Timing comparison: HomBased vs NSCR on cases matching W501's scale.
W501's log showed NSCR taking 357s for |Q|=933120, |M_bar|=360, |C|=2592.
Let's see how HomBased does on the same (C, M_bar) shapes."""
import subprocess, os

code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/hom_timing.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");

# Construct M_bar = A_6 and various large C to test scaling.
TestTiming := function(M_bar_cons, C_cons, comment)
    local M_bar, C, Q, t0, homResult, t_hom, nscrResult, t_nscr;
    M_bar := M_bar_cons();
    C := C_cons();
    Q := DirectProduct(M_bar, C);
    M_bar := Image(Embedding(Q, 1), M_bar);
    C := Image(Embedding(Q, 2), C);

    Print("=== ", comment, " ===\\n");
    Print("  |M_bar|=", Size(M_bar), ", |C|=", Size(C), ", |Q|=", Size(Q), "\\n");

    # HomBased timing
    t0 := Runtime();
    homResult := HomBasedCentralizerComplements(C, M_bar);
    t_hom := Runtime() - t0;
    Print("  HomBased: ", Length(homResult), " complements in ", t_hom, "ms\\n");

    # NSCR timing (skip if too big to finish)
    if Size(Q) <= 200000 then
        t0 := Runtime();
        nscrResult := NonSolvableComplementClassReps(Q, M_bar);
        t_nscr := Runtime() - t0;
        Print("  NSCR:     ", Length(nscrResult), " complements in ", t_nscr, "ms\\n");
        if t_hom > 0 then
            Print("  Speedup:  ", Float(t_nscr / Maximum(1, t_hom)), "x\\n");
        fi;
        if Length(homResult) = Length(nscrResult) then
            Print("  OK\\n");
        else
            Print("  MISMATCH\\n");
        fi;
    else
        Print("  NSCR:     SKIPPED (|Q| too big, would take many minutes)\\n");
    fi;
    Print("\\n");
end;

# Case 1: A_6 x C_6
TestTiming(function() return AlternatingGroup(6); end,
           function() return CyclicGroup(IsPermGroup, 6); end,
           "A_6 x C_6");

# Case 2: A_6 x (C_2 x C_2)
TestTiming(function() return AlternatingGroup(6); end,
           function()
             local a, b;
             a := (1, 2);
             b := (3, 4);
             return Group([a, b]);
           end,
           "A_6 x V_4");

# Case 3: A_6 x S_4 (C has more structure)
TestTiming(function() return AlternatingGroup(6); end,
           function() return SymmetricGroup(4); end,
           "A_6 x S_4");

# Case 4: A_8 x C_2 (larger M_bar)
TestTiming(function() return AlternatingGroup(8); end,
           function() return CyclicGroup(IsPermGroup, 2); end,
           "A_8 x C_2 (very large |Q|, NSCR skipped)");

# Case 5: A_6 x (C_3 x S_3) closer to 2592-size
TestTiming(function() return AlternatingGroup(6); end,
           function() return DirectProduct(CyclicGroup(IsPermGroup, 3),
                                            SymmetricGroup(4)); end,
           "A_6 x (C_3 x S_4), |C|=72");

LogTo();
QUIT;
'''
with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_test_timing.g", "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_test_timing.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
try:
    p.communicate(timeout=900)
except subprocess.TimeoutExpired:
    p.kill(); p.communicate()

log = open(r"C:\Users\jeffr\Downloads\Lifting\hom_timing.log").read()
# Print test output only
in_test = False
for line in log.splitlines():
    if "=== " in line:
        in_test = True
    if in_test:
        print(line)
