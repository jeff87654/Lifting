"""
run_s11_validation.py - Enumerate conjugacy classes S2-S11 with fix validation

Validates the cocycle/complement fixes by:
1. Running with CROSS_VALIDATE_COCYCLES := true for S2-S9 (fast enough)
2. Running S10-S11 with CROSS_VALIDATE_COCYCLES := false (performance)
3. Logging all output including any "invalid", "WARNING", "mismatch" messages
4. Comparing against known values

Known values (OEIS A000638):
  S2=2, S3=4, S4=11, S5=19, S6=56, S7=96, S8=296, S9=554, S10=1593, S11=3094
"""

import subprocess
import os
import sys
import time

gap_commands = r'''
LogTo("C:/Users/jeffr/Downloads/Lifting/s11_validation_output.txt");
Print("S11 Validation Test Run (with cocycle fix validation)\n");
Print("======================================================\n\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Phase 1: S2-S9 with cross-validation ON
# This verifies Pcgs and FP methods agree on all cocycle spaces
CROSS_VALIDATE_COCYCLES := true;
Print("\n\nPhase 1: S2-S9 with cross-validation ON\n");
Print("========================================\n\n");

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593, 3094];
allPassed := true;

for n in [2..9] do
    Print("\n========================================\n");
    Print("Testing S_", n, " (expected: ", known[n], ")\n");
    Print("========================================\n");
    startTime := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - startTime) / 1000.0;
    Print("\nS_", n, " Result: ", result, "\n");
    Print("Expected: ", known[n], "\n");
    if result = known[n] then
        Print("Status: PASS\n");
    else
        Print("Status: FAIL\n");
        allPassed := false;
    fi;
    Print("Time: ", elapsed, " seconds\n");
od;

# Phase 2: S10-S11 with cross-validation OFF (performance)
CROSS_VALIDATE_COCYCLES := false;
Print("\n\nPhase 2: S10-S11 with cross-validation OFF\n");
Print("============================================\n\n");

for n in [10..11] do
    Print("\n========================================\n");
    Print("Testing S_", n, " (expected: ", known[n], ")\n");
    Print("========================================\n");
    startTime := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - startTime) / 1000.0;
    Print("\nS_", n, " Result: ", result, "\n");
    Print("Expected: ", known[n], "\n");
    if result = known[n] then
        Print("Status: PASS\n");
    else
        Print("Status: FAIL\n");
        allPassed := false;
    fi;
    Print("Time: ", elapsed, " seconds\n");
od;

Print("\n\n========================================\n");
if allPassed then
    Print("ALL TESTS PASSED\n");
else
    Print("SOME TESTS FAILED\n");
fi;
Print("========================================\n");
LogTo();
QUIT;
'''

def main():
    print("Launching GAP to test S2-S11 with cocycle fix validation...")
    print("Output will be logged to s11_validation_output.txt")
    print()

    # Write GAP commands to a temporary file
    with open(r"C:\Users\jeffr\Downloads\Lifting\temp_s11_validation.g", "w") as f:
        f.write(gap_commands)

    # GAP paths
    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_s11_validation.g"

    # Set up environment for Cygwin
    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    start_time = time.time()

    try:
        print("Running GAP via Cygwin bash...")
        print("(S10 may take ~8 min, S11 may take significantly longer)")
        print()

        process = subprocess.Popen(
            [bash_exe, "--login", "-c",
             f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=gap_runtime
        )

        stdout, stderr = process.communicate(timeout=14400)  # 4 hour timeout

        elapsed = time.time() - start_time

        if stdout:
            print("Output:")
            print(stdout)
        if stderr:
            # Filter out syntax warnings (normal for GAP forward references)
            important_stderr = [line for line in stderr.split('\n')
                              if line.strip() and 'Syntax warning' not in line
                              and '^' not in line.strip()]
            if important_stderr:
                print("Errors:")
                print('\n'.join(important_stderr))

        print(f"\nTotal wall-clock time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        print(f"GAP exited with code: {process.returncode}")

        # Check output file
        output_file = r"C:\Users\jeffr\Downloads\Lifting\s11_validation_output.txt"
        if os.path.exists(output_file):
            print(f"\nFull log saved to: {output_file}")

            # Scan for diagnostic messages
            with open(output_file, 'r') as f:
                content = f.read()

            # Count diagnostic messages
            warnings = content.count("WARNING")
            invalid = content.count("invalid complements")
            mismatch = content.count("mismatch")
            fallback = content.count("falling back")

            print(f"\n--- Diagnostic Summary ---")
            print(f"  WARNING messages:          {warnings}")
            print(f"  Invalid complement events: {invalid}")
            print(f"  Cocycle space mismatches:   {mismatch}")
            print(f"  Fallback events:           {fallback}")

            if warnings == 0 and invalid == 0 and mismatch == 0 and fallback == 0:
                print("  => CLEAN RUN: No diagnostic issues detected!")
            else:
                print("  => ISSUES DETECTED: Review log for details")

            if "ALL TESTS PASSED" in content:
                print("\nFINAL RESULT: ALL TESTS PASSED")
            elif "SOME TESTS FAILED" in content:
                print("\nFINAL RESULT: SOME TESTS FAILED")
            else:
                print("\nFINAL RESULT: UNKNOWN (check log)")

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"\nProcess timed out after {elapsed:.0f} seconds")
        process.kill()
        stdout, _ = process.communicate()
        if stdout:
            print("Partial output:")
            print(stdout[-2000:])  # Last 2000 chars
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
