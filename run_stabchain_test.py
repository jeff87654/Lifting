"""
Test if StabChain of P differs when triggered by Size vs RefinedChiefSeries.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/stabchain_test.log"

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

# P1: Size triggers StabChain
P1 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
x := Size(P1);
sc1 := StabChainMutable(P1);
Print("P1 (Size first):\\n");
Print("  Base: ", BaseStabChain(sc1), "\\n");
Print("  Orbit lengths: ", List(ListStabChain(sc1), r -> Length(r.orbit)), "\\n\\n");

# P2: RefinedChiefSeries triggers StabChain
P2 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
series := RefinedChiefSeries(P2);
sc2 := StabChainMutable(P2);
Print("P2 (RefinedChiefSeries first):\\n");
Print("  Base: ", BaseStabChain(sc2), "\\n");
Print("  Orbit lengths: ", List(ListStabChain(sc2), r -> Length(r.orbit)), "\\n\\n");

# P3: Nothing triggers StabChain yet
P3 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P3 (fresh) HasStabChain: ", HasStabChainMutable(P3), "\\n");
# Force StabChain directly
StabChain(P3);
sc3 := StabChainMutable(P3);
Print("P3 (StabChain directly):\\n");
Print("  Base: ", BaseStabChain(sc3), "\\n");
Print("  Orbit lengths: ", List(ListStabChain(sc3), r -> Length(r.orbit)), "\\n\\n");

# Check if bases differ
if BaseStabChain(sc1) = BaseStabChain(sc2) then
    Print("P1 and P2 have SAME base\\n");
else
    Print("P1 and P2 have DIFFERENT bases!\\n");
fi;
if BaseStabChain(sc1) = BaseStabChain(sc3) then
    Print("P1 and P3 have SAME base\\n");
else
    Print("P1 and P3 have DIFFERENT bases!\\n");
fi;
if BaseStabChain(sc2) = BaseStabChain(sc3) then
    Print("P2 and P3 have SAME base\\n");
else
    Print("P2 and P3 have DIFFERENT bases!\\n");
fi;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_stabchain_test.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_stabchain_test.g"

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

stdout, stderr = process.communicate(timeout=120)

print(f"Finished at {time.strftime('%H:%M:%S')}")
print(f"Return code: {process.returncode}")

try:
    with open(log_file.replace("/", os.sep), "r") as f:
        log = f.read()
    for line in log.split('\n'):
        if any(kw in line for kw in ['Base', 'Orbit', 'SAME', 'DIFFERENT', 'P1', 'P2', 'P3', 'HasStab']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
