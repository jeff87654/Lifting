"""
A/B test: Non-split test for central extensions only.

Variant A: Current code (non-split test DISABLED) - run S2-S10
Variant B: Non-split test ENABLED but ONLY when IsCentral(Q, M_bar) - run S2-S10

The hypothesis: The old non-split test (m_gen in DerivedSubgroup(Q) => skip)
was correct for CENTRAL extensions but wrong for NON-CENTRAL extensions.
For non-central extensions, complement existence is governed by H^1(G, M)
with non-trivial action, and m_gen in [Q,Q] does NOT imply non-split.

If both variants produce the same correct counts (S6=56, all match OEIS),
then the centrality-guarded non-split test is safe and gives us a speedup.
"""

import subprocess
import os
import time
import shutil
import re

# Paths
lifting_alg = r"C:\Users\jeffr\Downloads\Lifting\lifting_algorithm.g"
lifting_alg_backup = r"C:\Users\jeffr\Downloads\Lifting\lifting_algorithm.g.bak"
gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
log_file_a = "C:/Users/jeffr/Downloads/Lifting/debug_nonsplit_a.log"
log_file_b = "C:/Users/jeffr/Downloads/Lifting/debug_nonsplit_b.log"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

# ---- Text markers for the source code swap ----

# Variant A (current code): The disabled comment block
VARIANT_A_TEXT = """\
            # DISABLED: Fast non-split test for dim-1 layers
            # The test (m_gen in DerivedSubgroup(Q)) correctly identifies non-split
            # central C_p extensions, but needs further investigation for S6 failure.
            # TODO: debug why S6=55 with this enabled

            # Phase 2 Optimization: Early coprime termination (Schur-Zassenhaus)"""

# Variant B: Centrality-guarded non-split test
VARIANT_B_TEXT = """\
            # ENABLED: Fast non-split test for dim-1 layers (with centrality guard)
            # Only applies to CENTRAL extensions: 1 -> C_p -> Q -> G -> 1
            # where C_p <= Z(Q). For central extensions, the extension splits
            # iff the generator of C_p is NOT in [Q,Q].
            # For NON-CENTRAL extensions (C_p not in Z(Q)), complement existence
            # is governed by H^1(G, M) with non-trivial action, so this test
            # does NOT apply.
            if IsPrimeInt(Size(M_bar)) then
                m_gen := First(GeneratorsOfGroup(M_bar), g -> Order(g) > 1);
                if m_gen <> fail and ForAll(GeneratorsOfGroup(Q), q -> q*m_gen = m_gen*q) then
                    derivQ := DerivedSubgroup(Q);
                    if m_gen in derivQ then
                        # Central extension is non-split: no complements exist
                        numNonSplitSkips := numNonSplitSkips + 1;
                        t_complements := t_complements + (Runtime() - t0);
                        continue;
                    fi;
                fi;
            fi;

            # Phase 2 Optimization: Early coprime termination (Schur-Zassenhaus)"""


def make_gap_commands(log_file, label):
    return f'''
LogTo("{log_file}");
Print("=== {label} ===\\n");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches for a clean run
LIFT_CACHE := rec();
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];
allPass := true;

for n in [2..10] do
    Print("\\n========================================\\n");
    Print("Testing S_", n, " (expected: ", known[n], ")\\n");
    Print("========================================\\n");
    startTime := Runtime();
    result := CountAllConjugacyClassesFast(n);
    elapsed := (Runtime() - startTime);
    Print("\\nS_", n, " Result: ", result, "\\n");
    Print("Expected: ", known[n], "\\n");
    if result = known[n] then
        Print("Status: PASS\\n");
    else
        Print("Status: *** FAIL ***\\n");
        allPass := false;
    fi;
    Print("Time: ", elapsed, " ms\\n");
od;

Print("\\n========================================\\n");
if allPass then
    Print("ALL TESTS PASSED\\n");
else
    Print("SOME TESTS FAILED\\n");
fi;
Print("========================================\\n");
LogTo();
QUIT;
'''


def run_gap(label, log_file, cmd_file):
    """Run GAP with the given commands and return elapsed time."""
    gap_commands = make_gap_commands(log_file, label)

    with open(cmd_file, "w") as f:
        f.write(gap_commands)

    script_path = cmd_file.replace("\\", "/")
    script_path = script_path.replace("C:/Users/jeffr/Downloads/Lifting/",
                                      "/cygdrive/c/Users/jeffr/Downloads/Lifting/")

    print(f"\n{'='*60}")
    print(f"RUNNING: {label}")
    print(f"{'='*60}")
    start = time.time()

    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
    )

    stdout, stderr = process.communicate(timeout=7200)  # 2 hour timeout
    elapsed = time.time() - start
    print(f"GAP finished in {elapsed:.1f}s (return code: {process.returncode})")

    # Read and display log
    log_path = log_file.replace("/", os.sep)
    try:
        with open(log_path, "r") as f:
            log = f.read()

        # Print summary: results and pass/fail status
        print("\n--- Results ---")
        for line in log.split('\n'):
            line_s = line.strip()
            if any(kw in line_s for kw in ['Result:', 'Expected:', 'Status:', 'PASSED', 'FAILED',
                                            'nonsplit_skips', 'Testing S_']):
                print(f"  {line_s}")

    except FileNotFoundError:
        print("Log file not found!")
        print(f"STDOUT (first 3000 chars): {stdout[:3000]}")
        if stderr:
            print(f"STDERR: {stderr[:2000]}")

    return elapsed


