import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
Read("C:/Users/jeffr/Downloads/Lifting/h1_action.g");

Print("\\n========================================\\n");
Print("Comparing Orbital vs Non-Orbital Results\\n");
Print("========================================\\n\\n");

# Clear cache to force fresh computation
if IsBound(FPF_SUBDIRECT_CACHE) then
    FPF_SUBDIRECT_CACHE := rec();
fi;

# Test partition [3,3] in S6
Print("\\n--- Test: Partition [3,3] in S6 ---\\n\\n");

G1 := SymmetricGroup(3);
G2 := SymmetricGroup(3);
shifted1 := ShiftGroup(G1, 0);
shifted2 := ShiftGroup(G2, 3);
P := Group(Concatenation(GeneratorsOfGroup(shifted1), GeneratorsOfGroup(shifted2)));

# WITH orbital optimization
Print("WITH orbital optimization (USE_H1_ORBITAL = true):\\n");
USE_H1_ORBITAL := true;
ResetH1OrbitalStats();
result_with := FindFPFClassesByLifting(P, [shifted1, shifted2], [0, 3]);
Print("Found ", Length(result_with), " FPF subdirects\\n");
for i in [1..Length(result_with)] do
    Print("  ", i, ": |G| = ", Size(result_with[i]), "\\n");
od;
Print("\\n");
PrintH1OrbitalStats();

# WITHOUT orbital optimization
Print("\\nWITHOUT orbital optimization (USE_H1_ORBITAL = false):\\n");
USE_H1_ORBITAL := false;
ResetH1OrbitalStats();
result_without := FindFPFClassesByLifting(P, [shifted1, shifted2], [0, 3]);
Print("Found ", Length(result_without), " FPF subdirects\\n");
for i in [1..Length(result_without)] do
    Print("  ", i, ": |G| = ", Size(result_without[i]), "\\n");
od;

Print("\\n--- Comparison ---\\n");
Print("With orbital:    ", Length(result_with), "\\n");
Print("Without orbital: ", Length(result_without), "\\n");
Print("Expected: 6 (from previous runs)\\n");

QUIT;
'''

# Write commands to a temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

# GAP environment setup
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Comparing orbital vs non-orbital results...")
print()

# Run GAP via Cygwin bash
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

try:
    stdout, stderr = process.communicate(timeout=300)
    print(stdout)
    if stderr and "Syntax warning" not in stderr:
        print("STDERR:", stderr)
except subprocess.TimeoutExpired:
    process.kill()
    print("Test timed out")
    sys.exit(1)
