"""Quick test: S10 + S12 [8,4] with CheapSubgroupInvariantFull + centralizer opt."""
import subprocess, os, time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_quick.log"
gap_commands = (
    f'LogTo("{log_file}");\n'
    'Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");\n'
    'Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");\n'
    'FPF_SUBDIRECT_CACHE := rec();\n'
    'LIFT_CACHE := rec();\n'
    'if IsBound(ClearH1Cache) then ClearH1Cache(); fi;\n'
    'startTime := Runtime();\n'
    'result := CountAllConjugacyClassesFast(10);\n'
    'elapsed := (Runtime() - startTime) / 1000.0;\n'
    'Print("S10 = ", result, " (expected 1593), time = ", elapsed, "s\\n");\n'
    'if result = 1593 then Print("S10 PASS\\n"); else Print("S10 FAIL!\\n"); fi;\n'
    'if IsBound(ClearH1Cache) then ClearH1Cache(); fi;\n'
    'FPF_SUBDIRECT_CACHE := rec();\n'
    'startTime := Runtime();\n'
    'r := FindFPFClassesForPartition(12, [8,4]);\n'
    'elapsed := (Runtime() - startTime) / 1000.0;\n'
    'Print("[8,4] = ", Length(r), " (expected 1376), time = ", elapsed, "s\\n");\n'
    'if Length(r) = 1376 then Print("[8,4] PASS\\n"); else Print("[8,4] FAIL!\\n"); fi;\n'
    'LogTo();\nQUIT;\n'
)
with open(r"C:\Users\jeffr\Downloads\Lifting\test_quick.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_quick.g"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting test at {time.strftime('%H:%M:%S')}...")
p = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime)
stdout, stderr = p.communicate(timeout=600)
print(f"Finished at {time.strftime('%H:%M:%S')}")
with open(log_file, "r") as f:
    for line in f.read().strip().split('\n'):
        if any(kw in line for kw in ['S10', 'PASS', 'FAIL', '[8,4]', 'time =']):
            print(line)
