"""Standalone test of HomBasedCentralizerComplements vs
NonSolvableComplementClassReps on small direct products where the answer
can be computed either way.
"""
import subprocess, os

code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/hom_test.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");

# Test cases: Q = M_bar x C, compare HomBased vs NSCR and the theoretical count.

TestCase := function(M_bar_cons, C_cons, expected_comment)
    local M_bar, C, Q, homResult, nscrResult;
    M_bar := M_bar_cons();
    C := C_cons();

    # Build Q = M_bar x C as a direct product permutation group on disjoint points
    Q := DirectProduct(M_bar, C);
    M_bar := Image(Embedding(Q, 1), M_bar);  # M_bar embedded in Q
    C := Image(Embedding(Q, 2), C);          # C embedded in Q

    Print("=== Test: |M_bar|=", Size(M_bar), ", |C|=", Size(C),
          ", |Q|=", Size(Q), " (", expected_comment, ") ===\\n");
    Print("  gcd(|C|, |M_bar|) = ", Gcd(Size(C), Size(M_bar)), "\\n");

    # Verify direct product assumption
    Print("  Size(Intersection(C, M_bar)) = ", Size(Intersection(C, M_bar)), " (want 1)\\n");
    Print("  Size(Centralizer(Q, M_bar)) = ", Size(Centralizer(Q, M_bar)),
          " (want ", Size(C), ")\\n");

    # HomBased
    homResult := HomBasedCentralizerComplements(C, M_bar);
    Print("  HomBased:  ", Length(homResult), " complement classes\\n");

    # NSCR (slow but correct)
    nscrResult := NonSolvableComplementClassReps(Q, M_bar);
    Print("  NSCR:      ", Length(nscrResult), " complement classes\\n");

    if Length(homResult) = Length(nscrResult) then
        Print("  OK (counts match)\\n");
    else
        Print("  !! MISMATCH !!\\n");
    fi;
    Print("\\n");
end;

# Case 1: A_5 x C_3 (gcd=1, unique complement expected)
TestCase(function() return AlternatingGroup(5); end,
         function() return CyclicGroup(IsPermGroup, 3); end,
         "gcd=1 should have 1 complement");

# Case 2: A_5 x C_2 (gcd=2, involutions in A_5 give extra complement)
TestCase(function() return AlternatingGroup(5); end,
         function() return CyclicGroup(IsPermGroup, 2); end,
         "gcd=2");

# Case 3: A_5 x C_4 (gcd=2 with C_4)
TestCase(function() return AlternatingGroup(5); end,
         function() return CyclicGroup(IsPermGroup, 4); end,
         "gcd=4 with C_4");

# Case 4: A_5 x V_4 (Klein 4-group)
TestCase(function() return AlternatingGroup(5); end,
         function()
             local a, b;
             a := (1, 2);
             b := (3, 4);
             return Group([a, b]);
         end,
         "gcd=4 with V_4");

# Case 5: A_6 x C_2 (|M_bar|=360, tests the layer from W501)
TestCase(function() return AlternatingGroup(6); end,
         function() return CyclicGroup(IsPermGroup, 2); end,
         "A_6 x C_2");

# Case 6: A_6 x C_3 (A_6 has C_3 subgroups, non-trivial Hom)
TestCase(function() return AlternatingGroup(6); end,
         function() return CyclicGroup(IsPermGroup, 3); end,
         "A_6 x C_3");

LogTo();
QUIT;
'''
with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_test_hom.g", "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_test_hom.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
try:
    p.communicate(timeout=600)
except subprocess.TimeoutExpired:
    p.kill(); p.communicate()

log = open(r"C:\Users\jeffr\Downloads\Lifting\hom_test.log").read()
# Show just the test output (skip syntax warnings)
in_test = False
for line in log.splitlines():
    if "=== Test:" in line:
        in_test = True
    if in_test:
        print(line)
