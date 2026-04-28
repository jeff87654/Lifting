import subprocess
import os

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Print("Testing S6...\\n");
result := CountAllConjugacyClassesFast(6);
Print("S6 Result: ", result, " (expected: 56)\\n");
if result = 56 then Print("PASS\\n"); else Print("FAIL\\n"); fi;
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\test_s6_commands.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_s6_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

process = subprocess.Popen(
    [bash_exe, "--login", "-c", f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=300)
print(stdout)
