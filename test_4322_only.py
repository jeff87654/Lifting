import subprocess
import os
import time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_4322_only_output.txt"

gap_commands = f'''
LogTo("{log_file}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
FPF_SUBDIRECT_CACHE := rec();

Print("\\n=== Testing [4,3,2,2] only ===\\n");
Print("Expected: 195\\n\\n");

result := FindFPFClassesForPartition(11, [4,3,2,2]);
Print("\\n[4,3,2,2] count: ", Length(result), "\\n");
Print("Expected: 195\\n");
if Length(result) = 195 then
    Print("SUCCESS\\n");
else
    Print("MISMATCH (diff = ", 195 - Length(result), ")\\n");
fi;

LogTo();
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

print("Testing [4,3,2,2] partition only...")

wall_start = time.time()
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=600)
wall_end = time.time()
print(f"Wall clock: {wall_end - wall_start:.1f}s")
print(stdout[-500:] if len(stdout) > 500 else stdout)
