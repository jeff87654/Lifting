"""
Test: Disable orbital at ONE layer at a time to find which layer's merge causes the final deficit.

For combo T(6,5) x T(6,8) x T(3,2):
- OFF gives 26 final children
- ON gives 17 final children (some are incorrect merges)

We test:
- Orbital ON at all layers: expect 17
- Orbital ON except layer K: if layer K's merge causes the bug, expect >17
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/per_layer_orbital.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Set up combo
factors := [TransitiveGroup(6, 5), TransitiveGroup(6, 8), TransitiveGroup(3, 2)];
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
numLayers := Length(series) - 1;
Print("Chief series: ", List(series, Size), "\\n");
Print("Num layers: ", numLayers, "\\n\\n");

# Reference: all orbital OFF
Print("=== Reference: orbital OFF (all layers) ===\\n");
USE_H1_ORBITAL := false;
parents_ref := [P];
for i in [1..numLayers] do
    ClearH1Cache();
    FPF_SUBDIRECT_CACHE := rec();
    parents_ref := LiftThroughLayer(P, series[i], series[i+1], parents_ref, shifted, offs, fail);
od;
Print("OFF: ", Length(parents_ref), " final children\\n\\n");

# Reference: all orbital ON
Print("=== Reference: orbital ON (all layers) ===\\n");
USE_H1_ORBITAL := true;
parents_full_on := [P];
for i in [1..numLayers] do
    ClearH1Cache();
    FPF_SUBDIRECT_CACHE := rec();
    parents_full_on := LiftThroughLayer(P, series[i], series[i+1], parents_full_on, shifted, offs, fail);
od;
Print("Full ON: ", Length(parents_full_on), " final children\\n\\n");

# Test: disable orbital at one layer at a time
for skipLayer in [1..numLayers] do
    parents := [P];
    for i in [1..numLayers] do
        if i = skipLayer then
            USE_H1_ORBITAL := false;
        else
            USE_H1_ORBITAL := true;
        fi;
        ClearH1Cache();
        FPF_SUBDIRECT_CACHE := rec();
        parents := LiftThroughLayer(P, series[i], series[i+1], parents, shifted, offs, fail);
    od;
    diff := Length(parents) - Length(parents_full_on);
    Print("Skip layer ", skipLayer, " (factor=", Size(series[skipLayer])/Size(series[skipLayer+1]),
          "): ", Length(parents), " children");
    if diff > 0 then
        Print(" (+", diff, " vs full ON)");
    fi;
    Print("\\n");
od;

# Also test: orbital ON at ONLY one layer at a time
Print("\\n=== Orbital ON at only ONE layer ===\\n");
for onlyLayer in [1..numLayers] do
    parents := [P];
    for i in [1..numLayers] do
        if i = onlyLayer then
            USE_H1_ORBITAL := true;
        else
            USE_H1_ORBITAL := false;
        fi;
        ClearH1Cache();
        FPF_SUBDIRECT_CACHE := rec();
        parents := LiftThroughLayer(P, series[i], series[i+1], parents, shifted, offs, fail);
    od;
    diff := Length(parents_ref) - Length(parents);
    Print("Only layer ", onlyLayer, " (factor=", Size(series[onlyLayer])/Size(series[onlyLayer+1]),
          "): ", Length(parents), " children");
    if diff > 0 then
        Print(" (-", diff, " vs OFF)");
    fi;
    Print("\\n");
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_per_layer_orbital.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_per_layer_orbital.g"

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

stdout, stderr = process.communicate(timeout=7200)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        line_stripped = line.strip()
        if any(kw in line for kw in ['===', 'OFF:', 'ON:', 'Full ON', 'Skip layer',
                                      'Only layer', 'Chief', 'Num layers', 'children',
                                      'Reference']):
            print(line_stripped)
except FileNotFoundError:
    print("Log file not found!")
