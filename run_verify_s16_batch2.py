import subprocess
import os
import sys

partitions = [
    ([16], 1954),
    ([8,5,3], 3594),
    ([12,2,2], 3414),
]

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
part, expected = partitions[idx]
part_str = "_".join(str(x) for x in part)
script_path = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/verify_s16_{part_str}.g"

print(f"Running S16 partition {part} (expected: {expected})")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 4g "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=14400)
print(f"Exit code: {process.returncode}")

log_file = rf"C:\Users\jeffr\Downloads\Lifting\verify_s16_{part_str}.log"
if os.path.exists(log_file):
    with open(log_file) as f:
        content = f.read()
    lines = content.strip().split('\n')
    print(f"\n=== Log tail ({len(lines)} lines) ===")
    for line in lines[-15:]:
        print(line)
else:
    print(f"Log file not found: {log_file}")
