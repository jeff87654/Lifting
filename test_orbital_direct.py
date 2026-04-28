import subprocess
import os
import sys

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
Read("C:/Users/jeffr/Downloads/Lifting/h1_action.g");

# Reset statistics
ResetH1OrbitalStats();
ResetH1TimingStats();

Print("\\n========================================\\n");
Print("Direct Test of H^1 Orbital Optimization\\n");
Print("========================================\\n\\n");

# Clear cache to force fresh computation
if IsBound(FPF_SUBDIRECT_CACHE) then
    FPF_SUBDIRECT_CACHE := rec();
fi;

# Test partition [3,3] in S6 - has swap automorphism
# The outer normalizer S_2 wr S_3 permutes the two factors
Print("\\n--- Test 1: Partition [3,3] in S6 ---\\n");
Print("Expected: S_2 (swap automorphism) acts on H^1, giving orbit reduction\\n\\n");

G1 := SymmetricGroup(3);
G2 := SymmetricGroup(3);
shifted1 := ShiftGroup(G1, 0);
shifted2 := ShiftGroup(G2, 3);
P := Group(Concatenation(GeneratorsOfGroup(shifted1), GeneratorsOfGroup(shifted2)));

result := FindFPFClassesByLifting(P, [shifted1, shifted2], [0, 3]);
Print("Found ", Length(result), " FPF subdirects for [3,3]\\n");
Print("Expected: 6\\n\\n");

PrintH1TimingStats();
Print("\\n");
PrintH1OrbitalStats();

# Test partition [4,4] in S8 - has swap automorphism
Print("\\n--- Test 2: Partition [4,4] in S8 ---\\n");
Print("Expected: S_2 (swap automorphism) acts on H^1, giving orbit reduction\\n\\n");

ResetH1OrbitalStats();
ResetH1TimingStats();

G1 := SymmetricGroup(4);
G2 := SymmetricGroup(4);
shifted1 := ShiftGroup(G1, 0);
shifted2 := ShiftGroup(G2, 4);
P := Group(Concatenation(GeneratorsOfGroup(shifted1), GeneratorsOfGroup(shifted2)));

result := FindFPFClassesByLifting(P, [shifted1, shifted2], [0, 4]);
Print("Found ", Length(result), " FPF subdirects for [4,4]\\n");
Print("Expected: 50\\n\\n");

PrintH1TimingStats();
Print("\\n");
PrintH1OrbitalStats();

# Test partition [3,3,2] in S8 - has swap on the 3s
Print("\\n--- Test 3: Partition [3,3,2] in S8 ---\\n");
Print("Expected: S_2 (swap of the two S_3) acts on H^1\\n\\n");

ResetH1OrbitalStats();
ResetH1TimingStats();

G1 := SymmetricGroup(3);
G2 := SymmetricGroup(3);
G3 := SymmetricGroup(2);
shifted1 := ShiftGroup(G1, 0);
shifted2 := ShiftGroup(G2, 3);
shifted3 := ShiftGroup(G3, 6);
P := Group(Concatenation(
    GeneratorsOfGroup(shifted1),
    GeneratorsOfGroup(shifted2),
    GeneratorsOfGroup(shifted3)));

result := FindFPFClassesByLifting(P, [shifted1, shifted2, shifted3], [0, 3, 6]);
Print("Found ", Length(result), " FPF subdirects for [3,3,2]\\n");
Print("Expected: 11\\n\\n");

PrintH1TimingStats();
Print("\\n");
PrintH1OrbitalStats();

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

print("Running direct orbital optimization test...")
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
    stdout, stderr = process.communicate(timeout=600)  # 10 minute timeout
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
except subprocess.TimeoutExpired:
    process.kill()
    print("Test timed out after 10 minutes")
    sys.exit(1)
