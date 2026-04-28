"""Profile the stuck combo: partition [4,4,2,2,2] with T(4,2) x T(4,3) x C_2^3.

Runs with GAP ProfileGlobalFunctions for a time budget, then reports the
hot spots. Also runs a timed breakdown by layer.
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests",
                         "profile_slow_combo.log")


def run_gap():
    gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean_first";
Print("HOLT_ENGINE_MODE = ", HOLT_ENGINE_MODE, "\\n");

# Build P = T(4,2) x T(4,3) x C_2 x C_2 x C_2 on points 1..14.
# Partition [4,4,2,2,2]. This is the combo W8/W9/W10 hang on.
T1 := TransitiveGroup(4, 2);
T2 := ShiftGroup(TransitiveGroup(4, 3), 4);
T3 := ShiftGroup(TransitiveGroup(2, 1), 8);
T4 := ShiftGroup(TransitiveGroup(2, 1), 10);
T5 := ShiftGroup(TransitiveGroup(2, 1), 12);
P := Group(Concatenation(GeneratorsOfGroup(T1), GeneratorsOfGroup(T2),
                          GeneratorsOfGroup(T3), GeneratorsOfGroup(T4),
                          GeneratorsOfGroup(T5)));
shifted := [T1, T2, T3, T4, T5];
offsets := [0, 4, 8, 10, 12];
Npart := SymmetricGroup(14);
CURRENT_BLOCK_RANGES := [[1,4],[5,8],[9,10],[11,12],[13,14]];

Print("|P| = ", Size(P), "  |Npart| = ", Size(Npart), "\\n");

if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Watch which functions are hot. ProfileGlobalFunctions tracks
# cpu/wall time spent inside each listed function.
ProfileGlobalFunctions(true);
ProfileOperationsAndMethods(true);

_START := Runtime();
_last := _START;
_tick := function(label)
  Print("  [T+", (Runtime() - _START)/1000.0, "s, +",
        (Runtime() - _last)/1000.0, "s] ", label, "\\n");
  _last := Runtime();
end;

_tick("starting HoltFPFSubgroupClassesOfProduct");
fpf := HoltFPFSubgroupClassesOfProduct(P, shifted, offsets, Npart);
_tick(Concatenation("HoltFPF returned ", String(Length(fpf)), " classes"));

Print("\\nTotal elapsed: ", (Runtime() - _START)/1000.0, "s\\n");

# Report top-40 hot functions by time
Print("\\n=== Profile: top 40 hot functions ===\\n");
DisplayProfile();

LogTo();
QUIT;
'''
    cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests",
                             "temp_profile_slow.g")
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

    # Block until GAP exits. Use a very long timeout (it really can take
    # hours for pathological combos).
    try:
        proc = subprocess.run(
            [bash_exe, "--login", "-c",
             f'cd "{gap_dir}" && ./gap.exe -q -o 0 "{script_path}"'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env, timeout=7200,
        )
    finally:
        if os.path.exists(cmd_file):
            os.remove(cmd_file)
    return proc


if __name__ == "__main__":
    print("=== Profiling slow combo ===")
    print(f"Log: {LOG_FILE}")
    proc = run_gap()
    print(f"Exit code: {proc.returncode}")
    if proc.stderr:
        print(f"stderr tail: {proc.stderr[-1000:]}")
