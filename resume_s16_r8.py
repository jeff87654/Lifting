"""
S16 Round 8: Restart [4,4,4,4] with fixed GF(2) BFS queue.

W52 was killed (stuck in O(n^2) BFS due to Remove(todo,1)).
W57 resumes [4,4,4,4] from checkpoint (worker_45) with fixed code.

Also launches W58 to re-run the failed C_2^8 combos from W53/W54:
  - [4,4,4,2,2] combo [[4,2],[4,2],[4,2],[2,1],[2,1]] (combo #16)
  - [4,4,2,2,2,2] combo [[4,2],[4,2],[2,1],[2,1],[2,1],[2,1]] (combo #6)
These combos failed with list access errors in the old code.

Still running: W43 (PID 63860, [8,8]), W47 (PID 55688, [8,4,4])
              W53 (non-C2^8 combos of [4,4,4,2,2]), W54 (non-C2^8 combos of [4,4,2,2,2,2])
              W55 ([6,4,2,2,2])
"""

import subprocess
import os
import sys
import time
import shutil

BASE_DIR = r"C:\Users\jeffr\Downloads\Lifting"
PARALLEL_DIR = os.path.join(BASE_DIR, "parallel_s16")
CKPT_DIR = os.path.join(PARALLEL_DIR, "checkpoints")
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"


