"""test_gq_perf_real.py — timing study of GQuotients-per-Q-type vs
NormalSubgroups across REAL LEFT subs files spanning S6-S12.

Picks a representative set of subs files (one per LEFT-shape class),
loads the FPF subgroup list, and times both enumeration paths on
each H.  Reports per-LEFT and aggregate stats.
"""
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "test_gq_perf_real.log"
if LOG.exists():
    LOG.unlink()

# Find subs files; pick one representative per "shape class" defined by the
# combo's structure (deg multiset + factor types).
SUBS_DIR = ROOT / "predict_species_tmp" / "_holt_split"
all_subs = sorted(SUBS_DIR.glob("*/subs_left.g"))
print(f"Found {len(all_subs)} subs files")

# Bucket by combo shape and pick small + medium + large per bucket.
# Shape = list of (degree, t_index) pairs sorted, abstracted to (degree,) only.
# Pick up to N per "max degree".
selected = []
seen_shapes = set()
for path in all_subs:
    combo_name = path.parent.name   # e.g. "[2,1]_[4,3]_[4,3]_[4,3]"
    # Parse degrees: each token "[d,t]"
    degs = tuple(sorted(int(m.group(1)) for m in re.finditer(r"\[(\d+),", combo_name)))
    # Use the multiset of degrees as the shape
    if degs in seen_shapes:
        continue
    seen_shapes.add(degs)
    selected.append((path, combo_name, degs))

# Restrict to LEFTs of total degree ≤ 12 to keep the test bounded
selected = [(p, c, d) for (p, c, d) in selected if sum(d) <= 12]
print(f"Selected {len(selected)} representative LEFT combos (total degree <= 12)")

# Cap per-H NormalSubgroups so a pathological one doesn't hang the whole run
NS_CAP_MS = 30000

GAP_LINES = [
    f'LogTo("{str(LOG).replace(chr(92), "/")}");',
    'Print("=== GQ-per-Q-type vs NormalSubgroups perf comparison ===\\n\\n");',
    '',
    '# Q-types we care about for S18+S19+S20 builds',
    'Q_C2 := CyclicGroup(IsPermGroup, 2);',
    'Q_C3 := CyclicGroup(IsPermGroup, 3);',
    'Q_S3 := SymmetricGroup(3);',
    'Q_V4 := DirectProduct(CyclicGroup(IsPermGroup, 2), CyclicGroup(IsPermGroup, 2));',
    'Q_C4 := CyclicGroup(IsPermGroup, 4);',
    'Q_D8 := TransitiveGroup(4, 3);',
    'Q_A4 := AlternatingGroup(4);',
    'Q_S4 := SymmetricGroup(4);',
    '',
    '# Pretend we are building for S20 (M_R=4): need all S_4 quotients',
    'Q_TYPES := [Q_C2, Q_C3, Q_V4, Q_C4, Q_D8, Q_A4, Q_S4];',
    '',
    'TotGQ := 0;  TotNS := 0;  TotH := 0;',
    'NS_skipped := 0;  HuiltCorrupt := 0;',
    '',
    'TimeOneH := function(H, ns_cap_ms)',
    '    local t, gqs, kers, gq_total, gq_kers_total, ns, ns_time, q;',
    '    gq_total := 0;',
    '    gq_kers_total := 0;',
    '    for q in Q_TYPES do',
    '        t := Runtime();',
    '        gqs := GQuotients(H, q);',
    '        kers := Set(List(gqs, Kernel));',
    '        gq_total := gq_total + (Runtime() - t);',
    '        gq_kers_total := gq_kers_total + Length(kers);',
    '    od;',
    '    if Size(H) > 8000 then',
    '        return rec(gq_ms := gq_total, gq_kers := gq_kers_total,',
    '                   ns_ms := -1, ns_count := -1);',
    '    fi;',
    '    t := Runtime();',
    '    ns := NormalSubgroups(H);',
    '    ns_time := Runtime() - t;',
    '    return rec(gq_ms := gq_total, gq_kers := gq_kers_total,',
    '               ns_ms := ns_time, ns_count := Length(ns));',
    'end;',
    '',
]

for path, combo_name, degs in selected:
    cyg = str(path).replace("\\", "/")
    GAP_LINES.append(f'''
# {combo_name}  degrees={list(degs)}  totalM={sum(degs)}
Print("\\n=== combo={combo_name} totalM=", {sum(degs)}, " ===\\n");
SUBGROUPS := fail;
Read("{cyg}");
if SUBGROUPS = fail or Length(SUBGROUPS) = 0 then
    Print("  (no subgroups read)\\n");
else
    Print("  ", Length(SUBGROUPS), " H entries\\n");
    combo_gq_ms := 0;
    combo_ns_ms := 0;
    combo_h := 0;
    combo_max_gq := 0;
    combo_max_ns := 0;
    combo_ns_skipped := 0;
    for H in SUBGROUPS do
        res := TimeOneH(H, {NS_CAP_MS});
        combo_gq_ms := combo_gq_ms + res.gq_ms;
        combo_h := combo_h + 1;
        if res.gq_ms > combo_max_gq then combo_max_gq := res.gq_ms; fi;
        if res.ns_ms < 0 then
            combo_ns_skipped := combo_ns_skipped + 1;
        else
            combo_ns_ms := combo_ns_ms + res.ns_ms;
            if res.ns_ms > combo_max_ns then combo_max_ns := res.ns_ms; fi;
        fi;
    od;
    TotGQ := TotGQ + combo_gq_ms;
    TotNS := TotNS + combo_ns_ms;
    TotH := TotH + combo_h;
    NS_skipped := NS_skipped + combo_ns_skipped;
    Print("  GQ total=", combo_gq_ms, "ms  NS total=", combo_ns_ms, "ms",
          "  GQ-max=", combo_max_gq, "ms  NS-max=", combo_max_ns, "ms",
          "  H=", combo_h, "  NS-skipped=", combo_ns_skipped, "\\n");
fi;
''')

GAP_LINES.append('''
Print("\\n=== AGGREGATE ===\\n");
Print("Total H:           ", TotH, "\\n");
Print("Total GQ time (s): ", Float(TotGQ/1000.0), "\\n");
Print("Total NS time (s): ", Float(TotNS/1000.0), "\\n");
Print("NS skipped:        ", NS_skipped, "\\n");
if TotGQ > 0 then
    Print("Avg GQ per H (ms): ", Float(TotGQ/TotH), "\\n");
fi;
if TotNS > 0 then
    Print("Avg NS per H (ms): ", Float(TotNS / (TotH - NS_skipped)), "\\n");
fi;
LogTo();
QUIT;
''')

(ROOT / "test_gq_perf_real.g").write_text("\n".join(GAP_LINES), encoding="utf-8")

bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_gq_perf_real.g"

env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"

print(f"Running {len(selected)} LEFT combos...")
print(f"Log: {LOG}")
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cyg}"'],
    env=env,
)
print(f"GAP rc={proc.returncode}")
print()
if LOG.exists():
    text = LOG.read_text(encoding="utf-8")
    print(text[-5000:] if len(text) > 5000 else text)
