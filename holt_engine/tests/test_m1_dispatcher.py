"""M1 smoke test: verify dispatcher routing with USE_HOLT_ENGINE=true.

Runs S_2..S_8 fresh via CountAllConjugacyClassesFast(8) with the new
"clean_first" default. Each S_n should match OEIS A000638 exactly.
Also verifies that _HoltIsLegacyFastPathCase routes correctly on a few
known fast-path cases (small abelian, Goursat-2, S_n-shortcircuit).
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "m1_dispatcher_log.txt")

EXPECTED = {
    2: 2, 3: 4, 4: 11, 5: 19, 6: 56, 7: 96, 8: 296
}


def run_gap():
    gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
Print("USE_HOLT_ENGINE = ", USE_HOLT_ENGINE, "\\n");
Print("HOLT_ENGINE_MODE = ", HOLT_ENGINE_MODE, "\\n\\n");

# Unit test fast-path detector
Print("=== Fast-path detector unit tests ===\\n");

# small abelian: C_2 x C_2 (|P|=4)
testP1 := Group((1,2), (3,4));
Print("C_2 x C_2 fast-path: ", _HoltIsLegacyFastPathCase(testP1, [Group((1,2)), Group((3,4))]), "\\n");

# small non-abelian: S_3 (|P|=6)
testP2 := Group((1,2,3), (1,2));
Print("S_3 (|P|=6, single factor) fast-path: ", _HoltIsLegacyFastPathCase(testP2, [testP2]), "\\n");

# 2-factor non-abelian: S_3 x S_3
S3a := Group((1,2,3), (1,2));
S3b := Group((4,5,6), (4,5));
testP3 := Group(Concatenation(GeneratorsOfGroup(S3a), GeneratorsOfGroup(S3b)));
Print("S_3 x S_3 fast-path (expect true): ",
      _HoltIsLegacyFastPathCase(testP3, [S3a, S3b]), "\\n");

# S_n in multi-factor: S_5 x S_2 x S_2 (natural S_5)
S5 := SymmetricGroup(5);
S2a := Group((6,7)); S2b := Group((8,9));
testP4 := Group(Concatenation(GeneratorsOfGroup(S5),
                              GeneratorsOfGroup(S2a),
                              GeneratorsOfGroup(S2b)));
Print("S_5 x S_2 x S_2 fast-path (expect true): ",
      _HoltIsLegacyFastPathCase(testP4, [S5, S2a, S2b]), "\\n");

Print("\\n=== S_2..S_8 fresh run (cached path, no LIFT_CACHE init) ===\\n");

# Clear any cached lift values
if IsBound(LIFT_CACHE) then
  LIFT_CACHE := rec();
fi;

t0 := Runtime();
s8_total := CountAllConjugacyClassesFast(8);
elapsed := (Runtime() - t0) / 1000.0;

Print("\\nS_8 total = ", s8_total, "\\n");
Print("Elapsed: ", elapsed, "s\\n");

# Print cumulative values
for n in [2..8] do
  if IsBound(LIFT_CACHE.(String(n))) then
    Print("  S_", n, " = ", LIFT_CACHE.(String(n)), "\\n");
  fi;
od;

LogTo();
QUIT;
'''
    cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_m1_dispatcher.g")
    with open(cmd_file, "w", encoding="utf-8") as f:
        f.write(gap_commands)

    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = cmd_file.replace("C:\\", "/cygdrive/c/").replace("\\", "/")
    gap_dir = '/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1'

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    proc = subprocess.run(
        [bash_exe, "--login", "-c",
         f'cd "{gap_dir}" && ./gap.exe -q -o 0 "{script_path}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env, timeout=600,
    )
    os.remove(cmd_file)

    log_contents = ""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            log_contents = f.read()
    return proc, log_contents


if __name__ == "__main__":
    print("=== Running M1 dispatcher smoke test ===")
    proc, log = run_gap()

    print("=== stdout (last 3K) ===")
    print(proc.stdout[-3000:])
    print("=== stderr (last 1K) ===")
    print(proc.stderr[-1000:] if proc.stderr else "(empty)")

    results = {}
    import re
    for m in re.finditer(r"S_(\d+) = (\d+)", log):
        n, v = int(m.group(1)), int(m.group(2))
        results[n] = v

    ok = True
    print("\n=== Results ===")
    for n in sorted(EXPECTED.keys()):
        actual = results.get(n)
        expected = EXPECTED[n]
        status = "PASS" if actual == expected else "FAIL"
        if actual != expected:
            ok = False
        print(f"  S_{n}: got {actual}, expected {expected}  [{status}]")

    # Check fast-path detector outputs
    expected_fp = {
        "C_2 x C_2 fast-path": "true",
        "S_3 (|P|=6, single factor) fast-path": "true",
        "S_3 x S_3 fast-path": "true",
        "S_5 x S_2 x S_2 fast-path": "true",
    }
    print("\n=== Fast-path detector ===")
    for label, expected_val in expected_fp.items():
        pat = re.escape(label) + r":\s*(\w+)"
        m = re.search(pat, log)
        actual_val = m.group(1) if m else "(not found)"
        status = "PASS" if actual_val == expected_val else "FAIL"
        if actual_val != expected_val:
            ok = False
        print(f"  {label}: got '{actual_val}', expected '{expected_val}'  [{status}]")

    print(f"\n[{'PASS' if ok else 'FAIL'}] M1 dispatcher smoke test")
    sys.exit(0 if ok else 1)
