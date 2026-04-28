import os
import pathlib
import subprocess
import time


ROOT = pathlib.Path(r"C:\Users\jeffr\Downloads\Lifting")
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"


def gap_bool(value):
    return "true" if value else "false"


def run_gap(label, n, partition, factors, section_enabled):
    gap_path = ROOT / f"tmp_h1_section_{label}.g"
    log_path = ROOT / f"tmp_h1_section_{label}.log"
    factor_expr = "[" + ", ".join(
        f"TransitiveGroup({degree},{idx})" for degree, idx in factors
    ) + "]"
    partition_expr = "[" + ",".join(str(x) for x in partition) + "]"
    gap_log = str(log_path).replace("\\", "/")
    gap_commands = f"""
LogTo("{gap_log}");
H1_OUTER_SECTION_ACTION := {gap_bool(section_enabled)};
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
USE_HOLT_ENGINE := true;
HOLT_ENGINE_MODE := "clean";
CHECKPOINT_DIR := "";
COMBO_OUTPUT_DIR := "";
HOLT_ENABLE_BLOCK_QUOTIENT_DEDUP := false;
HOLT_UF_INDEX_BUCKET_MIN := 40;
BlockRangesFromPartition := function(partition)
  local ranges, start, d;
  ranges := [];
  start := 1;
  for d in partition do
    Add(ranges, [start, start + d - 1]);
    start := start + d;
  od;
  return ranges;
end;
BuildCombo := function()
  local partition, currentFactors, shifted, offs, off, k, P, Nfull;
  partition := {partition_expr};
  currentFactors := {factor_expr};
  shifted := [];
  offs := [];
  off := 0;
  for k in [1..Length(currentFactors)] do
    Add(offs, off);
    Add(shifted, ShiftGroup(currentFactors[k], off));
    off := off + NrMovedPoints(currentFactors[k]);
  od;
  P := GroupByGenerators(Concatenation(List(shifted, GeneratorsOfGroup)));
  SetSize(P, Product(List(shifted, Size)));
  Nfull := BuildConjugacyTestGroup({n}, partition);
  CURRENT_BLOCK_RANGES := BlockRangesFromPartition(partition);
  return [P, shifted, offs, Nfull];
end;
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
if IsBound(HOLT_TF_CACHE) then HOLT_TF_CACHE := rec(); fi;
ResetH1OrbitalStats();
pack := BuildCombo();
Print("CASE {label} section=", H1_OUTER_SECTION_ACTION,
      " |P|=", Size(pack[1]), " |N|=", Size(pack[4]), "\\n");
t0 := Runtime();
res := HoltFPFSubgroupClassesOfProduct(pack[1], pack[2], pack[3], pack[4]);
elapsed := Runtime() - t0;
Print("RESULT {label} count=", Length(res), " elapsed_ms=", elapsed, "\\n");
PrintH1OrbitalStats();
LogTo();
QUIT;
"""
    gap_path.write_text(gap_commands)

    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/" + gap_path.name
    started = time.time()
    process = subprocess.Popen(
        [
            BASH_EXE,
            "--login",
            "-c",
            f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_path}"',
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=GAP_RUNTIME,
    )
    stdout, stderr = process.communicate()
    wall = time.time() - started
    log_text = log_path.read_text(errors="replace") if log_path.exists() else ""
    warnings = log_text.count("BuildH1ActionRecordFromOuterNorm failed")
    result_line = next((line for line in log_text.splitlines() if line.startswith("RESULT ")), "")
    print(f"{label}: rc={process.returncode} wall={wall:.1f}s warnings={warnings} {result_line}")
    if process.returncode != 0:
        print(stderr[-2000:])
    return process.returncode


def main():
    cases = [
        ("s17_5552_off1", 17, [5, 5, 5, 2], [(5, 5), (5, 5), (5, 5), (2, 1)], False),
        ("s17_5552_on1", 17, [5, 5, 5, 2], [(5, 5), (5, 5), (5, 5), (2, 1)], True),
        ("s17_5552_off2", 17, [5, 5, 5, 2], [(5, 5), (5, 5), (5, 5), (2, 1)], False),
        ("s17_5552_on2", 17, [5, 5, 5, 2], [(5, 5), (5, 5), (5, 5), (2, 1)], True),
    ]
    for args in cases:
        rc = run_gap(*args)
        if rc != 0:
            raise SystemExit(rc)


if __name__ == "__main__":
    main()