def extract_results(log_file):
    """Extract S_n results from a log file."""
    log_path = log_file.replace("/", os.sep)
    try:
        with open(log_path, "r") as f:
            log = f.read()
    except FileNotFoundError:
        return {}

    results = {}
    # Match lines like "S_6 Result: 56"
    for match in re.finditer(r'S_(\d+) Result: (\d+)', log):
        n = int(match.group(1))
        count = int(match.group(2))
        results[n] = count

    # Count nonsplit skips
    nonsplit_count = len(re.findall(r'nonsplit_skips=(\d+)', log))
    nonsplit_total = sum(int(m.group(1)) for m in re.finditer(r'nonsplit_skips=(\d+)', log))

    return results, nonsplit_total


def main():
    print("=" * 60)
    print("A/B TEST: Non-split test with centrality guard")
    print("=" * 60)
    print()
    print("Hypothesis: The old non-split test (m_gen in [Q,Q] => skip)")
    print("was wrong for non-central extensions. Adding IsCentral(Q, M_bar)")
    print("guard should fix S6=55 bug while preserving the speedup.")
    print()

    # --- Step 1: Back up the source file ---
    print(f"Backing up {lifting_alg} ...")
    shutil.copy2(lifting_alg, lifting_alg_backup)
    print(f"  Backup saved to {lifting_alg_backup}")

    # Verify the marker text exists
    with open(lifting_alg, "r") as f:
        source = f.read()

    if VARIANT_A_TEXT not in source:
        print("ERROR: Could not find variant A marker text in lifting_algorithm.g!")
        print("The disabled non-split test comment block was not found.")
        print("Aborting.")
        return

    try:
        # --- Step 2: Run variant A (current code, non-split DISABLED) ---
        time_a = run_gap(
            "Variant A: Non-split test DISABLED (current code)",
            log_file_a,
            r"C:\Users\jeffr\Downloads\Lifting\temp_nonsplit_a.g"
        )

        # --- Step 3: Patch in variant B (centrality-guarded non-split test) ---
        print(f"\n{'='*60}")
        print("Patching lifting_algorithm.g for Variant B...")
        print("  Adding: IsCentral(Q, M_bar) guard to non-split test")
        print(f"{'='*60}")

        with open(lifting_alg, "r") as f:
            source = f.read()

        patched = source.replace(VARIANT_A_TEXT, VARIANT_B_TEXT)
        if patched == source:
            print("ERROR: Patch failed - marker text not found after variant A run!")
            return

        with open(lifting_alg, "w") as f:
            f.write(patched)
        print("  Patch applied successfully.")

        # --- Step 4: Run variant B (centrality-guarded non-split test) ---
        time_b = run_gap(
            "Variant B: Non-split test ENABLED (central only)",
            log_file_b,
            r"C:\Users\jeffr\Downloads\Lifting\temp_nonsplit_b.g"
        )

    finally:
        # --- Step 5: Restore backup (always, even on error) ---
        print(f"\n{'='*60}")
        print("Restoring original lifting_algorithm.g from backup...")
        shutil.copy2(lifting_alg_backup, lifting_alg)
        print("  Restored successfully.")
        # Clean up backup
        os.remove(lifting_alg_backup)
        print("  Backup removed.")

    # --- Step 6: Compare results ---
    print(f"\n{'='*60}")
    print("COMPARISON: A vs B")
    print(f"{'='*60}")

    known = {2: 1, 3: 2, 4: 4, 5: 11, 6: 19, 7: 56, 8: 96, 9: 296, 10: 554}
    # Note: OEIS A000638 uses different indexing; the values above correspond to
    # S2=1 class (trivial only? no) - actually let me use the values from run_test.py
    known = {2: 2, 3: 4, 4: 11, 5: 19, 6: 56, 7: 96, 8: 296, 9: 554, 10: 1593}

    results_a, nonsplit_a = extract_results(log_file_a)
    results_b, nonsplit_b = extract_results(log_file_b)

    print(f"\n{'n':>4} {'Expected':>10} {'Variant A':>12} {'Variant B':>12} {'A ok?':>8} {'B ok?':>8}")
    print("-" * 60)
    all_a_ok = True
    all_b_ok = True
    for n in range(2, 11):
        exp = known.get(n, '?')
        a_val = results_a.get(n, '?')
        b_val = results_b.get(n, '?')
        a_ok = "PASS" if a_val == exp else "FAIL"
        b_ok = "PASS" if b_val == exp else "FAIL"
        if a_val != exp:
            all_a_ok = False
        if b_val != exp:
            all_b_ok = False
        print(f"{n:>4} {exp:>10} {str(a_val):>12} {str(b_val):>12} {a_ok:>8} {b_ok:>8}")

    print(f"\nNon-split skips:  A={nonsplit_a},  B={nonsplit_b}")
    print(f"Wall time:        A={time_a:.1f}s,  B={time_b:.1f}s")
    if time_a > 0:
        speedup = (time_a - time_b) / time_a * 100
        print(f"Speedup B vs A:   {speedup:+.1f}%")

    print()
    if all_a_ok and all_b_ok:
        print("CONCLUSION: Both variants produce correct results.")
        print("The centrality-guarded non-split test is SAFE and can be enabled.")
        if nonsplit_b > 0:
            print(f"Variant B skipped {nonsplit_b} non-split central extensions.")
    elif all_a_ok and not all_b_ok:
        print("CONCLUSION: Variant B (centrality guard) still has bugs!")
        print("The IsCentral guard alone is not sufficient to fix the non-split test.")
    elif not all_a_ok:
        print("WARNING: Variant A (current code) also failed - check for other issues.")

    print()
    print(f"Full logs:")
    print(f"  A: {log_file_a.replace('/', os.sep)}")
    print(f"  B: {log_file_b.replace('/', os.sep)}")


if __name__ == "__main__":
    main()
