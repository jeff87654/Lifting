"""Diagnostic v2: re-run W506 combo 6 with BOTH GAH and HBC instrumented.

The first diag run (PID 8496/16464) only had the GAH hook; this one has the
HBC hook too.  Bumps MAX_Q to 250K to cover the larger parents at layers 7-8.
"""
import subprocess, os

LOG = "C:/Users/jeffr/Downloads/Lifting/diag_combo6_v2.log"
DUMP = "C:/Users/jeffr/Downloads/Lifting/diag_combo6_v2_diffs.g"
MAX_Q = 250000

code = f'''
LogTo("{LOG}");

USE_GENERAL_AUT_HOM := false;
DIAG_GAH_VS_NSCR := true;
DIAG_GAH_MAX_Q_SIZE := {MAX_Q};
DIAG_GAH_DUMP_FILE := "{DUMP}";

PrintTo("{DUMP}", "DIAG_GAH_DIFFERS_LOADED := [];\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n[diag-v2] USE_GENERAL_AUT_HOM = ", USE_GENERAL_AUT_HOM,
      " (matches W506)\\n");
Print("[diag-v2] DIAG_GAH_VS_NSCR = ", DIAG_GAH_VS_NSCR,
      " (cap |Q| <= ", DIAG_GAH_MAX_Q_SIZE, ")\\n\\n");

T5 := TransitiveGroup(5, 5);;
T2 := TransitiveGroup(2, 1);;
partition := [5, 5, 2, 2, 2, 2];;
factors := [T5, T5, T2, T2, T2, T2];;

shifted := [];
offsets := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offsets, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
N := BuildPerComboNormalizer(partition, factors, 18);

FPF_SUBDIRECT_CACHE := rec();

Print("[diag-v2] |P|=", Size(P), " |N|=", Size(N), "\\n");
Print("[diag-v2] starting FindFPFClassesByLifting...\\n\\n");

t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

Print("\\n=== RESULT ===\\n");
Print("[diag-v2] Raw FPF: ", Length(fpf), "\\n");
Print("[diag-v2] DIAG_GAH_DIFFERS records: ", Length(DIAG_GAH_DIFFERS), "\\n");
Print("[diag-v2] Elapsed: ", Float(elapsed/1000), "s\\n");

LogTo();
QUIT;
''';

tmp_path = r"C:\Users\jeffr\Downloads\Lifting\tmp_diag_combo6_v2.g"
with open(tmp_path, "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_diag_combo6_v2.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print(f"Log: {LOG}")
print(f"Diff dump: {DUMP}")
