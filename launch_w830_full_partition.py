"""Launch W830 to run FindFPFClassesForPartition([6,4,4,4]) which will skip
the 527 existing combos and compute the 33 missing with proper incrementalDedup."""
import os, subprocess

OUTPUT_DIR = r"C:/Users/jeffr/Downloads/Lifting/parallel_s18"
WORKER_ID = 830

log_file = f"{OUTPUT_DIR}/worker_{WORKER_ID}.log"
ckpt_dir = f"{OUTPUT_DIR}/checkpoints/worker_{WORKER_ID}"
heartbeat_file = f"{OUTPUT_DIR}/worker_{WORKER_ID}_heartbeat.txt"
os.makedirs(ckpt_dir, exist_ok=True)

gap_code = f'''
LogTo("{log_file}");
Print("Worker {WORKER_ID} starting [6,4,4,4] full-partition rerun (proper incrementalDedup)\\n");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_DISABLE_DEDUP := true;  # legacy incrementalDedup does the work
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
CHECKPOINT_DIR := "{ckpt_dir}";
_HEARTBEAT_FILE := "{heartbeat_file}";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
COMBO_OUTPUT_DIR := "{OUTPUT_DIR}/[6,4,4,4]";
FPF_SUBDIRECT_CACHE := rec();
PrintTo("{heartbeat_file}", "starting [6,4,4,4]\\n");

t0 := Runtime();
fpf := FindFPFClassesForPartition(18, [6,4,4,4]);
t := (Runtime() - t0)/1000.0;
Print("=> ", Length(fpf), " classes (", t, "s)\\n");
PrintTo("{heartbeat_file}", "completed [6,4,4,4]\\n");
LogTo();
QUIT;
'''
script_file = f"{OUTPUT_DIR}/worker_{WORKER_ID}.g"
with open(script_file, "w") as f:
    f.write(gap_code)
script_cygwin = script_file.replace("C:/", "/cygdrive/c/")
env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'
cmd = [
    r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe",
    "--login", "-c",
    f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
    f'exec ./gap.exe -q -o 0 "{script_cygwin}"'
]
p = subprocess.Popen(
    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    env=env, cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
)
print(f"W{WORKER_ID} pid={p.pid}")
