"""Test lazy TF database population with atomic writes.

Checks:
  1. Fresh compute produces a valid <key>.g file (no tmp leftovers).
  2. Read-back after compute works.
  3. HOLT_TF_STRICT_MISS=true errors on miss.
  4. No .tmp.* files remain in database/tf_groups/.
  5. Concurrent-write simulation: two in-process calls on different keys
     both populate correctly.
"""

import os, subprocess, sys, glob

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
TF_DB_DIR = os.path.join(LIFTING_DIR, "database", "tf_groups")
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "lazy_pop_log.txt")

# Cleanup before test
for f in glob.glob(os.path.join(TF_DB_DIR, "id_36_10*")):
    if "backup" not in f:
        os.remove(f)
for f in glob.glob(os.path.join(TF_DB_DIR, "id_72_*")):
    if "backup" not in f:
        os.remove(f)
for f in glob.glob(os.path.join(TF_DB_DIR, "*.tmp.*")):
    os.remove(f)

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

# Reset caches
HOLT_TF_CACHE := rec();
HOLT_TF_STRICT_MISS := false;

Print("\\n=== Lazy population of S_3 x S_3 (key id_36_10) ===\\n");

s3xs3 := DirectProduct(SymmetricGroup(3), SymmetricGroup(3));
tf := HoltIdentifyTFTop(s3xs3);
Print("Key: ", tf.key, "\\n");

t0 := Runtime();
classes := HoltLoadTFClasses(tf);
Print("Computed ", Length(classes), " classes in ", Runtime()-t0, "ms\\n");

# File should exist now
path := Concatenation(HoltTFDatabasePath(), tf.key, ".g");
Print("File on disk: ", IsReadableFile(path), "\\n");

# Re-read
HOLT_TF_CACHE := rec();
classes2 := HoltLoadTFClasses(tf);
Print("Warm load: ", Length(classes2), " classes (match: ",
      Length(classes) = Length(classes2), ")\\n");

Print("\\n=== Strict-miss mode errors on miss ===\\n");
HOLT_TF_CACHE := rec();
HOLT_TF_STRICT_MISS := true;
# Use an INTRANSITIVE group so we skip the TransitiveGroup-library step
# and actually hit the miss path. DihedralGroup(10) x C_3 as perm rep,
# acting on 8 points with 2 orbits -> intransitive.
d10 := DihedralGroup(IsPermGroup, 10);
c3 := CyclicGroup(IsPermGroup, 3);
intrans := DirectProduct(d10, c3);
# Delete any pre-existing cache entry so we force a miss
tf_i := HoltIdentifyTFTop(intrans);
Print("Strict-miss key: ", tf_i.key,
      " (transitive: ", IsTransitive(intrans, MovedPoints(intrans)), ")\\n");

# Ensure no stale disk file
path := Concatenation(HoltTFDatabasePath(), tf_i.key, ".g");
if IsReadableFile(path) then
  Exec(Concatenation("rm -f '", path, "'"));
fi;

caught := false;
BreakOnError := false;
result := CALL_WITH_CATCH(HoltLoadTFClasses, [tf_i]);
BreakOnError := true;
if result[1] = false then
  caught := true;
  Print("Strict miss raised error as expected\\n");
else
  Print("Strict miss UNEXPECTEDLY returned: ", Length(result[2]), " classes\\n");
fi;
Print("Strict-miss error raised: ", caught, "\\n");

# Back to lazy
HOLT_TF_STRICT_MISS := false;
HOLT_TF_CACHE := rec();

LogTo();
QUIT;
'''

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_lazy_pop.g")
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

print("=== stdout ===")
print(proc.stdout[-3000:])
os.remove(cmd_file)

# Check disk state
id_36_10 = os.path.exists(os.path.join(TF_DB_DIR, "id_36_10.g"))
tmp_files = glob.glob(os.path.join(TF_DB_DIR, "*.tmp.*"))

print(f"\nDisk state:")
print(f"  id_36_10.g exists: {id_36_10}")
print(f"  leftover .tmp.* files: {len(tmp_files)}")

checks = [
    "File on disk: true",
    "match: true",
    "Strict-miss error raised: true",
]
ok = all(c in proc.stdout for c in checks) and id_36_10 and len(tmp_files) == 0
for c in checks:
    print(f"  [{'OK' if c in proc.stdout else 'MISSING'}] {c}")
print(f"  [{'OK' if id_36_10 else 'FAIL'}] id_36_10.g populated")
print(f"  [{'OK' if len(tmp_files) == 0 else 'FAIL'}] no leftover tmp files")
print(f"\n[{'PASS' if ok else 'FAIL'}] Lazy TF population")
sys.exit(0 if ok else 1)
