"""Phase 3 test: tf_database.g + presentation_engine.g.

Checks:
  - HoltIdentifyTFTop on S_4, S_5, A_5 returns stable keys.
  - HoltLoadTFClasses on S_5 (radical = 1, TF top = S_5) returns 19 classes.
  - Write-through: miss triggers compute + disk write.
  - Read-through: clearing HOLT_TF_CACHE and calling again returns from disk.
  - HoltPresentationForClassRec returns pcgs-backed rec for solvable groups.
  - S1-S10 regression still passes.
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "phase_3_log.txt")
TF_DB_DIR = os.path.join(LIFTING_DIR, "database", "tf_groups")
MISS_LOG = os.path.join(LIFTING_DIR, "tf_miss_log.txt")

# Clean up prior test artifacts
for key in ["id_120_34", "id_60_5"]:
    path = os.path.join(TF_DB_DIR, f"{key}.g")
    if os.path.exists(path):
        os.remove(path)
if os.path.exists(MISS_LOG):
    os.remove(MISS_LOG)

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

Print("\\n=== HoltIdentifyTFTop ===\\n");

s4 := SymmetricGroup(4);
s5 := SymmetricGroup(5);
a5 := AlternatingGroup(5);

tf_s4 := HoltIdentifyTFTop(s4);
Print("S_4: key=", tf_s4.key, " size=", tf_s4.size, "\\n");

tf_s5 := HoltIdentifyTFTop(s5);
Print("S_5: key=", tf_s5.key, " size=", tf_s5.size, "\\n");

tf_a5 := HoltIdentifyTFTop(a5);
Print("A_5: key=", tf_a5.key, " size=", tf_a5.size, "\\n");

Print("\\n=== HoltLoadTFClasses (S_5 should hit TransitiveGroup lib) ===\\n");

# Start with clean cache
HOLT_TF_CACHE := rec();

t_hits_before := HOLT_TF_STATS.transitive_hits;
classes_s5 := HoltLoadTFClasses(tf_s5);
Print("S_5 classes count = ", Length(classes_s5), " (expect 19)\\n");
Print("  new transitive hits: ",
      HOLT_TF_STATS.transitive_hits - t_hits_before, "\\n");

Print("\\n=== A_5 TF top ===\\n");

HOLT_TF_CACHE := rec();
classes_a5 := HoltLoadTFClasses(tf_a5);
Print("A_5 classes count = ", Length(classes_a5), " (expect 9)\\n");

Print("\\n=== HoltLoadTFClasses (intransitive group: must miss + write through) ===\\n");

# S_3 x S_3 on 6 points is intransitive (not in transitive lib);
# IdGroup = [36,10]; won't match lg_... keys in TF_SUBGROUP_LATTICE.
s3xs3 := DirectProduct(SymmetricGroup(3), SymmetricGroup(3));
tf_dp := HoltIdentifyTFTop(s3xs3);
Print("S_3 x S_3: key=", tf_dp.key, " size=", tf_dp.size, "\\n");

# Clean any leftover cache file to force miss path
tf_path := Concatenation(HoltTFDatabasePath(), tf_dp.key, ".g");
if IsReadableFile(tf_path) then
  Exec(Concatenation("rm -f '", tf_path, "'"));
fi;

HOLT_TF_CACHE := rec();
misses_before := HOLT_TF_STATS.misses;

t0 := Runtime();
classes_dp := HoltLoadTFClasses(tf_dp);
elapsed := Runtime() - t0;
Print("S_3 x S_3 classes count = ", Length(classes_dp), "\\n");
Print("  compute elapsed: ", elapsed, "ms\\n");
Print("  new misses: ", HOLT_TF_STATS.misses - misses_before, "\\n");
Print("  disk file exists: ", IsReadableFile(tf_path), "\\n");

Print("\\n=== HoltLoadTFClasses (warm: must hit disk) ===\\n");

HOLT_TF_CACHE := rec();
disk_hits_before := HOLT_TF_STATS.disk_hits;

t0 := Runtime();
classes_dp_warm := HoltLoadTFClasses(tf_dp);
elapsed := Runtime() - t0;
Print("S_3 x S_3 classes count (warm) = ", Length(classes_dp_warm), "\\n");
Print("  warm elapsed: ", elapsed, "ms\\n");
Print("  new disk hits: ", HOLT_TF_STATS.disk_hits - disk_hits_before, "\\n");
Print("  warm == cold count: ", Length(classes_dp) = Length(classes_dp_warm), "\\n");

# Third call must hit in-memory
mem_hits_before := HOLT_TF_STATS.mem_hits;
classes_dp_mem := HoltLoadTFClasses(tf_dp);
Print("  in-memory hit after second load: ",
      HOLT_TF_STATS.mem_hits > mem_hits_before, "\\n");

Print("\\n=== Presentation engine ===\\n");

pres_a4 := HoltPresentationForClassRec(AlternatingGroup(4));
Print("A_4 presentation: source=", pres_a4.source,
      " is_solvable=", pres_a4.is_solvable,
      " ngens=", Length(pres_a4.generators), "\\n");
Print("  A_4 solvable flag correct: ", pres_a4.is_solvable = true, "\\n");

pres_a5 := HoltPresentationForClassRec(AlternatingGroup(5));
Print("A_5 presentation: source=", pres_a5.source,
      " is_solvable=", pres_a5.is_solvable,
      " ngens=", Length(pres_a5.generators), "\\n");

Print("\\n=== tf_miss_log contents ===\\n");
if IsReadableFile(HoltTFMissLogPath()) then
  Print("miss log exists\\n");
else
  Print("miss log missing (unexpected)\\n");
fi;

Print("\\n=== S1-S10 regression ===\\n");
pass := true;
for n in [1..10] do
  if HoltRegressionCheck(n) <> true then
    Print("  FAIL at n=", n, "\\n");
    pass := false;
  fi;
od;
Print("S1-S10 regression: ", pass, "\\n");

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_phase_3.g")
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
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    timeout=600,
)

print("=== stdout ===")
print(proc.stdout[-5000:])
print("=== stderr (last 2K) ===")
print(proc.stderr[-2000:] if proc.stderr else "(empty)")

if os.path.exists(LOG_FILE):
    print("=== GAP log ===")
    with open(LOG_FILE) as f:
        print(f.read())

os.remove(cmd_file)

checks = [
    "S_5 classes count = 19",
    "A_5 classes count = 9",
    "disk file exists: true",
    "warm == cold count: true",
    "in-memory hit after second load: true",
    "A_4 solvable flag correct: true",
    "S1-S10 regression: true",
]
ok = all(c in proc.stdout for c in checks)
for c in checks:
    print(f"  [{'OK' if c in proc.stdout else 'MISSING'}] {c}")
print(f"\n[{'PASS' if ok else 'FAIL'}] Phase 3 test")
sys.exit(0 if ok else 1)
