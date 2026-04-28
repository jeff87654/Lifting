"""
Quick check: lift through layers 1-7 no-orbital, layer 8 with orbital.
Count at each step.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/verify_layer8_orb.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Build the combo
T66_5 := TransitiveGroup(6, 5);
T66_8 := TransitiveGroup(6, 8);
T63_2 := TransitiveGroup(3, 2);
factors := [T66_5, T66_8, T63_2];
shifted := [];
offs := [];
off := 0;
for k in [1..Length(factors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(factors[k], off));
    off := off + NrMovedPoints(factors[k]);
od;
P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));

series := RefinedChiefSeries(P);
numLayers := Length(series) - 1;

ClearH1Cache();
current := [P];
for layer_idx in [1..numLayers] do
    M := series[layer_idx];
    NN := series[layer_idx + 1];
    ClearH1Cache();
    if layer_idx = numLayers then
        USE_H1_ORBITAL := true;
    else
        USE_H1_ORBITAL := false;
    fi;
    current := LiftThroughLayer(P, M, NN, current, shifted, offs, fail);
    Print("Layer ", layer_idx, " (orbital=", USE_H1_ORBITAL, "): ",
          Length(current), " results\\n");
od;

Print("\\nTotal: ", Length(current), "\\n");
Print("Sizes: ", List(current, Size), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_verify_layer8_orb.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_verify_layer8_orb.g"

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

stdout, stderr = process.communicate(timeout=600)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if 'Layer' in line or 'Total' in line or 'Sizes' in line or 'orbital' in line.lower():
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
