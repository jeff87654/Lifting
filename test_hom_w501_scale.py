"""Measure HomBasedCentralizerComplements on groups matching the structure
W501 is hitting: M_bar = A_6, |C| ∈ {648, 2592}.

Since the method's cost only depends on (C, M_bar), not Q, we can just
build a C of the right size and time the call.
"""
import subprocess, os

code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/hom_w501.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");

M_bar := AlternatingGroup(6);
Print("M_bar = A_6, |M_bar| = 360\\n\\n");

# Try several groups of size 648 and 2592 (the two sizes W501 encountered).
TestOneC := function(C, comment)
    local t0, homClasses, t;
    Print("--- ", comment, " ---\\n");
    Print("  |C| = ", Size(C), "\\n");
    Print("  structure: ", StructureDescription(C), "\\n");
    Print("  gcd(|C|, 360) = ", Gcd(Size(C), 360), "\\n");

    # Just time the Hom enumeration (the dominant cost).
    # Building complements in a real Q is negligible on top.
    t0 := Runtime();
    homClasses := AllHomomorphismClasses(C, M_bar);
    t := Runtime() - t0;
    Print("  Hom classes: ", Length(homClasses), "\\n");
    Print("  AllHomomorphismClasses time: ", t, " ms\\n\\n");
end;

# Size 648 groups (same size as W501's first centralizer-case parent)
# Pick several different structures to sample.
TestOneC(SmallGroup(648, 1), "SmallGroup(648, 1)");
TestOneC(SmallGroup(648, 100), "SmallGroup(648, 100)");
TestOneC(SmallGroup(648, 500), "SmallGroup(648, 500)");
TestOneC(SmallGroup(648, 700), "SmallGroup(648, 700)");

# Size 2592 groups (same size as W501's |C|=2592 case with |Q|=933K)
TestOneC(SmallGroup(2592, 1), "SmallGroup(2592, 1)");
TestOneC(SmallGroup(2592, 500), "SmallGroup(2592, 500)");
TestOneC(SmallGroup(2592, 1000), "SmallGroup(2592, 1000)");
TestOneC(SmallGroup(2592, 1700), "SmallGroup(2592, 1700)");

LogTo();
QUIT;
'''
with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_w501_scale.g", "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_w501_scale.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
try:
    p.communicate(timeout=900)
except subprocess.TimeoutExpired:
    p.kill(); p.communicate()

log = open(r"C:\Users\jeffr\Downloads\Lifting\hom_w501.log").read()
started = False
for line in log.splitlines():
    if "M_bar = A_6" in line:
        started = True
    if started:
        print(line)
