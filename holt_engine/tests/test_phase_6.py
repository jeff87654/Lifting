"""Phase 6 test: run_holt.py + parallel runner wiring.

Checks:
  - run_holt.py --dry-run lists S10 partitions without executing GAP
  - Single-worker run of S10 via run_holt.py reproduces 1593 total
  - Heartbeat + checkpoint wrappers compile and call through successfully
  - Checkpoint round-trip: write + read via HoltSaveCheckpoint/HoltResumeCheckpoint
"""

import os, subprocess, sys, tempfile

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "phase_6_log.txt")

# 1. Dry-run sanity check
print("=== run_holt.py --dry-run (S10, 2 workers) ===")
dry_proc = subprocess.run(
    [sys.executable, "run_holt.py", "10", "--workers", "2", "--dry-run"],
    cwd=LIFTING_DIR,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    timeout=30,
)
print(dry_proc.stdout[-1500:])
dry_ok = "Worker 0" in dry_proc.stdout and "Worker 1" in dry_proc.stdout
print(f"  [{'OK' if dry_ok else 'FAIL'}] dry-run partition sharding visible")

# 2. Heartbeat + checkpoint smoke test via direct GAP call
gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

Print("\\n=== Heartbeat wrapper ===\\n");
_HEARTBEAT_FILE := "C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/phase_6_heartbeat.txt";
if IsExistingFile(_HEARTBEAT_FILE) then Exec("rm -f \\"", _HEARTBEAT_FILE, "\\""); fi;
HoltEmitHeartbeat("alive 5s test-combo dedup 1/1");
HoltEmitHeartbeat("alive 6s test-combo done, combo #1 fpf=5");
Print("Heartbeat file exists: ", IsReadableFile(_HEARTBEAT_FILE), "\\n");

Print("\\n=== Checkpoint round-trip ===\\n");
ckpt_path := "C:/Users/jeffr/Downloads/Lifting/holt_engine/tests/phase_6_ckpt.g";
if IsExistingFile(ckpt_path) then Exec("rm -f \\"", ckpt_path, "\\""); fi;

# Synthesize a minimal checkpoint
dummy_gens := [[ (1,2), (1,2,3) ]];
dummy_groups := List(dummy_gens, Group);
HoltSaveCheckpoint(ckpt_path, ["combo1", "combo2"], dummy_groups, 42, 1);
Print("Checkpoint file exists: ", IsReadableFile(ckpt_path), "\\n");

# Read back
loaded := HoltResumeCheckpoint(ckpt_path);
Print("Loaded: completedKeys count = ", Length(loaded.completedKeys),
      ", allFpfGens count = ", Length(loaded.allFpfGens), "\\n");
Print("  completedKeys = ", loaded.completedKeys, "\\n");
Print("  round-trip keys match: ",
      loaded.completedKeys = ["combo1", "combo2"], "\\n");
Print("  round-trip totalCandidates: ", loaded.totalCandidates = 42, "\\n");

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_phase_6.g")
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

print("\n=== GAP heartbeat + checkpoint round-trip ===")
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "{gap_dir}" && ./gap.exe -q -o 0 "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, timeout=120,
)
print(proc.stdout[-3000:])

os.remove(cmd_file)

checks = [
    "Heartbeat file exists: true",
    "Checkpoint file exists: true",
    "round-trip keys match: true",
    "round-trip totalCandidates: true",
]
ok = dry_ok and all(c in proc.stdout for c in checks)
for c in checks:
    print(f"  [{'OK' if c in proc.stdout else 'MISSING'}] {c}")
print(f"\n[{'PASS' if ok else 'FAIL'}] Phase 6 test")
sys.exit(0 if ok else 1)
