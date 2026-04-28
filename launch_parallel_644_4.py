"""Launch additional workers W801, W802 on [6,4,4,4] to parallelize.
Each worker iterates through combos and skips ones with existing files,
so they naturally split work via filesystem race."""
import os, subprocess

OUTPUT_DIR = r"C:/Users/jeffr/Downloads/Lifting/parallel_s18"
N = 18

def make_worker(wid):
    log_file = f"{OUTPUT_DIR}/worker_{wid}.log"
    result_file = f"{OUTPUT_DIR}/worker_{wid}_results.txt"
    gens_dir = f"{OUTPUT_DIR}/gens"
    ckpt_dir = f"{OUTPUT_DIR}/checkpoints/worker_{wid}"
    heartbeat_file = f"{OUTPUT_DIR}/worker_{wid}_heartbeat.txt"
    os.makedirs(ckpt_dir, exist_ok=True)
    os.makedirs(gens_dir, exist_ok=True)
    gap_code = f'''
LogTo("{log_file}");
Print("Worker {wid} starting [6,4,4,4]\\n");
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

part := [6,4,4,4];
COMBO_OUTPUT_DIR := "{OUTPUT_DIR}/[6,4,4,4]";
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
PrintTo("{heartbeat_file}", "starting partition [6,4,4,4]\\n");
partStart := Runtime();
fpf_classes := FindFPFClassesForPartition({N}, part);
partTime := (Runtime() - partStart) / 1000.0;
Print("=> ", Length(fpf_classes), " classes (", partTime, "s)\\n");
PrintTo("{heartbeat_file}", "completed [6,4,4,4]\\n");
LogTo();
QUIT;
'''
    script_file = f"{OUTPUT_DIR}/worker_{wid}.g"
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
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         env=env, cwd=r"C:\Program Files\GAP-4.15.1\runtime",
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    print(f"Launched W{wid}, pid={p.pid}")

for wid in [801, 802]:
    make_worker(wid)
