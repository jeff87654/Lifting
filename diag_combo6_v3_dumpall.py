"""Diagnostic v3: re-run combo 6 with USE_GENERAL_AUT_HOM=true (the buggy
mode) and dump EVERY GAH/HBC call's (Q, M_bar) generators to a file, with
NO NSCR comparison.  After this finishes (similar runtime to W506's
original ~63 minutes), we replay the largest-|Q| calls offline against NSCR.
"""
import subprocess, os

LOG = "C:/Users/jeffr/Downloads/Lifting/diag_combo6_v3.log"
DUMP_ALL = "C:/Users/jeffr/Downloads/Lifting/diag_combo6_v3_allcalls.g"

code = f'''
LogTo("{LOG}");

USE_GENERAL_AUT_HOM := true;
DIAG_GAH_VS_NSCR := false;
DIAG_GAH_DUMP_ALL_FILE := "{DUMP_ALL}";

PrintTo("{DUMP_ALL}", "GAH_ALL_CALLS := [];\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

Print("\\n[v3] USE_GENERAL_AUT_HOM = true (buggy mode)\\n");
Print("[v3] dumping all GAH/HBC calls to ", DIAG_GAH_DUMP_ALL_FILE, "\\n\\n");

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

Print("[v3] |P|=", Size(P), " |N|=", Size(N), "\\n");

t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

# Final dedup under N to compare to the 147 vs 154 question.
CURRENT_BLOCK_RANGES := [];
off := 0;
for k in [1..Length(partition)] do
    Add(CURRENT_BLOCK_RANGES, [off + 1, off + partition[k]]);
    off := off + partition[k];
od;
deduped := [];
byInv := rec();
for H in fpf do
    AddIfNotConjugate(N, H, deduped, byInv, ComputeSubgroupInvariant);
od;

Print("\\n=== RESULT ===\\n");
Print("[v3] raw FPF: ", Length(fpf), "\\n");
Print("[v3] deduped (under N): ", Length(deduped), "\\n");
Print("[v3] elapsed: ", Float(elapsed/1000), "s\\n");
Print("[v3] expected (with GAH bug): 147\\n");
Print("[v3] dump file: ", DIAG_GAH_DUMP_ALL_FILE, "\\n");

LogTo();
QUIT;
''';

tmp_path = r"C:\Users\jeffr\Downloads\Lifting\tmp_diag_combo6_v3.g"
with open(tmp_path, "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_diag_combo6_v3.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print(f"Log: {LOG}")
print(f"Dump-all: {DUMP_ALL}")
