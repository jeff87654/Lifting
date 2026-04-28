import subprocess
import os

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear cache
FPF_SUBDIRECT_CACHE := rec();

Print("\\n=== Testing Orbit Reduction ===\\n\\n");

# Test subspace counts
Print("EnumerateSubdirectSubspaces(3) [pure C2^3]:\\n");
t1 := Runtime();
s := EnumerateSubdirectSubspaces(3);
Print("  ", Length(s), " orbit reps (was 5 subspaces)\\n");
Print("  Time: ", (Runtime()-t1)/1000.0, "s\\n\\n");

Print("EnumerateSubdirectSubspaces(4) [pure C2^4]:\\n");
t1 := Runtime();
s := EnumerateSubdirectSubspaces(4);
Print("  ", Length(s), " orbit reps\\n");
Print("  Time: ", (Runtime()-t1)/1000.0, "s\\n\\n");

Print("EnumerateSubdirectSubspacesRplusK(1, 3) [for [3,2,2,2]]:\\n");
t1 := Runtime();
s := EnumerateSubdirectSubspacesRplusK(1, 3);
Print("  ", Length(s), " orbit reps (was 349 subspaces)\\n");
Print("  Time: ", (Runtime()-t1)/1000.0, "s\\n\\n");

# Now test the full partition
Print("=== Full [3,2,2,2] test ===\\n");
partition := [3,2,2,2];
G1 := SymmetricGroup(3);
G2 := SymmetricGroup(2);
G3 := SymmetricGroup(2);
G4 := SymmetricGroup(2);
shifted := [ShiftGroup(G1, 0), ShiftGroup(G2, 3), ShiftGroup(G3, 5), ShiftGroup(G4, 7)];
offs := [0, 3, 5, 7];

t1 := Runtime();
result := FindSubdirectsForPartitionWith2s(partition, [G1, G2, G3, G4], shifted, offs);
t2 := Runtime();
Print("  Found ", Length(result), " subdirects in ", (t2-t1)/1000.0, "s\\n");
Print("  (was 349 in 0.578s, should be much fewer)\\n\\n");

# Full S8 verification
Print("=== Full S8 verification ===\\n");
result8 := CountAllConjugacyClassesFast(8);
Print("S8 count: ", result8, " (expected 296)\\n");
if result8 = 296 then
    Print("SUCCESS!\\n");
else
    Print("MISMATCH!\\n");
fi;

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

stdout, stderr = process.communicate(timeout=600)
print(stdout)
if "Error" in stderr:
    print("STDERR:", stderr[:2000])
