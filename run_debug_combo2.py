"""
Debug: run ONE specific combo with and without orbital, compare lift results.

Combo: [3,2], [6,5], [6,8] from partition [6,6,3] of S15
Expected: orbital = 17 candidates, no-orbital = 26 candidates
After dedup: orbital = 13, no-orbital = 14

This script runs FindFPFClassesByLifting directly on this combo,
both with orbital on and off, then compares the results under N-conjugacy.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/debug_combo2.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n=== Debug combo [3,2], [6,5], [6,8] ===\\n\\n");

# Build the specific combo
T63_2 := TransitiveGroup(3, 2);  # S_3
T66_5 := TransitiveGroup(6, 5);
T66_8 := TransitiveGroup(6, 8);

# Factors in order: [6,5], [6,8], [3,2] (sorted by decreasing size)
factors := [T66_5, T66_8, T63_2];
partition := [6, 6, 3];

# Shift groups
shifted := [];
offs := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("|P| = ", Size(P), "\\n");
Print("factors: ", List(factors, f -> [NrMovedPoints(f), TransitiveIdentification(f)]), "\\n\\n");

# Build N (partition normalizer) for dedup comparison
N := BuildConjugacyTestGroup(15, [6, 6, 3]);
Print("|N| = ", Size(N), "\\n\\n");

# Run WITH orbital
Print("=== Run 1: orbital ON ===\\n");
USE_H1_ORBITAL := true;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
ResetH1TimingStats();

result_orb := FindFPFClassesByLifting(P, shifted, offs, N);
Print("Orbital result: ", Length(result_orb), " FPF subdirects\\n\\n");

# Run WITHOUT orbital
Print("=== Run 2: orbital OFF ===\\n");
USE_H1_ORBITAL := false;
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
ClearH1Cache();
ResetH1TimingStats();

result_no_orb := FindFPFClassesByLifting(P, shifted, offs, N);
Print("No-orbital result: ", Length(result_no_orb), " FPF subdirects\\n\\n");

Print("Difference: ", Length(result_no_orb) - Length(result_orb), "\\n\\n");

# Now compare the results modulo N-conjugacy
Print("=== Comparing under N-conjugacy ===\\n");

# Check: are orbital results a subset of no-orbital results (modulo N)?
Print("\\nChecking if every orbital result is N-conjugate to some no-orbital result...\\n");
for i in [1..Length(result_orb)] do
    found := false;
    for j in [1..Length(result_no_orb)] do
        if RepresentativeAction(N, result_orb[i], result_no_orb[j]) <> fail then
            found := true;
            break;
        fi;
    od;
    if not found then
        Print("  orb[", i, "] NOT found in no_orb! |orb[", i, "]| = ", Size(result_orb[i]), "\\n");
    fi;
od;
Print("Done.\\n");

Print("\\nChecking if every no-orbital result is N-conjugate to some orbital result...\\n");
missing := [];
for i in [1..Length(result_no_orb)] do
    found := false;
    for j in [1..Length(result_orb)] do
        if RepresentativeAction(N, result_no_orb[i], result_orb[j]) <> fail then
            found := true;
            break;
        fi;
    od;
    if not found then
        Print("  no_orb[", i, "] NOT found in orb! |no_orb[", i, "]| = ", Size(result_no_orb[i]), "\\n");
        Add(missing, i);
    fi;
od;
Print("Done. ", Length(missing), " missing.\\n\\n");

# Count N-equivalence classes in each set
Print("=== Counting N-equivalence classes ===\\n");

DedupUnderN := function(results, N)
    local reps, H, found, i;
    reps := [];
    for H in results do
        found := false;
        for i in [1..Length(reps)] do
            if RepresentativeAction(N, H, reps[i]) <> fail then
                found := true;
                break;
            fi;
        od;
        if not found then
            Add(reps, H);
        fi;
    od;
    return reps;
end;

Print("Deduping orbital results under N...\\n");
orb_dedup := DedupUnderN(result_orb, N);
Print("  ", Length(result_orb), " -> ", Length(orb_dedup), " classes\\n");

Print("Deduping no-orbital results under N...\\n");
no_orb_dedup := DedupUnderN(result_no_orb, N);
Print("  ", Length(result_no_orb), " -> ", Length(no_orb_dedup), " classes\\n");

Print("\\nN-class counts: orbital=", Length(orb_dedup), " no_orbital=", Length(no_orb_dedup), "\\n");
Print("Expected from per-combo comparison: orbital=13 no_orbital=14\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_debug_combo2.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_debug_combo2.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting at {time.strftime('%H:%M:%S')}")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    env=env, cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=7200)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")
if stderr:
    print(f"STDERR: {stderr[:500]}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()

    # Print key sections
    print("\\n=== KEY RESULTS ===")
    for line in log.split('\\n'):
        if any(kw in line for kw in ['result:', 'NOT found', 'missing', 'classes',
                                      'Difference', 'N-class', 'Expected']):
            print(line.strip())

    print(f"\\nLog: {len(log)} chars")
    print("\\n=== LAST 2000 CHARS ===")
    print(log[-2000:])
except FileNotFoundError:
    print("Log file not found!")
