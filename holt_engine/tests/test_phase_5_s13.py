"""Phase 5 S13 regression: USE_HOLT_ENGINE + per-partition verification.

Run in background; expected runtime ~20-30 min.
"""

import os, re, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
REF_S13 = r"C:\Users\jeffr\Downloads\Symmetric Groups\Partition\s13_partition_classes_output.txt"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "phase_5_s13_log.txt")


def parse_reference(path):
    counts = {}
    with open(path) as f:
        for line in f:
            m = re.match(r"\[\s*([\d,\s]+)\s*\]\s*\|\s*(\d+)", line)
            if m:
                parts = tuple(int(x) for x in m.group(1).split(","))
                counts[parts] = int(m.group(2))
    return counts


def parse_gap_output(log_contents):
    pat = re.compile(
        r"Partition \[\s*([\d,\s]+)\s*\]:(.*?)=>\s*(\d+)\s+classes",
        re.DOTALL,
    )
    out = {}
    for m in pat.finditer(log_contents):
        parts = tuple(int(x) for x in m.group(1).split(","))
        out[parts] = int(m.group(3))
    return out


def run_s13():
    gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
if IsBound(LIFT_CACHE.("13")) then Unbind(LIFT_CACHE.("13")); fi;

s13_total := CountAllConjugacyClassesFast(13);
Print("\\nS13 total = ", s13_total, "\\n");

LogTo();
QUIT;
'''
    cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_phase_5_s13.g")
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
        text=True, env=env, timeout=7200,
    )
    os.remove(cmd_file)
    log_contents = ""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            log_contents = f.read()
    return proc, log_contents


if __name__ == "__main__":
    print("=== S13 regression (USE_HOLT_ENGINE=true) ===")
    proc, log = run_s13()
    reference = parse_reference(REF_S13)
    computed = parse_gap_output(log)
    fpf_ref = {p: v for p, v in reference.items() if 1 not in p}
    missing = set(fpf_ref) - set(computed)
    mismatches = [(p, fpf_ref[p], computed[p])
                  for p in sorted(fpf_ref.keys() & computed.keys())
                  if fpf_ref[p] != computed[p]]
    print(f"FPF ref: {len(fpf_ref)}  computed: {len(computed)}")
    print(f"Missing: {sorted(missing)}")
    print(f"Mismatches: {len(mismatches)}")
    for p, r, c in mismatches[:10]:
        print(f"  {p}: ref={r} got={c}")
    ok = ("S13 total = 20832" in proc.stdout) and not missing and not mismatches
    print(f"\n[{'PASS' if ok else 'FAIL'}] Phase 5 S13")
    sys.exit(0 if ok else 1)
