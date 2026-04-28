import subprocess
import os

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_algorithm.g");
Read("C:/Users/jeffr/Downloads/Lifting/h1_action.g");

ResetH1OrbitalStats();
ResetH1TimingStats();

Print("\\n--- Test: Partition [3,3,2,2] in S10 ---\\n");
Print("Has S_2 swapping the two S_3s and S_2 swapping the two C_2s\\n\\n");

G1 := SymmetricGroup(3);
G2 := SymmetricGroup(3);
G3 := SymmetricGroup(2);
G4 := SymmetricGroup(2);
shifted1 := ShiftGroup(G1, 0);
shifted2 := ShiftGroup(G2, 3);
shifted3 := ShiftGroup(G3, 6);
shifted4 := ShiftGroup(G4, 8);
P := Group(Concatenation(
    GeneratorsOfGroup(shifted1),
    GeneratorsOfGroup(shifted2),
    GeneratorsOfGroup(shifted3),
    GeneratorsOfGroup(shifted4)));

result := FindFPFClassesByLifting(P, [shifted1, shifted2, shifted3, shifted4], [0, 3, 6, 8]);
Print("Found ", Length(result), " FPF subdirects\\n\\n");

PrintH1TimingStats();
Print("\\n");
PrintH1OrbitalStats();

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=300)
print(stdout)
