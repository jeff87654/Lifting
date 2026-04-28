"""End-to-end validation: run combo 6 with the fixed GAH (USE_GENERAL_AUT_HOM
= true) and verify the final deduped count is 154 (matching the prebug
baseline / NSCR).
"""
import subprocess, os

LOG = "C:/Users/jeffr/Downloads/Lifting/combo6_with_fix.log"

code = r'''
LogTo("__LOG__");

USE_GENERAL_AUT_HOM := true;
DIAG_GAH_VS_NSCR := false;

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

Print("\n[fix] |P|=", Size(P), " |N|=", Size(N), "\n");
Print("[fix] starting FindFPFClassesByLifting (USE_GENERAL_AUT_HOM=true with FIX)...\n\n");

t0 := Runtime();
fpf := FindFPFClassesByLifting(P, shifted, offsets, N);
elapsed := Runtime() - t0;

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

Print("\n=== RESULT ===\n");
Print("[fix] Raw FPF: ", Length(fpf), "\n");
Print("[fix] Deduped: ", Length(deduped), " classes\n");
Print("[fix] Elapsed: ", Float(elapsed/1000), "s\n");
Print("[fix] Expected: 154 (prebug baseline)\n");
if Length(deduped) = 154 then
    Print("[fix] *** MATCH: bug fixed! ***\n");
else
    Print("[fix] *** MISMATCH: still ", Length(deduped) - 154, " off\n");
fi;

LogTo();
QUIT;
'''.replace("__LOG__", LOG)

tmp_path = r"C:\Users\jeffr\Downloads\Lifting\tmp_combo6_with_fix.g"
with open(tmp_path, "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_combo6_with_fix.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print(f"Log: {LOG}")
