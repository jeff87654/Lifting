"""Single-threaded S1 -> S13 run through the clean Holt dispatcher.

Runs CountAllConjugacyClassesFast(13) fresh (caches cleared) with
USE_HOLT_ENGINE=true, routing through HoltFPFSubgroupClassesOfProduct
(clean pipeline with per-layer FPF pruning + legacy fallback for
§3.2-sized TF tops). Verifies OEIS values for every S_n.

Expected values (OEIS A000638):
  S1=1, S2=2, S3=4, S4=11, S5=19, S6=56, S7=96, S8=296,
  S9=554, S10=1593, S11=3094, S12=10723, S13=20832
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "s1_s13_clean_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_TF_STRICT_MISS := false;  # lazy population on

# Clear ALL caches for fresh timing
LIFT_CACHE := rec();
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
if IsBound(HOLT_TF_CACHE) then HOLT_TF_CACHE := rec(); fi;

Print("\\n=== S1 to S13 via clean Holt dispatcher ===\\n");
Print("USE_HOLT_ENGINE = ", USE_HOLT_ENGINE, "\\n");

overall_start := Runtime();
expected := rec(
  ("1") := 1, ("2") := 2, ("3") := 4, ("4") := 11, ("5") := 19,
  ("6") := 56, ("7") := 96, ("8") := 296, ("9") := 554, ("10") := 1593,
  ("11") := 3094, ("12") := 10723, ("13") := 20832);
all_pass := true;
for n in [1..13] do
  t0 := Runtime();
  got := CountAllConjugacyClassesFast(n);
  elapsed := Runtime() - t0;
  want := expected.(String(n));
  if got = want then
    Print("  S_", n, " = ", got, " PASS (", Int(elapsed/1000), "s)\\n");
  else
    Print("  S_", n, " = ", got, " FAIL (expected ", want, ", ",
          Int(elapsed/1000), "s)\\n");
    all_pass := false;
  fi;
od;

Print("\\nTotal S1-S13 wall-clock: ", Int((Runtime() - overall_start) / 1000),
      "s\\n");
Print("S1-S13 via clean dispatcher: ", all_pass, "\\n");

LogTo();
QUIT;
'''

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_s1_s13_clean.g")
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

print("=== stdout ===")
print(proc.stdout[-3000:])
os.remove(cmd_file)

ok = "S1-S13 via clean dispatcher: true" in proc.stdout
print(f"\n[{'PASS' if ok else 'FAIL'}] Single-thread S1-S13 clean dispatcher")
sys.exit(0 if ok else 1)
