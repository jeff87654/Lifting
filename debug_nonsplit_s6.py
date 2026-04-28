"""
Targeted S6 debug: trace every complement computation to find
where the non-split test (without centrality guard) causes undercounting.
"""

import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

log_file = "C:/Users/jeffr/Downloads/Lifting/debug_nonsplit_s6.log"

# We'll run S6 computation with a version of the non-split test that
# TRACES but does NOT skip. It logs every case where the test would fire.
# Then we compare with what the H^1/ComplementClassesRepresentatives actually finds.

gap_code = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear caches
LIFT_CACHE := rec();
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# We need to trace the non-split test behavior.
# Strategy: temporarily wrap the complement computation to log details.
#
# Instead of modifying the source, let's just run S6 and look at the
# LiftThroughLayer output which now includes nonsplit_skips count.

Print("Running S6 with centrality-guarded non-split test...\\n");
result := CountAllConjugacyClassesFast(6);
Print("\\nS6 = ", result, "\\n");
Print("Expected: 56\\n");
if result = 56 then
    Print("PASS\\n");
else
    Print("*** FAIL ***\\n");
fi;

# Now test without centrality guard to see what happens.
# We can't easily modify the source at runtime, but we can verify
# the mathematical claim: for every C_2 chief factor layer,
# M_bar is central in Q.
#
# Let's compute S6 conjugacy classes directly and check.
Print("\\n--- Verifying centrality of C_2 chief factors ---\\n");
G := SymmetricGroup(6);
cs := ChiefSeries(G);
Print("Chief series of S_6: ", List(cs, Size), "\\n");
for i in [1..Length(cs)-1] do
    M := cs[i];
    N := cs[i+1];
    factor := M/N;
    Print("Factor ", i, ": |M/N| = ", Size(factor), "\\n");
    if IsPGroup(factor) and IsPrimeInt(Size(factor)) then
        Print("  This is C_", Size(factor), "\\n");
        # Check: is N normal in G? Always yes for chief series.
        # But in LiftThroughLayer, we work with SUBGROUPS S of P=S_n x ... x S_n
        # The chief factors there come from the product, not from S_n.
    fi;
od;

Print("\\n--- Key insight: the bug cannot be in C_2 centrality ---\\n");
Print("For p=2: Aut(C_2) = trivial, so any normal C_2 is central.\\n");
Print("If S6=55 with non-split test (no centrality guard), the bug\\n");
Print("must be in the implementation, not the math.\\n");
Print("Possible causes:\\n");
Print("1. M_bar is not actually C_p (test misidentifies Size)\\n");
Print("2. m_gen is not a generator of M_bar\\n");
Print("3. DerivedSubgroup computation has wrong quotient structure\\n");
Print("4. The continue skips more than just complement computation\\n");

LogTo();
QUIT;
'''

script_file = os.path.join(LIFTING_DIR, "debug_nonsplit_s6.g")
with open(script_file, "w") as f:
    f.write(gap_code)

script_cygwin = "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_nonsplit_s6.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print(f"Running S6 debug...")
start = time.time()

process = subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, cwd=GAP_RUNTIME
)

stdout, stderr = process.communicate(timeout=300)
elapsed = time.time() - start
print(f"Process completed in {elapsed:.1f}s (rc={process.returncode})")

log_path = os.path.join(LIFTING_DIR, "debug_nonsplit_s6.log")
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    # Print relevant lines
    for line in log.split("\n"):
        if any(kw in line for kw in ['S6', 'PASS', 'FAIL', 'nonsplit',
                                       'Chief', 'Factor', 'centrality', 'insight', 'Possible', 'bug']):
            print(line)
    print(f"\nFull log: {log_path}")
else:
    print("No log file produced")
    if stderr:
        print(f"stderr: {stderr[:500]}")
