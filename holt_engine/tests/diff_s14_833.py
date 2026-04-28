"""Diff S_14 [8,3,3] partition between legacy and clean_first modes.

Two GAP runs: one with HOLT_ENGINE_MODE=legacy, one with clean_first.
Compare per-combo outputs to find which combo(s) lose classes.
"""

import os, subprocess, sys, re

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"


def run_gap(mode, log_file):
    gap_commands = f'''
LogTo("{log_file.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "{mode}";
Print("HOLT_ENGINE_MODE = ", HOLT_ENGINE_MODE, "\\n");

if IsBound(LIFT_CACHE.("14")) then Unbind(LIFT_CACHE.("14")); fi;
if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t0 := Runtime();
fpf := FindFPFClassesForPartition(14, [8,3,3]);
elapsed := (Runtime() - t0) / 1000.0;

Print("\\n[8,3,3] classes = ", Length(fpf), "\\n");
Print("Elapsed: ", elapsed, "s\\n");

LogTo();
QUIT;
'''
    cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests",
                             f"temp_diff_833_{mode}.g")
    with open(cmd_file, "w", encoding="utf-8") as f:
        f.write(gap_commands)

    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = cmd_file.replace("C:\\", "/cygdrive/c/").replace("\\", "/")
    gap_dir = '/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1'

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    if os.path.exists(log_file):
        os.remove(log_file)

    proc = subprocess.run(
        [bash_exe, "--login", "-c",
         f'cd "{gap_dir}" && ./gap.exe -q -o 0 "{script_path}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env, timeout=600,
    )
    os.remove(cmd_file)

    with open(log_file) as f:
        log = f.read()
    return proc, log


def parse_combo_counts(log):
    """Extract per-combo fpf counts. Format: 'combo: X candidates -> Y new (Z total)'."""
    result = []
    for m in re.finditer(
        r">> combo \[\[(.*?)\]\] factors.*?combo: (\d+) candidates -> (\d+) new",
        log, re.DOTALL
    ):
        combo_key = m.group(1).strip()
        candidates = int(m.group(2))
        added = int(m.group(3))
        result.append((combo_key, candidates, added))
    return result


if __name__ == "__main__":
    print("=== Legacy S_14 [8,3,3] ===")
    log_leg = os.path.join(LIFTING_DIR, "holt_engine", "tests",
                            "diff_833_legacy.log")
    p_leg, log_leg_contents = run_gap("legacy", log_leg)
    m = re.search(r"\[8,3,3\] classes = (\d+)", log_leg_contents)
    leg_total = int(m.group(1)) if m else None
    print(f"Legacy total: {leg_total}")

    print("\n=== Clean_first S_14 [8,3,3] ===")
    log_cf = os.path.join(LIFTING_DIR, "holt_engine", "tests",
                           "diff_833_clean.log")
    p_cf, log_cf_contents = run_gap("clean_first", log_cf)
    m = re.search(r"\[8,3,3\] classes = (\d+)", log_cf_contents)
    cf_total = int(m.group(1)) if m else None
    print(f"Clean_first total: {cf_total}")

    print(f"\nDiff: {leg_total - cf_total if leg_total and cf_total else 'N/A'}")

    leg_combos = parse_combo_counts(log_leg_contents)
    cf_combos = parse_combo_counts(log_cf_contents)

    print(f"\nLegacy combos: {len(leg_combos)}, Clean combos: {len(cf_combos)}")

    # Diff combo-by-combo
    leg_map = {c[0]: c for c in leg_combos}
    cf_map = {c[0]: c for c in cf_combos}
    all_keys = set(leg_map) | set(cf_map)

    diffs = []
    for k in sorted(all_keys):
        lv = leg_map.get(k)
        cv = cf_map.get(k)
        if lv is None or cv is None or lv[2] != cv[2]:
            diffs.append((k, lv, cv))

    print(f"\nDifferences: {len(diffs)}")
    for k, lv, cv in diffs[:20]:
        lc = lv[2] if lv else "?"
        cc = cv[2] if cv else "?"
        print(f"  {k}: legacy={lc}, clean={cc}")
