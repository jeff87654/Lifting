"""
For each combo in [6,6,3], compare per-parent complement counts
between orbital ON and OFF. When they differ, check if the orbital
orbit representatives correctly cover all FPF complements.

Key insight: within a single parent S and layer, the orbital method
should produce exactly the right number of P-conjugacy classes of
FPF complements. If it doesn't, the action matrix is wrong for that
parent/layer.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/find_bad_layer.log"

# Use a focused test: just check the combos that had raw count differences
# in the earlier orbital_diagnosis.py run. The biggest discrepancy was
# [T6_9, T6_9, T3_2] with ON=310, OFF=656 (diff=346).
# But those are raw counts. We need to check per-parent.
#
# Better approach: instrument LiftThroughLayer to log per-parent complement
# counts for both orbital and non-orbital paths, then compare.

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# We'll test [T6_5, T6_5, T3_2] which is a repeated-part combo
# (two copies of T6_5). Let's try [T6_9, T6_9, T3_2] since it had
# the biggest raw count difference.

testCombos := [
    [[6,9], [6,9], [3,2]],
    [[6,5], [6,8], [3,2]],
    [[6,3], [6,3], [3,2]]
];

for comboInfo in testCombos do
    factors := List(comboInfo, x -> TransitiveGroup(x[1], x[2]));
    shifted := [];
    offs := [];
    off := 0;
    for k in [1..3] do
        Add(offs, off);
        Add(shifted, ShiftGroup(factors[k], off));
        off := off + NrMovedPoints(factors[k]);
    od;
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));

    series := RefinedChiefSeries(P);
    Print("\\n=== Combo ", comboInfo, " |P|=", Size(P), " ===\\n");
    Print("Chief series sizes: ", List(series, Size), "\\n");

    # Lift through all layers except the last
    # Run twice: orbital ON and OFF
    for useOrbital in [true, false] do
        USE_H1_ORBITAL := useOrbital;
        ClearH1Cache();
        FPF_SUBDIRECT_CACHE := rec();

        parents := [P];
        for i in [1..Length(series)-2] do
            ClearH1Cache();
            parents := LiftThroughLayer(P, series[i], series[i+1], parents, shifted, offs, fail);
        od;

        # Final layer
        M := series[Length(series)-1];
        L := series[Length(series)];
        ClearH1Cache();
        finalLifted := LiftThroughLayer(P, M, L, parents, shifted, offs, fail);

        Print("  orbital=", useOrbital, ": ",
              Length(parents), " parents -> ", Length(finalLifted), " final lifted\\n");
    od;
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_find_bad_layer.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_find_bad_layer.g"

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

stdout, stderr = process.communicate(timeout=3600)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['===', 'orbital=', 'Chief', 'parents', 'Combo',
                                      'H^1 orbital']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
