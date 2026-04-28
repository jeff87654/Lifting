"""Test database loading and transitive subgroups retrieval."""

import subprocess
import os

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/database/load_database.g");
LoadDatabaseIfExists();

Print("\\n=== Testing Transitive Subgroups Database ===\\n");

# Test GetPrecomputedSubgroups
Print("T(3,1) = C3: ", Length(GetPrecomputedSubgroups(3, 1)), " subgroups (expected 2)\\n");
Print("T(3,2) = S3: ", Length(GetPrecomputedSubgroups(3, 2)), " subgroups (expected 4)\\n");
Print("T(4,5) = S4: ", Length(GetPrecomputedSubgroups(4, 5)), " subgroups (expected 11)\\n");
Print("T(8,50) = S8: ", Length(GetPrecomputedSubgroups(8, 50)), " subgroups (expected 296)\\n");

# Test GetSubgroupClassReps with a transitive group
Print("\\n=== Testing GetSubgroupClassReps ===\\n");
S3 := SymmetricGroup(3);
subs := GetSubgroupClassReps(S3);
Print("S3 via GetSubgroupClassReps: ", Length(subs), " subgroups (expected 4)\\n");

S4 := SymmetricGroup(4);
subs := GetSubgroupClassReps(S4);
Print("S4 via GetSubgroupClassReps: ", Length(subs), " subgroups (expected 11)\\n");

# Test with shifted group
shifted_S3 := Group((4,5,6), (4,5));  # S3 on {4,5,6}
subs := GetSubgroupClassReps(shifted_S3);
Print("S3 on {4,5,6} via GetSubgroupClassReps: ", Length(subs), " subgroups (expected 4)\\n");

Print("\\nDatabase statistics:\\n");
PrintDatabaseStats();

Print("\\n=== All tests completed ===\\n");
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test_db.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_db.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Testing database loading and transitive subgroups...")
print("=" * 60)

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=120)
print(stdout)
if stderr and "Syntax warning" not in stderr:
    print("STDERR:", stderr)
