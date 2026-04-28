"""
Test if StabChain base differs between Size and RefinedChiefSeries.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/stabchain_test2.log"

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
Print("P1 (Size first): base=", BaseStabChain(StabChainMutable(P1)), "\\n\\n");

# P2: RefinedChiefSeries triggers StabChain
P2 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
series := RefinedChiefSeries(P2);
Print("P2 (RefinedChiefSeries first): base=", BaseStabChain(StabChainMutable(P2)), "\\n\\n");

# P3: NaturalHomomorphismByNormalSubgroup
P3 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
hom := NaturalHomomorphismByNormalSubgroup(P3, TrivialSubgroup(P3));
Print("P3 (NaturalHom first): base=", BaseStabChain(StabChainMutable(P3)), "\\n\\n");

# P4: Nothing triggers StabChain yet
P4 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
Print("P4 (fresh) HasStabChain: ", HasStabChainMutable(P4), "\\n");
StabChain(P4);
Print("P4 (StabChain directly): base=", BaseStabChain(StabChainMutable(P4)), "\\n\\n");

# Now test: P with Size(P) called first, then RefinedChiefSeries
P5 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
x := Size(P5);
series5 := RefinedChiefSeries(P5);
Print("P5 (Size then RCS): base=", BaseStabChain(StabChainMutable(P5)), "\\n");
Print("P5 series sizes: ", List(series5, Size), "\\n\\n");

# P with RCS first (no prior Size)
P6 := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
series6 := RefinedChiefSeries(P6);
Print("P6 (RCS first): base=", BaseStabChain(StabChainMutable(P6)), "\\n");
Print("P6 series sizes: ", List(series6, Size), "\\n\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_stabchain_test2.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_stabchain_test2.g"

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

with open(log_file.replace("/", os.sep), "r") as f:
    log = f.read()
for line in log.split('\n'):
    if any(kw in line for kw in ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'base', 'series', 'HasStab']):
        print(line.strip())
