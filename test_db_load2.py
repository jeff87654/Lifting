"""Test database loading and transitive subgroups retrieval."""

import subprocess
import os

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/database/load_database.g");
LoadDatabaseIfExists();

Print("\\nTesting TRANSITIVE_SUBGROUPS...\\n");
Print("IsBound TRANSITIVE_SUBGROUPS: ", IsBound(TRANSITIVE_SUBGROUPS), "\\n");

if IsBound(TRANSITIVE_SUBGROUPS) then
    Print("RecNames: ", RecNames(TRANSITIVE_SUBGROUPS), "\\n");
fi;

# Try loading degree 3 manually
Print("\\nManually loading degree 3...\\n");
LoadTransitiveSubgroupsForDegree(3);
Print("IsBound TRANSITIVE_SUBGROUPS.3: ", IsBound(TRANSITIVE_SUBGROUPS.("3")), "\\n");

if IsBound(TRANSITIVE_SUBGROUPS.("3")) then
    Print("RecNames for degree 3: ", RecNames(TRANSITIVE_SUBGROUPS.("3")), "\\n");
    Print("Data for T(3,1): ", TRANSITIVE_SUBGROUPS.("3").("1"), "\\n");
fi;

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_test_db2.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_test_db2.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Testing database loading...")
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
if stderr:
    print("STDERR:", stderr)
