"""Single-thread S11 -> S12 -> S13 sweep through the clean Holt dispatcher.

Verifies that after the ChatGPT-flagged fixes (product series, module-first
orbit reduction, partNormalizer respected), the end-to-end counts still
match OEIS A000638: S11=3094, S12=10723, S13=20832.

Runs in the background; heartbeat via _HEARTBEAT_FILE; per-degree timing
logged. Each degree clears caches before running so the timing reflects
a cold path.
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "s11_s12_s13_clean_log.txt")
HB_FILE = os.path.join(LIFTING_DIR, "s11_s12_s13_clean_hb.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";   # clean pipeline first, fallback to max-rec, then legacy
HOLT_TF_STRICT_MISS := false;
_HEARTBEAT_FILE := "{HB_FILE.replace(os.sep, "/")}";

expected := rec(("11") := 3094, ("12") := 10723, ("13") := 20832);

run_degree := function(n)
  local t0, count, elapsed, key;
  # Clear caches for cold-path timing
  FPF_SUBDIRECT_CACHE := rec();
  LIFT_CACHE := rec();
  # Reload S1..n-1 counts from disk so we don't recompute them
  Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
  if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
  # Drop this degree and above so CountAllConjugacyClassesFast recomputes
  for key in RecNames(LIFT_CACHE) do
    if Int(key) >= n then
      Unbind(LIFT_CACHE.(key));
    fi;
  od;
  Print("\\n========== S_", n, " ==========\\n");
  t0 := Runtime();
  count := CountAllConjugacyClassesFast(n);
  elapsed := Runtime() - t0;
  Print("S_", n, " = ", count, " (expect ", expected.(String(n)),
        ", elapsed ", Int(elapsed/1000), "s)\\n");
  Print("  match: ", count = expected.(String(n)), "\\n");
  return [count, elapsed];
end;

# Run S11, S12, S13 sequentially
r11 := run_degree(11);
r12 := run_degree(12);
r13 := run_degree(13);

Print("\\n========== SUMMARY ==========\\n");
Print("S_11 = ", r11[1], " (", Int(r11[2]/1000), "s, expect 3094)  match: ", r11[1] = 3094, "\\n");
Print("S_12 = ", r12[1], " (", Int(r12[2]/1000), "s, expect 10723) match: ", r12[1] = 10723, "\\n");
Print("S_13 = ", r13[1], " (", Int(r13[2]/1000), "s, expect 20832) match: ", r13[1] = 20832, "\\n");
all_ok := r11[1] = 3094 and r12[1] = 10723 and r13[1] = 20832;
Print("ALL PASS: ", all_ok, "\\n");

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "temp_s11_s13_clean.g")
with open(cmd_file, "w", encoding="utf-8") as f:
    f.write(gap_commands)

bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = cmd_file.replace("C:\\", "/cygdrive/c/").replace("\\", "/")
gap_dir = '/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1'

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

for f in (LOG_FILE, HB_FILE):
    if os.path.exists(f):
        os.remove(f)

# No timeout: S13 could take hours through the clean pipeline
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "{gap_dir}" && ./gap.exe -q -o 0 "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env,
)

print("=== stdout tail ===")
print(proc.stdout[-3000:])

if os.path.exists(cmd_file):
    os.remove(cmd_file)

ok = "ALL PASS: true" in proc.stdout
print(f"\n[{'PASS' if ok else 'FAIL'}] S11-S13 clean sweep")
sys.exit(0 if ok else 1)
