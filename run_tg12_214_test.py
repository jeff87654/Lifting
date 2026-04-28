import subprocess, os, time
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && exec ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_tg12_214.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
stdout, stderr = p.communicate(timeout=120)
print("RC:", p.returncode)
log = r"C:\Users\jeffr\Downloads\Lifting\test_tg12_214.log"
if os.path.exists(log):
    with open(log) as f:
        content = f.read()
    # Print only the actual test output (skip syntax warnings)
    for line in content.split('\n'):
        if line.startswith('===') or line.startswith('P ') or line.startswith('  ') or line.startswith('Series') or line.startswith('Layer') or line.startswith('Result') or line.startswith('---') or 'BUG' in line or 'Layer' in line or 'order' in line:
            print(line)
