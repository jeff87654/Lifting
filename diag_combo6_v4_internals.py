"""Diagnostic v4: re-run combo 6 with GAH internals captured at each
mismatch.  Now records homClasses count, raw_count, dedup_count, and the
generators of C as seen at the mismatch — so we can compare context behavior
to isolation.
"""
import subprocess, os

LOG = "C:/Users/jeffr/Downloads/Lifting/diag_combo6_v4.log"
DUMP = "C:/Users/jeffr/Downloads/Lifting/diag_combo6_v4_diffs.g"
MAX_Q = 100000

code = f'''
LogTo("{LOG}");

USE_GENERAL_AUT_HOM := true;
DIAG_GAH_VS_NSCR := true;
DIAG_GAH_MAX_Q_SIZE := {MAX_Q};
DIAG_GAH_DUMP_FILE := "{DUMP}";

PrintTo("{DUMP}", "DIAG_GAH_DIFFERS_LOADED := [];\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

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

Print("\\n[v4] |P|=", Size(P), " (cap |Q|<=", DIAG_GAH_MAX_Q_SIZE, ")\\n\\n");

t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

Print("\\n=== RESULT ===\\n");
Print("[v4] raw FPF: ", Length(fpf), "\\n");
Print("[v4] divergent records: ", Length(DIAG_GAH_DIFFERS), "\\n");
Print("[v4] elapsed: ", Float(elapsed/1000), "s\\n");

LogTo();
QUIT;
''';

tmp_path = r"C:\Users\jeffr\Downloads\Lifting\tmp_diag_combo6_v4.g"
with open(tmp_path, "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_diag_combo6_v4.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print(f"Log: {LOG}")
print(f"Dump: {DUMP}")
