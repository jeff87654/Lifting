"""
Check if RefinedChiefSeries(P) gives different results across calls.
"""

import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/check_series.log"

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

Print("=== Chief Series Check ===\\n\\n");

# Call RefinedChiefSeries multiple times
for trial in [1..5] do
    series := RefinedChiefSeries(P);
    Print("Trial ", trial, ": sizes=", List(series, Size));
    Print(" factors=", List([1..Length(series)-1], i -> Size(series[i])/Size(series[i+1])));
    Print("\\n");

    # Check if the actual groups are the same
    if trial = 1 then
        saved_series := series;
    else
        same := true;
        for i in [1..Length(series)] do
            if series[i] <> saved_series[i] then
                same := false;
                Print("  DIFFERENT at position ", i, "!\\n");
                Print("  This: ", series[i], " generators=", GeneratorsOfGroup(series[i]), "\\n");
                Print("  Saved: ", saved_series[i], " generators=", GeneratorsOfGroup(saved_series[i]), "\\n");
                break;
            fi;
        od;
        if same then
            Print("  Same as trial 1\\n");
        fi;
    fi;
od;

# Now test: does FindFPFClassesByLifting compute its own chief series?
# And does USE_H1_ORBITAL affect the result?
Print("\\n=== FindFPFClassesByLifting tests ===\\n");

USE_H1_ORBITAL := true;
ClearH1Cache();
result1 := FindFPFClassesByLifting(P, shifted, offs);
Print("Run 1 (orbital=true): ", Length(result1), " results\\n");

USE_H1_ORBITAL := true;
ClearH1Cache();
result2 := FindFPFClassesByLifting(P, shifted, offs);
Print("Run 2 (orbital=true): ", Length(result2), " results\\n");

USE_H1_ORBITAL := false;
ClearH1Cache();
result3 := FindFPFClassesByLifting(P, shifted, offs);
Print("Run 3 (orbital=false): ", Length(result3), " results\\n");

USE_H1_ORBITAL := false;
ClearH1Cache();
result4 := FindFPFClassesByLifting(P, shifted, offs);
Print("Run 4 (orbital=false): ", Length(result4), " results\\n");

# Check sizes
Print("\\nResult 1 sizes: ", List(result1, Size), "\\n");
Print("Result 3 sizes: ", List(result3, Size), "\\n");

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_check_series.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_check_series.g"

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
        if any(kw in line for kw in ['Trial', 'Run', 'sizes', 'DIFFERENT', 'Same', 'Result']):
            print(line.strip())
except FileNotFoundError:
    print("Log file not found!")
