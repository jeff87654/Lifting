"""
Compare chief series GROUP OBJECTS (not just sizes) between Size(P) and fresh P.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/series_diff.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

T63_2 := TransitiveGroup(3, 2);
T66_5 := TransitiveGroup(6, 5);
T66_8 := TransitiveGroup(6, 8);
factors := [T66_5, T66_8, T63_2];
shifted := [];
offs := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;

P1 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
x := Size(P1);
series1 := RefinedChiefSeries(P1);

P2 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
series2 := RefinedChiefSeries(P2);

Print("Comparing chief series generators:\\n");
for i in [1..Length(series1)] do
    gens1 := GeneratorsOfGroup(series1[i]);
    gens2 := GeneratorsOfGroup(series2[i]);
    same_gens := (gens1 = gens2);
    same_group := (series1[i] = series2[i]);
    Print("  Level ", i, ": |G|=", Size(series1[i]),
          " sameGens=", same_gens,
          " sameGroup=", same_group,
          " ngens1=", Length(gens1), " ngens2=", Length(gens2), "\\n");
    if not same_gens then
        Print("    gens1: ", gens1, "\\n");
        Print("    gens2: ", gens2, "\\n");
    fi;
od;

# Check the subgroups at layer 8 level (series[8] = M, series[9] = N)
Print("\\nLayer 8 details:\\n");
Print("  series1[8] gens: ", GeneratorsOfGroup(series1[8]), "\\n");
Print("  series2[8] gens: ", GeneratorsOfGroup(series2[8]), "\\n");
Print("  series1[9] = trivial: ", Size(series1[9]) = 1, "\\n");

# Critical: lift through layers 1-7 and check if parents differ
USE_H1_ORBITAL := true;
current1 := [P1];
for i in [1..7] do
    ClearH1Cache();
    current1 := LiftThroughLayer(P1, series1[i], series1[i+1], current1, shifted, offs, fail);
od;

ClearH1Cache();
current2 := [P2];
for i in [1..7] do
    ClearH1Cache();
    current2 := LiftThroughLayer(P2, series2[i], series2[i+1], current2, shifted, offs, fail);
od;

Print("\\nParents after 7 layers:\\n");
Print("  Stab: ", Length(current1), " Fresh: ", Length(current2), "\\n");
Print("  Stab sizes: ", List(current1, Size), "\\n");
Print("  Fresh sizes: ", List(current2, Size), "\\n\\n");

# Check if parents are the same groups
Print("Comparing parents pairwise:\\n");
for i in [1..Length(current1)] do
    same := (current1[i] = current2[i]);
    Print("  Parent ", i, ": same=", same, " |S1|=", Size(current1[i]), " |S2|=", Size(current2[i]), "\\n");
    if not same then
        gens1 := GeneratorsOfGroup(current1[i]);
        gens2 := GeneratorsOfGroup(current2[i]);
        Print("    gens1: ", gens1, "\\n");
        Print("    gens2: ", gens2, "\\n");
    fi;
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_series_diff.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_series_diff.g"

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

stdout, stderr = process.communicate(timeout=300)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

with open(log_file.replace("/", os.sep), "r") as f:
    log = f.read()
for line in log.split('\n'):
    if any(kw in line for kw in ['Level', 'Layer', 'Parent', 'Stab', 'Fresh',
                                  'same', 'gens', 'Comparing']):
        print(line.strip())
