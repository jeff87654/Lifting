"""Launch W840 to rerun the single missing [2,1]_[4,3]_[4,3]_[8,26] combo
in [8,4,4,2] via FindFPFClassesForPartition (which dedups properly)."""
import os, subprocess

OUTPUT_DIR = r"C:/Users/jeffr/Downloads/Lifting/parallel_s18"
WORKER_ID = 840
N = 18

log_file = f"{OUTPUT_DIR}/worker_{WORKER_ID}.log"
ckpt_dir = f"{OUTPUT_DIR}/checkpoints/worker_{WORKER_ID}"
heartbeat_file = f"{OUTPUT_DIR}/worker_{WORKER_ID}_heartbeat.txt"
os.makedirs(ckpt_dir, exist_ok=True)

gap_code = f'''
LogTo("{log_file}");
Print("Worker {WORKER_ID} starting [8,4,4,2] (rerun missing [2,1]_[4,3]_[4,3]_[8,26])\\n");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
HOLT_DISABLE_ISO_TRANSPORT := true;
HOLT_DISABLE_DEDUP := true;
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
CHECKPOINT_DIR := "{ckpt_dir}";
_HEARTBEAT_FILE := "{heartbeat_file}";
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
COMBO_OUTPUT_DIR := "{OUTPUT_DIR}/[8,4,4,2]";
FPF_SUBDIRECT_CACHE := rec();
PrintTo("{heartbeat_file}", "starting [8,4,4,2]\\n");

t0 := Runtime();
fpf := FindFPFClassesForPartition(18, [8,4,4,2]);
t := (Runtime() - t0)/1000.0;
Print("=> ", Length(fpf), " classes in ", t, "s\\n");
PrintTo("{heartbeat_file}", "completed [8,4,4,2]\\n");
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
