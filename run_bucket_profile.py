"""
Bucket size profiling runner for S12 [4,4,4] partition.

Profiles dedup bucket sizes and RepresentativeAction call counts
to understand the effectiveness of ComputeSubgroupInvariant bucketing.
"""

import subprocess
import os
import sys

def run_gap_profile():
    """Run GAP bucket profiling script."""

    print("Starting bucket size profiling for S12 [4,4,4]...")
    print("This will take several minutes...\n")

    # Paths
    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_bucket_profile.g"
    log_file = r"C:\Users\jeffr\Downloads\Lifting\gap_bucket_profile.log"

    # Clear log file
    if os.path.exists(log_file):
        os.remove(log_file)

    # Environment setup
    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    # Run GAP
    try:
        process = subprocess.Popen(
            [bash_exe, "--login", "-c",
             f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=gap_runtime
        )

        # Wait for completion (timeout after 30 minutes)
        stdout, stderr = process.communicate(timeout=1800)

        if process.returncode != 0:
            print(f"GAP exited with code {process.returncode}")
            if stderr:
                print(f"stderr: {stderr}")

        # Read and display results
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                log_content = f.read()
            print("\n" + "="*60)
            print("PROFILING RESULTS")
            print("="*60 + "\n")
            print(log_content)

            # Extract key metrics
            if "Total candidates processed:" in log_content:
                for line in log_content.split("\n"):
                    if "Conjugacy classes found:" in line:
                        print(f"\n>>> {line.strip()}")
                    elif "Total candidates processed:" in line:
                        print(f">>> {line.strip()}")
                    elif "Total RepresentativeAction calls:" in line:
                        print(f">>> {line.strip()}")
                    elif "Max bucket size:" in line:
                        print(f">>> {line.strip()}")
                    elif "Average RA calls per candidate:" in line:
                        print(f">>> {line.strip()}")
                    elif "Dedup overhead:" in line:
                        print(f">>> {line.strip()}")
        else:
            print(f"Log file not found: {log_file}")

    except subprocess.TimeoutExpired:
        print("Process timed out after 30 minutes")
        process.kill()
        return 1
    except Exception as e:
        print(f"Error running GAP: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(run_gap_profile())
