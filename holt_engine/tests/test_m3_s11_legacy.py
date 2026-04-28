"""S_11 with HOLT_ENGINE_MODE=legacy for fresh baseline comparison."""

import os, subprocess, sys, time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "m3_s11_legacy_log.txt")


def run_gap():
    gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "legacy";
Print("HOLT_ENGINE_MODE = ", HOLT_ENGINE_MODE, "\\n");

if IsBound(LIFT_CACHE) and IsBound(LIFT_CACHE.("11")) then
  Unbind(LIFT_CACHE.("11"));
fi;
if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t0 := Runtime();
s11_total := CountAllConjugacyClassesFast(11);
elapsed := (Runtime() - t0) / 1000.0;

Print("\\nS_11 total = ", s11_total, "\\n");
Print("Elapsed: ", elapsed, "s\\n");

LogTo();
QUIT;
'''
    cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_m3_s11_legacy.g")
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

    t0 = time.time()
    proc = subprocess.run(
        [bash_exe, "--login", "-c",
         f'cd "{gap_dir}" && ./gap.exe -q -o 0 "{script_path}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env, timeout=600,
    )
    wall = time.time() - t0
    os.remove(cmd_file)

    log_contents = ""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            log_contents = f.read()
    return proc, log_contents, wall


if __name__ == "__main__":
    print("=== S_11 legacy-mode baseline ===")
    proc, log, wall = run_gap()

    print(f"Wall clock: {wall:.1f}s")
    print(proc.stdout[-800:])

    import re
    m = re.search(r"S_11 total = (\d+)", log)
    total = int(m.group(1)) if m else None
    m2 = re.search(r"Elapsed:\s*([\d.]+)\s*s", log)
    gap_elapsed = float(m2.group(1)) if m2 else None

    ok = (total == 3094)
    print(f"\nS_11 total: {total} (expected 3094)")
    print(f"GAP runtime (legacy): {gap_elapsed}s")
    print(f"[{'PASS' if ok else 'FAIL'}] S_11 legacy baseline")
    sys.exit(0 if ok else 1)
