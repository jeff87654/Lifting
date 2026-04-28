"""Benchmark: D_4^3 fast path vs clean Holt pipeline.

Combo: [2,1] x [4,3] x [4,3] x [4,3] (S_14 partition [4,4,4,2]).
Clean_first routes to legacy D_4^3 cache (fast path #5).
Clean forces through HoltFPFSubgroupClassesOfProduct.

Reports both timings and class counts to verify correctness + speed delta.
"""

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

# Build P on points 1..14 with partition [4,4,4,2]
# Factor order chosen to match S_14 run ordering: T(4,3) repeated 3x plus C_2.
T1 := TransitiveGroup(4, 3);           # D_4 on {{1..4}}
T2 := ShiftGroup(TransitiveGroup(4, 3), 4);  # D_4 on {{5..8}}
T3 := ShiftGroup(TransitiveGroup(4, 3), 8);  # D_4 on {{9..12}}
T4 := ShiftGroup(TransitiveGroup(2, 1), 12); # C_2 on {{13,14}}
P := Group(Concatenation(GeneratorsOfGroup(T1), GeneratorsOfGroup(T2),
                          GeneratorsOfGroup(T3), GeneratorsOfGroup(T4)));
shifted := [T1, T2, T3, T4];
offsets := [0, 4, 8, 12];
Npart := SymmetricGroup(14);

Print("|P| = ", Size(P), "\\n");

CURRENT_BLOCK_RANGES := [[1,4],[5,8],[9,12],[13,14]];

if IsBound(FPF_SUBDIRECT_CACHE) then FPF_SUBDIRECT_CACHE := rec(); fi;
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

t0 := Runtime();
fpf := _HoltDispatchLift(P, shifted, offsets, Npart);
elapsed := (Runtime() - t0) / 1000.0;

Print("\\n_HoltDispatchLift returned ", Length(fpf), " classes\\n");
Print("Elapsed: ", elapsed, "s\\n");

filtered := Filtered(fpf, H -> IsFPFSubdirect(H, shifted, offsets));
Print("Post-filter IsFPFSubdirect: ", Length(filtered), "\\n");

LogTo();
QUIT;
'''
    cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests",
                             f"temp_bench_d4_{mode}.g")
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
        text=True, env=env, timeout=1800,
    )
    os.remove(cmd_file)

    with open(log_file) as f:
        log = f.read()
    return proc, log


if __name__ == "__main__":
    print("=== D_4^3 cache vs Holt clean pipeline benchmark ===\n")
    for mode in ("clean_first", "clean"):
        print(f"=== Mode: {mode} ===")
        log = os.path.join(LIFTING_DIR, "holt_engine", "tests",
                            f"bench_d4_{mode}.log")
        proc, contents = run_gap(mode, log)
        for line in contents.split("\n"):
            if any(k in line for k in
                   ["HoltDispatchLift returned", "Post-filter",
                    "|P|", "Elapsed", "D_4^3 cache", "fast path"]):
                print(f"  {line}")
        print()
