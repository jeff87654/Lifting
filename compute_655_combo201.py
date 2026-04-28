"""Compute the single skipped combo from [6,5,5]: [[5,2],[5,2],[6,14]]
Timeout: 2 hours. If it hangs, we know the combo is infeasible in practice.
"""

import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

LOG_FILE = "C:/Users/jeffr/Downloads/Lifting/combo201_debug.log"
SCRIPT_FILE = os.path.join(LIFTING_DIR, "combo201_debug.g")

TIMEOUT_SEC = 7200  # 2 hours

gap_code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/combo201_debug.log");
Print("Computing [6,5,5] combo [[5,2],[5,2],[6,14]]\\n");
Print("Started at ", StringTime(Runtime()), "\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

N := 16;
offsets := [0, 6, 11];

f1 := TransitiveGroup(6, 14);
f2 := TransitiveGroup(5, 2);
f3 := TransitiveGroup(5, 2);

Print("f1 = TransGrp(6,14): ", StructureDescription(f1), " order=", Size(f1), "\\n");
Print("f2 = TransGrp(5,2): ", StructureDescription(f2), " order=", Size(f2), "\\n");
Print("f3 = TransGrp(5,2): ", StructureDescription(f3), " order=", Size(f3), "\\n\\n");

s1 := ShiftGroup(f1, offsets[1]);
s2 := ShiftGroup(f2, offsets[2]);
s3 := ShiftGroup(f3, offsets[3]);

shifted := [s1, s2, s3];
Print("Shifted moved points: ", List(shifted, MovedPoints), "\\n");

P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P order = ", Size(P), "\\n\\n");

cs := ChiefSeries(P);
Print("Chief series (", Length(cs), " terms, ", Length(cs)-1, " layers):\\n");
for i in [1..Length(cs)-1] do
    Print("  Layer ", i, ": |factor| = ", Size(cs[i]) / Size(cs[i+1]), "\\n");
od;
Print("\\n");

Print("Calling FindFPFClassesByLifting...\\n");
LogTo();
LogTo("C:/Users/jeffr/Downloads/Lifting/combo201_debug.log");

result := FindFPFClassesByLifting(P, shifted, offsets, N);

Print("\\nResult: ", Length(result), " FPF classes found\\n");
Print("Completed at ", StringTime(Runtime()), "\\n");

LogTo();
QUIT;
'''

with open(SCRIPT_FILE, "w") as f:
    f.write(gap_code)

script_cygwin = SCRIPT_FILE.replace("C:\\", "/cygdrive/c/").replace("\\", "/")

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

cmd = [
    BASH_EXE, "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_cygwin}"'
]

print(f"Launching GAP for combo [[5,2],[5,2],[6,14]]...", flush=True)
print(f"Timeout: {TIMEOUT_SEC}s ({TIMEOUT_SEC//60} min)", flush=True)
print(f"Log: {LOG_FILE}", flush=True)

start = time.time()
process = subprocess.Popen(
    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    env=env, cwd=GAP_RUNTIME
)
print(f"PID: {process.pid}", flush=True)

try:
    last_report = 0
    while True:
        rc = process.poll()
        if rc is not None:
            elapsed = time.time() - start
            print(f"\nGAP exited with code {rc} after {elapsed:.0f}s", flush=True)
            break

        elapsed = time.time() - start
        if elapsed > TIMEOUT_SEC:
            print(f"\nTIMEOUT after {elapsed:.0f}s, killing...", flush=True)
            process.kill()
            process.wait(timeout=30)
            print("Killed.", flush=True)
            break

        if elapsed - last_report >= 60:
            last_report = elapsed
            log_win = LOG_FILE.replace("/", "\\")
            if os.path.exists(log_win):
                try:
                    with open(log_win) as f:
                        lines = f.readlines()
                    if lines:
                        print(f"  [{int(elapsed)}s] {len(lines)}L, last: {lines[-1].strip()[:80]}", flush=True)
                except:
                    pass
        time.sleep(5)

except KeyboardInterrupt:
    process.kill()
    print("Interrupted.", flush=True)

log_win = LOG_FILE.replace("/", "\\")
if os.path.exists(log_win):
    with open(log_win) as f:
        content = f.read()
    print(f"\n=== Log ({len(content)} bytes) ===", flush=True)
    for line in content.strip().split("\n")[-40:]:
        print(line, flush=True)
else:
    print("No log file found", flush=True)