def launch_worker(wid, script_content):
    """Launch a GAP worker."""
    script_file = os.path.join(PARALLEL_DIR, f"worker_{wid}_script.g")
    with open(script_file, "w") as f:
        f.write(script_content)

    script_path = f"/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s16/worker_{wid}_script.g"
    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    process = subprocess.Popen(
        [BASH_EXE, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        cwd=GAP_RUNTIME
    )
    return process


def main():
    print(f"=== S16 Round 8: Fixed GF(2) BFS at {time.strftime('%H:%M:%S')} ===\n")

    # Setup W57 checkpoint from worker_45 (or worker_52 if it has more progress)
    w57_ckpt = os.path.join(CKPT_DIR, "worker_57")
    os.makedirs(w57_ckpt, exist_ok=True)
    # Use worker_52's checkpoint (copied from worker_45, same data)
    src = os.path.join(CKPT_DIR, "worker_52", "ckpt_16_4_4_4_4.g")
    dst = os.path.join(w57_ckpt, "ckpt_16_4_4_4_4.g")
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"  Copied checkpoint for [4,4,4,4] ({os.path.getsize(src)} bytes)")
    else:
        print(f"  WARNING: No checkpoint found for [4,4,4,4]")

    # W57: Resume [4,4,4,4] from checkpoint
    w57_log = "C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_57.log"
    w57_hb = "C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_57_heartbeat.txt"
    w57_results = "C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_57_results.txt"
    w57_ckpt_dir = "C:/Users/jeffr/Downloads/Lifting/parallel_s16/checkpoints/worker_57"
    w57_gens = "C:/Users/jeffr/Downloads/Lifting/parallel_s16/gens/gens_4_4_4_4.txt"

    w57_script = f'''LogTo("{w57_log}");
Print("Worker 57 (round 8 - fixed GF2 BFS) starting at ", Runtime()/1000, "s\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

CHECKPOINT_DIR := "{w57_ckpt_dir}";
_HEARTBEAT_FILE := "{w57_hb}";

Print("\\n========================================\\n");
Print("Partition [4,4,4,4]\\n");
Print("========================================\\n");
t0 := Runtime();
PrintTo("{w57_hb}", "starting partition [4,4,4,4]\\n");

result_4_4_4_4 := FindFPFClassesForPartition(16, [4,4,4,4]);
t_elapsed := Runtime() - t0;
Print("Partition [4,4,4,4]: ", Length(result_4_4_4_4),
      " FPF classes (", t_elapsed, "ms)\\n");

# Save generators
output := OutputTextFile("{w57_gens}", false);
for H in result_4_4_4_4 do
    PrintTo(output, GeneratorsOfGroup(H), "\\n");
od;
CloseStream(output);

AppendTo("{w57_results}",
    "[4,4,4,4]: ", Length(result_4_4_4_4),
    " classes (", t_elapsed, "ms)\\n");

PrintTo("{w57_hb}", "completed [4,4,4,4] ", Length(result_4_4_4_4), " classes\\n");

Print("\\nWorker 57 ALL DONE at ", Runtime()/1000, "s\\n");
PrintTo("{w57_hb}", "ALL DONE\\n");
LogTo();
QUIT;
'''

    # W58: Re-run failed C_2^8 combos for [4,4,4,2,2] and [4,4,2,2,2,2]
    # These need to be run as individual combos, building P directly
    w58_log = "C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_58.log"
    w58_hb = "C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_58_heartbeat.txt"
    w58_results = "C:/Users/jeffr/Downloads/Lifting/parallel_s16/worker_58_results.txt"
    w58_gens_1 = "C:/Users/jeffr/Downloads/Lifting/parallel_s16/gens/gens_c2_4_4_4_2_2.txt"
    w58_gens_2 = "C:/Users/jeffr/Downloads/Lifting/parallel_s16/gens/gens_c2_4_4_2_2_2_2.txt"

    w58_script = f'''LogTo("{w58_log}");
Print("Worker 58 (round 8 - C2^8 combo reruns) starting at ", Runtime()/1000, "s\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

_HEARTBEAT_FILE := "{w58_hb}";

# Helper: Build shifted factors from combo indices for degree-16 partition
BuildShiftedFactors := function(partition, comboIndices)
    local shifted, offs, off, ci, deg, idx, G, shift_gens, g, img, full, j;
    shifted := [];
    offs := [];
    off := 0;
    for ci in comboIndices do
        deg := ci[1];
        idx := ci[2];
        G := TransitiveGroup(deg, idx);
        shift_gens := [];
        for g in GeneratorsOfGroup(G) do
            img := ListPerm(g, deg);
            full := [1..16];
            for j in [1..deg] do
                full[j + off] := img[j] + off;
            od;
            Add(shift_gens, PermList(full));
        od;
        Add(shifted, Group(shift_gens));
        Add(offs, off);
        off := off + deg;
    od;
    return rec(shifted := shifted, offs := offs);
end;

# ============================================================
# Combo 1: [4,4,4,2,2] with [[4,2],[4,2],[4,2],[2,1],[2,1]]
# P = V_4^3 x C_2^2 = C_2^8
# ============================================================
Print("\\n========================================\\n");
Print("Combo: [4,4,4,2,2] all-V4 (C_2^8)\\n");
Print("========================================\\n");

PrintTo("{w58_hb}", "running [4,4,4,2,2] C2^8 combo\\n");
t0 := Runtime();

sf1 := BuildShiftedFactors([4,4,4,2,2], [[4,2],[4,2],[4,2],[2,1],[2,1]]);
P1 := Group(Concatenation(List(sf1.shifted, GeneratorsOfGroup)));
Print("|P1| = ", Size(P1), ", IsEA = ", IsElementaryAbelian(P1), "\\n");

# Build normalizer
N1 := BuildConjugacyTestGroup(16, [4,4,4,2,2]);
Print("|N1| = ", Size(N1), "\\n");

# AllSubgroups + FPF filter
orbits1 := List(sf1.shifted, G -> MovedPoints(G));
Print("Computing AllSubgroups...\\n");
allSubs1 := AllSubgroups(P1);
Print("  ", Length(allSubs1), " subgroups\\n");

fpf1 := Filtered(allSubs1, function(H)
    return ForAll(orbits1, function(orb)
        return IsTransitive(H, orb);
    end);
end);
Print("  ", Length(fpf1), " FPF (", Runtime() - t0, "ms)\\n");

# GF(2) orbit dedup
result1 := _DeduplicateEAFPFbyGF2Orbits(P1, fpf1, N1);
Print("  -> ", Length(result1), " orbit reps\\n");

# Save generators
output := OutputTextFile("{w58_gens_1}", false);
for H in result1 do
    PrintTo(output, GeneratorsOfGroup(H), "\\n");
od;
CloseStream(output);
Print("Combo 1 done: ", Length(result1), " classes (", Runtime() - t0, "ms)\\n");

# Free memory
Unbind(allSubs1);
Unbind(fpf1);
GASMAN("collect");

# ============================================================
# Combo 2: [4,4,2,2,2,2] with [[4,2],[4,2],[2,1],[2,1],[2,1],[2,1]]
# P = V_4^2 x C_2^4 = C_2^8
# ============================================================
Print("\\n========================================\\n");
Print("Combo: [4,4,2,2,2,2] all-V4/C2 (C_2^8)\\n");
Print("========================================\\n");

PrintTo("{w58_hb}", "running [4,4,2,2,2,2] C2^8 combo\\n");
t0 := Runtime();

sf2 := BuildShiftedFactors([4,4,2,2,2,2], [[4,2],[4,2],[2,1],[2,1],[2,1],[2,1]]);
P2 := Group(Concatenation(List(sf2.shifted, GeneratorsOfGroup)));
Print("|P2| = ", Size(P2), ", IsEA = ", IsElementaryAbelian(P2), "\\n");

N2 := BuildConjugacyTestGroup(16, [4,4,2,2,2,2]);
Print("|N2| = ", Size(N2), "\\n");

orbits2 := List(sf2.shifted, G -> MovedPoints(G));
Print("Computing AllSubgroups...\\n");
allSubs2 := AllSubgroups(P2);
Print("  ", Length(allSubs2), " subgroups\\n");

fpf2 := Filtered(allSubs2, function(H)
    return ForAll(orbits2, function(orb)
        return IsTransitive(H, orb);
    end);
end);
Print("  ", Length(fpf2), " FPF (", Runtime() - t0, "ms)\\n");

result2 := _DeduplicateEAFPFbyGF2Orbits(P2, fpf2, N2);
Print("  -> ", Length(result2), " orbit reps\\n");

output := OutputTextFile("{w58_gens_2}", false);
for H in result2 do
    PrintTo(output, GeneratorsOfGroup(H), "\\n");
od;
CloseStream(output);
Print("Combo 2 done: ", Length(result2), " classes (", Runtime() - t0, "ms)\\n");

# Save results
AppendTo("{w58_results}",
    "C2^8 combo [4,4,4,2,2]: ", Length(result1), " classes\\n",
    "C2^8 combo [4,4,2,2,2,2]: ", Length(result2), " classes\\n");

Print("\\nWorker 58 ALL DONE at ", Runtime()/1000, "s\\n");
PrintTo("{w58_hb}", "ALL DONE\\n");
LogTo();
QUIT;
'''

    # Launch W57
    print("Launching W57: [4,4,4,4] (from checkpoint)")
    proc57 = launch_worker(57, w57_script)
    print(f"  PID: {proc57.pid}")

    # Launch W58
    w58_ckpt = os.path.join(CKPT_DIR, "worker_58")
    os.makedirs(w58_ckpt, exist_ok=True)
    print("Launching W58: C_2^8 combo reruns")
    proc58 = launch_worker(58, w58_script)
    print(f"  PID: {proc58.pid}")

    print(f"\nBoth workers launched. Monitor with: python monitor_s16.py --once")
    print(f"\nAlso running:")
    print(f"  W43 (PID 63860, [8,8])")
    print(f"  W47 (PID 55688, [8,4,4])")
    print(f"  W53 (non-C2^8 combos of [4,4,4,2,2])")
    print(f"  W54 (non-C2^8 combos of [4,4,2,2,2,2])")
    print(f"  W55 ([6,4,2,2,2])")


if __name__ == "__main__":
    main()
