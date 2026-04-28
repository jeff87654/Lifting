"""Isolate the T(3,2) x T(3,2) x T(8,22) combo bug."""

import os, subprocess, sys, re

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"


def run_gap(mode, log_file):
    gap_commands = f'''
LogTo("{log_file.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "{mode}";
Print("HOLT_ENGINE_MODE = ", HOLT_ENGINE_MODE, "\\n");

# Build P = T(3,2) x T(3,2) x T(8,22) on points 1..14
T1 := TransitiveGroup(3, 2);   # S_3 on {{1,2,3}}
T2 := ShiftGroup(TransitiveGroup(3, 2), 3);  # S_3 on {{4,5,6}}
T3 := ShiftGroup(TransitiveGroup(8, 22), 6); # T(8,22) on {{7..14}}
P := Group(Concatenation(GeneratorsOfGroup(T1),
                          GeneratorsOfGroup(T2),
                          GeneratorsOfGroup(T3)));
shifted := [T1, T2, T3];
offsets := [0, 3, 6];
Npart := SymmetricGroup(14);  # broadest normalizer for simplicity

Print("|P| = ", Size(P), "\\n");
Print("|T(8,22)| = ", Size(TransitiveGroup(8,22)), "\\n");

# Set CURRENT_BLOCK_RANGES for the dedup
CURRENT_BLOCK_RANGES := [[1,3],[4,6],[7,14]];

if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t0 := Runtime();
fpf := _HoltDispatchLift(P, shifted, offsets, Npart);
elapsed := (Runtime() - t0) / 1000.0;

Print("\\n_HoltDispatchLift returned ", Length(fpf), " classes\\n");
Print("Elapsed: ", elapsed, "s\\n");

# Filter to verify FPF-subdirect
fpf_filtered := Filtered(fpf, H -> IsFPFSubdirect(H, shifted, offsets));
Print("Post-filter IsFPFSubdirect count: ", Length(fpf_filtered), "\\n");

# Orders
orders := SortedList(List(fpf_filtered, Size));
Print("Class orders: ", orders, "\\n");

LogTo();
QUIT;
'''
    cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests",
                             f"temp_combo_{mode}.g")
    with open(cmd_file, "w", encoding="utf-8") as f:
        f.write(gap_commands)

    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = cmd_file.replace("C:\\", "/cygdrive/c/").replace("\\", "/")
    gap_dir = '/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1'

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    if os.path.exists(log_file):
        os.remove(log_file)

    proc = subprocess.run(
        [bash_exe, "--login", "-c",
         f'cd "{gap_dir}" && ./gap.exe -q -o 0 "{script_path}"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env, timeout=300,
    )
    os.remove(cmd_file)

    with open(log_file) as f:
        log = f.read()
    return proc, log


if __name__ == "__main__":
    for mode in ("legacy", "clean_first", "clean"):
        print(f"\n=== Mode: {mode} ===")
        log = os.path.join(LIFTING_DIR, "holt_engine", "tests",
                            f"combo_{mode}.log")
        proc, contents = run_gap(mode, log)

        print("=== Relevant output ===")
        for line in contents.split("\n"):
            if any(k in line for k in
                   ["HoltDispatchLift returned", "Post-filter", "Class orders",
                    "|P|", "|T(8,22)|", "Elapsed"]):
                print(f"  {line}")
