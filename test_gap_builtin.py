import subprocess
import os

gap_commands = '''
Print("CanEasilyComputePcgs bound: ", IsBound(CanEasilyComputePcgs), "\\n");
if IsBound(CanEasilyComputePcgs) then
    Print("Testing on S4: ", CanEasilyComputePcgs(SymmetricGroup(4)), "\\n");
    Print("Testing on A5: ", CanEasilyComputePcgs(AlternatingGroup(5)), "\\n");
fi;
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_builtin.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_builtin.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=60)
print(stdout)
if stderr:
    print("STDERR:", stderr)
