"""Run combo 6 with the fix and INSTRUMENTED per-parent timing.  The
instrumentation prints (and FLUSHES) timing for each major step within the
complement-finding loop, so we can see WHERE time is spent on slow parents.
"""
import subprocess, os

LOG = "C:/Users/jeffr/Downloads/Lifting/combo6_inst.log"

code = r'''
LogTo("__LOG__");

USE_GENERAL_AUT_HOM := true;
DIAG_GAH_VS_NSCR := false;
GENERAL_AUT_HOM_VERBOSE := true;

# Bypass cache save bug.
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
SaveFPFSubdirectCache := function() end;

# Force per-parent stdout flush by hooking inside the lifting code via
# a global progress counter.  We override at the layer level.
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

Print("\n[inst] |P|=", Size(P), " |N|=", Size(N), "\n\n");

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
Print("[inst] Raw FPF: ", Length(fpf), "\n");
Print("[inst] Deduped: ", Length(deduped), " classes\n");
Print("[inst] Elapsed: ", Float(elapsed/1000), "s\n");
if Length(deduped) = 154 then
    Print("[inst] *** MATCH: bug fixed! ***\n");
else
    Print("[inst] *** count = ", Length(deduped), " (expected 154) ***\n");
fi;

LogTo();
QUIT;
'''.replace("__LOG__", LOG)

tmp_path = r"C:\Users\jeffr\Downloads\Lifting\tmp_combo6_inst.g"
with open(tmp_path, "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_combo6_inst.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print(f"Log: {LOG}")
