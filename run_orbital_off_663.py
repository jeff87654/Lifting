import subprocess, os, time

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_orbital_off_6_6_3.log"
gens_file = "C:/Users/jeffr/Downloads/Lifting/parallel_s15/gens/gens_6_6_3_orbital_off.txt"

gap_commands = f'''
LogTo("{log_file}");
USE_H1_ORBITAL := false;
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

Print("USE_H1_ORBITAL = ", USE_H1_ORBITAL, "\\n");
Print("=== Recomputing [6,6,3] with orbital OFF ===\\n");
t0 := Runtime();
result := FindFPFClassesForPartition(15, [6,6,3]);
t1 := Runtime();
Print("[6,6,3] orbital OFF count: ", Length(result), "\\n");
Print("[6,6,3] time: ", StringTime(t1 - t0), "\\n");

fname := "{gens_file}";
PrintTo(fname, "");
for H in result do
    AppendTo(fname, GeneratorsOfGroup(H), "\\n");
od;
Print("Saved ", Length(result), " groups\\n");
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_cmd_orbital_off_663.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_cmd_orbital_off_663.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"[6,6,3] orbital OFF starting at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=14400)
print(f"[6,6,3] orbital OFF finished at {time.strftime('%H:%M:%S')}")

with open(log_file.replace("/", os.sep), "r") as f:
    for line in f:
        if "count:" in line or "time:" in line or "USE_H1" in line:
            print(line.strip())
