"""Launch worker 800 to finish [6,4,4,4]: 86 missing combos."""
import os
import subprocess
import time

OUTPUT_DIR = r"C:/Users/jeffr/Downloads/Lifting/parallel_s18"
WORKER_ID = 800
N = 18

log_file = f"{OUTPUT_DIR}/worker_{WORKER_ID}.log"
result_file = f"{OUTPUT_DIR}/worker_{WORKER_ID}_results.txt"
gens_dir = f"{OUTPUT_DIR}/gens"
ckpt_dir = f"{OUTPUT_DIR}/checkpoints/worker_{WORKER_ID}"
heartbeat_file = f"{OUTPUT_DIR}/worker_{WORKER_ID}_heartbeat.txt"

os.makedirs(ckpt_dir, exist_ok=True)
os.makedirs(gens_dir, exist_ok=True)

gap_code = f'''
LogTo("{log_file}");
Print("Worker {WORKER_ID} starting [6,4,4,4] resume\\n");

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

# Write summary
_totalClasses := 0;
_comboFiles := DirectoryContents(COMBO_OUTPUT_DIR);
for _cfName in _comboFiles do
    if Length(_cfName) > 2 and _cfName{{[Length(_cfName)-1..Length(_cfName)]}} = ".g" then
        _cfContent := StringFile(Concatenation(COMBO_OUTPUT_DIR, "/", _cfName));
        if _cfContent <> fail then
            for _cfLine in SplitString(_cfContent, "\\n") do
                if Length(_cfLine) > 0 and _cfLine[1] = '[' then
                    _totalClasses := _totalClasses + 1;
                fi;
            od;
        fi;
    fi;
od;
PrintTo(Concatenation(COMBO_OUTPUT_DIR, "/summary.txt"),
        "partition: [6,4,4,4]\\n",
        "total_classes: ", _totalClasses, "\\n",
        "session_added: ", Length(fpf_classes), "\\n",
        "elapsed_seconds: ", partTime, "\\n");

genFile := Concatenation("{gens_dir}", "/gens_6_4_4_4.txt");
PrintTo(genFile, "");
for _h_idx in [1..Length(fpf_classes)] do
    _gens := List(GeneratorsOfGroup(fpf_classes[_h_idx]),
                  g -> ListPerm(g, {N}));
    AppendTo(genFile, String(_gens), "\\n");
od;

AppendTo("{result_file}", "[6,4,4,4] ", String(Length(fpf_classes)), "\\n");
AppendTo("{result_file}", "TIME ", String(partTime), "\\n");
PrintTo("{heartbeat_file}", "completed [6,4,4,4] = ", Length(fpf_classes), " classes\\n");

if IsBound(SaveFPFSubdirectCache) then SaveFPFSubdirectCache(); fi;
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
    cmd,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
)
print(f"Launched W{WORKER_ID}, pid={p.pid}, log={log_file}")
