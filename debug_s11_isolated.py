"""Truly isolated S11 tests: reset both caches between TF-off and TF-on."""
import subprocess, os, shutil
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
FPF_CACHE = LIFTING / "database" / "fpf_subdirects" / "fpf_cache.g"
TF_CACHE = LIFTING / "database" / "tf_groups" / "tf_subgroup_lattice.g"


def reset_caches():
    # FPF: revert to git
    subprocess.run(["git", "checkout", str(FPF_CACHE)], cwd=str(LIFTING),
                   capture_output=True)
    # TF: empty
    TF_CACHE.write_text(
        "###############################################################################\n"
        "# tf_subgroup_lattice.g - Reset\n"
        "###############################################################################\n"
        "TF_SUBGROUP_LATTICE_DATA := rec();\n"
    )


def run_s11(tf_enabled, log_suffix):
    log_file = LIFTING / f"debug_iso_s11_{log_suffix}.log"
    if log_file.exists():
        log_file.unlink()
    tmp = LIFTING / f"temp_iso_s11_{log_suffix}.g"
    gap_code = f'''
USE_TF_DATABASE := {("true" if tf_enabled else "false")};;
LogTo("{log_file.as_posix()}");
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");
Read("{(LIFTING / "database" / "lift_cache.g").as_posix()}");
Unbind(LIFT_CACHE.("11"));
Print("USE_TF_DATABASE = ", USE_TF_DATABASE, "\\n");
t0 := Runtime();
result := CountAllConjugacyClassesFast(11);
elapsed := (Runtime() - t0) / 1000.0;
Print("S_11 = ", result, " (expected 3094) elapsed=", elapsed, "s\\n");
LogTo();
QUIT;
'''
    tmp.write_text(gap_code)
    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'
    proc = subprocess.Popen(
        [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
         f'./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_iso_s11_{log_suffix}.g"'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        cwd=r"C:\Program Files\GAP-4.15.1\runtime")
    proc.communicate(timeout=600)
    return log_file.read_text() if log_file.exists() else ""


print("=== Run 1: TF disabled, fresh caches ===")
reset_caches()
log = run_s11(False, "tf_off_iso")
for line in log.splitlines():
    if "S_11 =" in line or "USE_TF" in line:
        print(line)

print("\n=== Run 2: TF enabled, fresh caches ===")
reset_caches()
log = run_s11(True, "tf_on_iso")
for line in log.splitlines():
    if "S_11 =" in line or "USE_TF" in line or "TF_LOOKUP" in line or "TF-database" in line:
        print(line)
