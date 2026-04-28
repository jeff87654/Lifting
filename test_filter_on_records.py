"""test_filter_on_records.py — compare two filter strategies on the
precomputed D_8^4 normal-subgroup sidecar:

  A. Filter on records (size precomputed): records → check e.size → build Group only for survivors
  B. Filter on Groups (status quo): records → build Group → call Size(K) → check
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "test_filter_on_records.log"
NS_FILE = ROOT / "normalsubgroups_D8_4.g"

if LOG.exists():
    LOG.unlink()

GAP_SCRIPT = f'''
LogTo("{str(LOG).replace(chr(92), "/")}");
Print("=== filter on records vs filter on Groups ===\\n");

t := Runtime();
Read("{str(NS_FILE).replace(chr(92), "/")}");
Print("[t+", Runtime()-t, "ms] loaded NORMALS_OF_D8_4 (",
      Length(NORMALS_OF_D8_4), " records)\\n\\n");

q_size_filter := [1, 2, 3, 6];
H_size := 4096;

# --- Strategy A: filter on records (precomputed size) ---
Print("--- A: filter on records ---\\n");
t := Runtime();
records_filt := Filtered(NORMALS_OF_D8_4,
    e -> e.size <> H_size and (H_size / e.size) in q_size_filter);
Print("[t+", Runtime()-t, "ms] filtered to ", Length(records_filt), " records\\n");
t := Runtime();
groups_A := List(records_filt, function(e)
    if Length(e.gens) = 0 then return TrivialGroup(IsPermGroup); fi;
    return Group(e.gens);
end);
Print("[t+", Runtime()-t, "ms] built ", Length(groups_A), " Group objects\\n\\n");

# --- Strategy B: build all Groups, then filter on Size ---
Print("--- B: build all Groups, filter on Size ---\\n");
t := Runtime();
all_groups := List(NORMALS_OF_D8_4, function(e)
    if Length(e.gens) = 0 then return TrivialGroup(IsPermGroup); fi;
    return Group(e.gens);
end);
Print("[t+", Runtime()-t, "ms] built ", Length(all_groups), " Group objects\\n");
t := Runtime();
groups_B := Filtered(all_groups,
    K -> Size(K) <> H_size and (H_size / Size(K)) in q_size_filter);
Print("[t+", Runtime()-t, "ms] filtered to ", Length(groups_B), " Groups\\n\\n");

Print("Both strategies surface ", Length(groups_A), " survivors.\\n");
LogTo();
QUIT;
'''

(ROOT / "test_filter_on_records.g").write_text(GAP_SCRIPT, encoding="utf-8")
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_filter_on_records.g"
env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"
print(f"Running... (log: {LOG})")
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cyg}"'],
    env=env,
)
print(f"GAP rc={proc.returncode}")
if LOG.exists():
    print(LOG.read_text(encoding="utf-8"))
