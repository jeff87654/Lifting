import subprocess
import os

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear cache
FPF_SUBDIRECT_CACHE := rec();

Print("\\n=== Profiling [3,2,2,2] ===\\n\\n");

# Test the subspace enumeration directly
Print("Testing EnumerateSubdirectSubspacesRplusK(1, 3)...\\n");
t1 := Runtime();
subspaces := EnumerateSubdirectSubspacesRplusK(1, 3);
t2 := Runtime();
Print("  Found ", Length(subspaces), " subspaces in ", (t2-t1)/1000.0, "s\\n\\n");

# Now test the full C2 optimization path
Print("Testing FindSubdirectsForPartitionWith2s...\\n");
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
Print("  Found ", Length(result), " subdirects in ", (t2-t1)/1000.0, "s\\n\\n");

# Check what GetQuotientMapsToC2 returns for S3
Print("Testing GetQuotientMapsToC2(S3)...\\n");
S3 := SymmetricGroup(3);
quotientInfo := GetQuotientMapsToC2(S3);
Print("  r = ", quotientInfo.dimension, "\\n");
Print("  kernels = ", quotientInfo.kernels, "\\n\\n");

# Now test through the full pipeline
Print("Testing full CountForPartitionFast([3,2,2,2], 9)...\\n");
t1 := Runtime();
# We need to call the actual partition function
testResult := CountForPartitionFast([3,2,2,2], 9);
t2 := Runtime();
Print("  Time: ", (t2-t1)/1000.0, "s\\n");

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
