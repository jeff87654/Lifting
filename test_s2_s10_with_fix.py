"""S2-S10 regression with the GAH fix enabled.  Should give 1593 (the
verified count from CLAUDE.md).
"""
import subprocess, os

LOG = "C:/Users/jeffr/Downloads/Lifting/s2_s10_with_fix.log"

code = r'''
LogTo("__LOG__");

USE_GENERAL_AUT_HOM := true;
DIAG_GAH_VS_NSCR := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear caches for clean run.
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Bypass pre-existing SaveFPFSubdirectCache bug (MovedPoints error) — not
# related to the GAH fix.  We just want S_n counts.
SaveFPFSubdirectCache := function() end;

Print("\n[s2-10] Starting S2-S10 with USE_GENERAL_AUT_HOM=true (with FIX)\n");
t0 := Runtime();
total := 0;
for n in [2..10] do
    cnt := CountAllConjugacyClassesFast(n);
    total := total + cnt;
    Print("[s2-10] S", n, " = ", cnt, "\n");
od;
elapsed := Runtime() - t0;

Print("\n=== S2-S10 RESULT ===\n");
Print("[s2-10] Total: ", total, " (expected 1593)\n");
Print("[s2-10] Elapsed: ", Float(elapsed/1000), "s\n");
if total = 1593 then
    Print("[s2-10] *** PASS: regression OK ***\n");
else
    Print("[s2-10] *** FAIL: total = ", total, " not 1593 ***\n");
fi;

LogTo();
QUIT;
'''.replace("__LOG__", LOG)

tmp_path = r"C:\Users\jeffr\Downloads\Lifting\tmp_s2_s10_fix.g"
with open(tmp_path, "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_s2_s10_fix.g"'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

print(f"Launched at PID {p.pid}")
print(f"Log: {LOG}")
