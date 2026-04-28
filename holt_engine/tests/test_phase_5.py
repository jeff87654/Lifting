"""Phase 5 test: S12 + S13 per-partition regression with USE_HOLT_ENGINE=true.

Compares per-partition FPF counts from CountAllConjugacyClassesFast output
against the brute-force reference files:
  C:\\Users\\jeffr\\Downloads\\Symmetric Groups\\Partition\\s12_partition_classes_output.txt
  C:\\Users\\jeffr\\Downloads\\Symmetric Groups\\Partition\\s13_partition_classes_output.txt

Success: total matches OEIS (S12=10723, S13=20832) AND every FPF partition
count matches the reference.
"""

import os, re, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
REF_S12 = r"C:\Users\jeffr\Downloads\Symmetric Groups\Partition\s12_partition_classes_output.txt"
REF_S13 = r"C:\Users\jeffr\Downloads\Symmetric Groups\Partition\s13_partition_classes_output.txt"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "phase_5_log.txt")


def parse_reference(path):
    """Parse lines like '[ 12 ]     | 301' -> {(12,): 301, ...}"""
    counts = {}
    with open(path) as f:
        for line in f:
            m = re.match(r"\[\s*([\d,\s]+)\s*\]\s*\|\s*(\d+)", line)
            if m:
                parts = tuple(int(x) for x in m.group(1).split(","))
                counts[parts] = int(m.group(2))
    return counts


def parse_gap_output(log_contents):
    """Parse 'Partition [ 12 ]:\n ... \n  => 301 classes' from GAP output.

    There can be hundreds of combo lines between the 'Partition ...:' header
    and the '  => N classes' total, so use a DOTALL regex to skip past them.
    """
    pat = re.compile(
        r"Partition \[\s*([\d,\s]+)\s*\]:(.*?)=>\s*(\d+)\s+classes",
        re.DOTALL,
    )
    out = {}
    for m in pat.finditer(log_contents):
        parts = tuple(int(x) for x in m.group(1).split(","))
        out[parts] = int(m.group(3))
    return out


def run_s12():
    """Run S12 with USE_HOLT_ENGINE=true, return log contents."""
    gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
Print("USE_HOLT_ENGINE = ", USE_HOLT_ENGINE, "\\n");

# Clear LIFT_CACHE.12 so we force computation, but keep S1-S11 cached
if IsBound(LIFT_CACHE) and IsBound(LIFT_CACHE.("12")) then
  Unbind(LIFT_CACHE.("12"));
fi;

s12_total := CountAllConjugacyClassesFast(12);
Print("\\nS12 total = ", s12_total, "\\n");

LogTo();
QUIT;
'''
    cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_phase_5.g")
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
        text=True, env=env, timeout=3600,
    )
    os.remove(cmd_file)

    log_contents = ""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            log_contents = f.read()
    return proc, log_contents


if __name__ == "__main__":
    print("=== Running S12 with USE_HOLT_ENGINE=true ===")
    proc, log = run_s12()

    print("=== stdout (last 2K) ===")
    print(proc.stdout[-2000:])
    print("=== stderr (last 1K) ===")
    print(proc.stderr[-1000:] if proc.stderr else "(empty)")

    reference = parse_reference(REF_S12)
    computed = parse_gap_output(log)

    # FPF partitions of 12: no 1-parts in partition
    fpf_ref = {p: v for p, v in reference.items() if 1 not in p}
    print(f"\nReference FPF partitions of S12: {len(fpf_ref)}")
    print(f"Computed partitions:             {len(computed)}")

    missing = set(fpf_ref.keys()) - set(computed.keys())
    extra = set(computed.keys()) - set(fpf_ref.keys())
    mismatches = []
    for p in sorted(set(fpf_ref.keys()) & set(computed.keys())):
        if fpf_ref[p] != computed[p]:
            mismatches.append((p, fpf_ref[p], computed[p]))

    print(f"Missing in computed: {sorted(missing)}")
    print(f"Extra in computed:   {sorted(extra)}")
    print(f"Mismatches:          {len(mismatches)}")
    for p, r, c in mismatches[:10]:
        print(f"  {p}: ref={r} computed={c}")

    ok = (
        "S12 total = 10723" in proc.stdout
        and not missing
        and not mismatches
    )
    print(f"\n[{'PASS' if ok else 'FAIL'}] Phase 5 (S12 only)")
    sys.exit(0 if ok else 1)
