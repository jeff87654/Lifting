#!/usr/bin/env python3
"""
Run GAP test for lifting algorithm with logging
"""

import subprocess
from datetime import datetime
import sys

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
SCRIPT_PATH = "/cygdrive/c/Users/jeffr/Downloads/Lifting/run_test.g"
LOG_FILE = r"C:\Users\jeffr\Downloads\Lifting\gap_output.txt"

def main():
    print(f"Starting test at {datetime.now()}")
    print(f"Output will be logged to: {LOG_FILE}")
    print("=" * 70)

    cmd = [GAP_BASH, "--login", "-c", f'/opt/gap-4.15.1/gap -q "{SCRIPT_PATH}"']

    with open(LOG_FILE, "w") as log:
        log.write(f"# GAP Test Log\n")
        log.write(f"# Started at {datetime.now()}\n")
        log.write("=" * 70 + "\n\n")
        log.flush()

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in proc.stdout:
            print(line, end='')
            log.write(line)
            log.flush()

        proc.wait()

        log.write(f"\n# Finished at {datetime.now()}\n")
        log.write(f"# Exit code: {proc.returncode}\n")

    print()
    print("=" * 70)
    print(f"Finished at {datetime.now()}")
    print(f"Exit code: {proc.returncode}")
    print(f"Full log saved to: {LOG_FILE}")

    return proc.returncode

if __name__ == "__main__":
    sys.exit(main())
