"""Reproduce the undercount: pick a specific (Q, M_bar) and compare
TFDB-derived complements vs NSCR/CCR ground truth."""
import subprocess, os
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = LIFTING / "debug_tfdb_undercount.log"

gap_commands = f'''
LogTo("{LOG.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");

# Test 1: A5 x A5 with M_bar = first A5
Print("\\n=== Test 1: Q = A5 x A5, M_bar = first A5 ===\\n");
Q := DirectProduct(AlternatingGroup(5), AlternatingGroup(5));
Print("|Q| = ", Size(Q), "\\n");

# Use the Embedding to get the first factor as a subgroup
emb1 := Embedding(Q, 1);
M_bar := Image(emb1);
Print("|M_bar| = ", Size(M_bar), "\\n");
Print("M_bar normal in Q? ", IsNormal(Q, M_bar), "\\n");
idx := Size(Q) / Size(M_bar);
Print("idx = ", idx, "\\n");

# Method 1: ConjugacyClassesSubgroups + filter (TFDB approach)
Print("\\n--- Method 1: ConjugacyClassesSubgroups + filter ---\\n");
t0 := Runtime();
all_subs := List(ConjugacyClassesSubgroups(Q), Representative);
Print("Total subgroup classes: ", Length(all_subs),
      " (", Runtime()-t0, "ms)\\n");

complements_v1 := [];
for H in all_subs do
    if Size(H) = idx and Size(Intersection(H, M_bar)) = 1 then
        Add(complements_v1, H);
    fi;
od;
Print("Complements via filter: ", Length(complements_v1), "\\n");

# Method 2: ComplementClassesRepresentatives (GAP built-in)
Print("\\n--- Method 2: ComplementClassesRepresentatives ---\\n");
t0 := Runtime();
complements_v2 := ComplementClassesRepresentatives(Q, M_bar);
Print("CCR result: ", Length(complements_v2),
      " (", Runtime()-t0, "ms)\\n");

# Method 3: NonSolvableComplementClassReps (Holt's NSCR)
Print("\\n--- Method 3: NonSolvableComplementClassReps ---\\n");
t0 := Runtime();
complements_v3 := NonSolvableComplementClassReps(Q, M_bar);
Print("NSCR result: ", Length(complements_v3),
      " (", Runtime()-t0, "ms)\\n");

# Method 4: HomBasedCentralizerComplements (used by lifting code)
Print("\\n--- Method 4: HomBasedCentralizerComplements ---\\n");
C := Centralizer(Q, M_bar);
Print("|C| = ", Size(C), " (should equal idx if Q is direct product)\\n");
if Size(C) = idx and Size(Intersection(C, M_bar)) = 1 then
    t0 := Runtime();
    complements_v4 := HomBasedCentralizerComplements(C, M_bar);
    Print("HBC result: ", Length(complements_v4),
          " (", Runtime()-t0, "ms)\\n");
else
    Print("HBC not applicable\\n");
fi;

# Method 5: My EnumerateComplementsViaTFDatabase
Print("\\n--- Method 5: EnumerateComplementsViaTFDatabase ---\\n");
t0 := Runtime();
complements_v5 := EnumerateComplementsViaTFDatabase(Q, M_bar);
Print("TFDB result: ", Length(complements_v5),
      " (", Runtime()-t0, "ms)\\n");

# Summary
Print("\\n=== SUMMARY ===\\n");
Print("CCS+filter (M1):  ", Length(complements_v1), "\\n");
Print("CCR (M2):         ", Length(complements_v2), "\\n");
Print("NSCR (M3):        ", Length(complements_v3), "\\n");
if Size(C) = idx and Size(Intersection(C, M_bar)) = 1 then
    Print("HBC (M4):         ", Length(complements_v4), "\\n");
fi;
Print("TFDB (M5):        ", Length(complements_v5), "\\n");

LogTo();
QUIT;
'''

TMP = LIFTING / "temp_debug_tfdb.g"
TMP.write_text(gap_commands)
if LOG.exists():
    LOG.unlink()

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

proc = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_debug_tfdb.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
stdout, stderr = proc.communicate(timeout=300)
print(stdout[-3000:])
if stderr:
    print("\nstderr:")
    print(stderr[-1000:])
