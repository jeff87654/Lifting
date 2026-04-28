"""Launch GAP to run conjugacy tests on bucketed groups."""
import subprocess
from datetime import datetime

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
SCRIPT = "/cygdrive/c/Users/jeffr/Downloads/Lifting/conjugacy_test.g"
LOG = r"C:\Users\jeffr\Downloads\Lifting\conjugacy_test_log.txt"

cmd = [GAP_BASH, "--login", "-c", f'/opt/gap-4.15.1/gap -q -o 8g "{SCRIPT}"']

print(f"Starting at {datetime.now()}")
with open(LOG, "w") as log:
    log.write(f"# Started at {datetime.now()}\n\n")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in proc.stdout:
        print(line, end='')
        log.write(line)
        log.flush()
    proc.wait()
    log.write(f"\n# Finished at {datetime.now()}\n")
    log.write(f"# Exit code: {proc.returncode}\n")
    print(f"\nFinished at {datetime.now()}, exit code: {proc.returncode}")
