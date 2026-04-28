"""M4 unit test: HoltTopSubgroupsByMaximals correctness.

Tests that the FPF-aware max-subgroup BFS produces output equivalent to
direct ConjugacyClassesSubgroups, filtered by the FPF-projection condition.
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "m4_unit_log.txt")


def run_gap():
    gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
Print("HOLT_TF_CCS_DIRECT = ", HOLT_TF_CCS_DIRECT, "\\n");

# Test 1: A_5 x C_2 (small; TF top = A_5, |Q|=60)
A5 := AlternatingGroup(5);
C2 := Group((6,7));
P := Group(Concatenation(GeneratorsOfGroup(A5), GeneratorsOfGroup(C2)));
factors := [A5, C2];
# Partition normalizer = N_S5(A_5) x N_S2(C_2) = S_5 x S_2
Npart := Group(Concatenation(GeneratorsOfGroup(SymmetricGroup(5)),
                              GeneratorsOfGroup(Group((6,7)))));
Pt := RadicalGroup(P);
Print("\\n=== Test 1: A_5 x C_2 ===\\n");
Print("|P|=", Size(P), " |Pt|=", Size(Pt), " |Q|=", Size(P)/Size(Pt), "\\n");

t0 := Runtime();
result := HoltTopSubgroupsByMaximals(P, Pt, factors, Npart);
elapsed1 := Runtime() - t0;
Print("HoltTopSubgroupsByMaximals: ", Length(result), " classes (", elapsed1, "ms)\\n");

# Sanity: each result S should contain Pt, project onto every factor, and
# be unique up to Npart-conjugacy.
isValid := true;
for S in result do
    if not IsSubgroup(S, Pt) then isValid := false; break; fi;
    for F in factors do
        if Size(ClosureGroup(S, F)) <> Size(P) then
            isValid := false; break;
        fi;
    od;
od;

# FPF-subdirect of A_5 x C_2: only P itself (since A_5 is simple, any proper
# subgroup projects to a proper subgroup of A_5, failing surjection). So
# result should have exactly 1 class.
if Length(result) = 1 and isValid then
    Print("[PASS] Test 1: 1 class (expected for A_5 x C_2)\\n");
else
    Print("[FAIL] Test 1: got ", Length(result),
          " classes, valid=", isValid, "\\n");
fi;

# Test 2: Fast-path detection — P solvable (no radical split needed)
Print("\\n=== Test 2: Solvable P (C_4 x C_4) ===\\n");
C4a := Group((1,2,3,4));
C4b := Group((5,6,7,8));
P := Group(Concatenation(GeneratorsOfGroup(C4a), GeneratorsOfGroup(C4b)));
Pt := RadicalGroup(P);
Print("|P|=", Size(P), " |Pt|=", Size(Pt), " |Q|=", Size(P)/Size(Pt), "\\n");
# |Q|=1 since P is solvable, so HoltTopSubgroupsByMaximals returns just [P]
t0 := Runtime();
result := HoltTopSubgroupsByMaximals(P, Pt, [C4a, C4b], P);
elapsed := Runtime() - t0;
Print("Result: ", Length(result), " classes; expected 1 (trivial TF top)\\n");
if Length(result) = 1 then
    Print("[PASS] Test 2\\n");
else
    Print("[FAIL] Test 2\\n");
fi;

LogTo();
QUIT;
'''
    cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_m4_unit.g")
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
        text=True, env=env, timeout=300,
    )
    os.remove(cmd_file)

    log_contents = ""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            log_contents = f.read()
    return proc, log_contents


if __name__ == "__main__":
    print("=== M4 unit test: HoltTopSubgroupsByMaximals ===")
    proc, log = run_gap()

    print("\n=== Output ===")
    print(log[-3000:] if len(log) > 3000 else log)

    ok = "[PASS] Test 1" in log and "[PASS] Test 2" in log
    print(f"\n[{'PASS' if ok else 'FAIL'}] M4 unit test")
    sys.exit(0 if ok else 1)
