"""Quick test: inter-layer dedup on S12 partitions with cache."""
import subprocess, os, time

log_file = "C:/Users/jeffr/Downloads/Lifting/test_interlayer.log"

# Build GAP commands with string concatenation (no f-strings with \n)
lines = []
lines.append('LogTo("' + log_file + '");')
lines.append('Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");')
lines.append('Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");')
# Test [6,4,2] of S12 (expected 1126, exercises 5-part chief series with C_2 layers)
lines.append('if IsBound(ClearH1Cache) then ClearH1Cache(); fi;')
lines.append('FPF_SUBDIRECT_CACHE := rec();')
lines.append('startTime := Runtime();')
lines.append('r := FindFPFClassesForPartition(12, [6,4,2]);')
lines.append('elapsed := (Runtime() - startTime) / 1000.0;')
lines.append('Print("[6,4,2] = ", Length(r), " (expected 1126), time = ", elapsed, "s\n");')
lines.append('if Length(r) = 1126 then Print("[6,4,2] PASS\n"); else Print("[6,4,2] FAIL!\n"); fi;')
# Test [4,4,2,2] of S12 (expected 2367, exercises repeated parts with C_2 explosion)
lines.append('if IsBound(ClearH1Cache) then ClearH1Cache(); fi;')
lines.append('FPF_SUBDIRECT_CACHE := rec();')
lines.append('startTime := Runtime();')
lines.append('r := FindFPFClassesForPartition(12, [4,4,2,2]);')
lines.append('elapsed := (Runtime() - startTime) / 1000.0;')
lines.append('Print("[4,4,2,2] = ", Length(r), " (expected 2367), time = ", elapsed, "s\n");')
lines.append('if Length(r) = 2367 then Print("[4,4,2,2] PASS\n"); else Print("[4,4,2,2] FAIL!\n"); fi;')
lines.append('LogTo();')
lines.append('QUIT;')

gap_commands = '\n'.join(lines) + '\n'

with open(r"C:\Users\jeffr\Downloads\Lifting\test_interlayer.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_interlayer.g"
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting test at {time.strftime('%H:%M:%S')}...")
p = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime)
stdout, stderr = p.communicate(timeout=1200)
print(f"Finished at {time.strftime('%H:%M:%S')}")
with open(log_file, "r") as f:
    for line in f.read().strip().split('\n'):
        if any(kw in line for kw in ['PASS', 'FAIL', '= ', 'Inter-layer', 'time =']):
            print(line)
