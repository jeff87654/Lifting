"""compare_h_cache_strategies_s12.py — pick 20 random S12 LEFT combos and
time TRADITIONAL h_cache build (NS+filter for ALL Q-types) vs
S3-ONLY h_cache build (tiered for q_groups={C_2,C_3,S_3}).
"""
import os
import random
import re
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "compare_h_cache_strategies_s12.log"
if LOG.exists():
    LOG.unlink()

# Pick 20 random S12 combo files.  These give us LEFT subgroup gen-lists
# (each line is one FPF class).
random.seed(42)
all_combos = sorted((ROOT / "parallel_sn_v2" / "12").rglob("*.g"))
print(f"Total S12 combos: {len(all_combos)}")
sample = random.sample(all_combos, min(20, len(all_combos)))
sample.sort()
print(f"Sampling {len(sample)} combos")

# For each combo, parse to extract H gens lines
def parse_combo_file(path):
    """Returns list of (gens_str_for_GAP, partition_str, combo_name).
    Each H is one element of SUBGROUPS list."""
    text = path.read_text(encoding="utf-8")
    joined = re.sub(r"\\\r?\n", "", text)
    gen_lines = [ln.strip() for ln in joined.splitlines()
                 if ln.startswith("[") and not ln.startswith("[Group")]
    return gen_lines

# Determine partition (block sizes) from combo path
def part_from_path(p):
    # path like parallel_sn_v2/12/[4,4,4]/[4,3]_[4,3]_[4,3].g
    return p.parent.name

case_blocks = []
for cf in sample:
    gen_lines = parse_combo_file(cf)
    if not gen_lines:
        continue
    case_blocks.append({
        "combo": cf.stem,
        "partition": part_from_path(cf),
        "gen_lines": gen_lines,
    })
    print(f"  {part_from_path(cf)}/{cf.stem} : {len(gen_lines)} H subgroups")

# Build the GAP script
GAP_LINES = [
    f'LogTo("{str(LOG).replace(chr(92), "/")}");',
    'Print("=== TRADITIONAL vs S3-ONLY h_cache, 20 random S12 combos ===\\n");',
    '',
    'Q_C2 := CyclicGroup(IsPermGroup, 2);',
    'Q_C3 := CyclicGroup(IsPermGroup, 3);',
    'Q_S3 := SymmetricGroup(3);',
    'Q_GROUPS := [Q_C2, Q_C3, Q_S3];',
    '',
    'ConjAction := function(K, g) return K^g; end;',
    'SafeId := function(G)',
    '    local n;',
    '    n := Size(G);',
    '    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;',
    '    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];',
    'end;',
    '',
    '_IndexPNormals := function(H, p)',
    '    local DH, hom, A, max_subs;',
    '    DH := DerivedSubgroup(H);',
    '    if Index(H, DH) mod p <> 0 then return []; fi;',
    '    hom := NaturalHomomorphismByNormalSubgroup(H, DH);',
    '    A := Range(hom);',
    '    max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = p);',
    '    return List(max_subs, K -> PreImage(hom, K));',
    'end;',
    '',
    '_TieredEnumerate := function(H, q_groups)',
    '    local result, Q, sz, kers;',
    '    result := [];',
    '    for Q in q_groups do',
    '        sz := Size(Q);',
    '        if IsPrimeInt(sz) then',
    '            Append(result, _IndexPNormals(H, sz));',
    '        else',
    '            Append(result, Set(List(GQuotients(H, Q), Kernel)));',
    '        fi;',
    '    od;',
    '    return Set(result);',
    'end;',
    '',
    '_OrbitRecs := function(H, N_H, normals)',
    '    local K_orbit, K_H, hom_H, Q_H, Stab_NH_KH, orbits;',
    '    orbits := [];',
    '    for K_orbit in Orbits(N_H, normals, ConjAction) do',
    '        K_H := K_orbit[1];',
    '        hom_H := NaturalHomomorphismByNormalSubgroup(H, K_H);',
    '        Q_H := Range(hom_H);',
    '        Stab_NH_KH := Stabilizer(N_H, K_H, ConjAction);',
    '        Add(orbits, rec(qsize := Size(Q_H), qid := SafeId(Q_H)));',
    '    od;',
    '    return orbits;',
    'end;',
    '',
    'TimeOneH := function(H, S_M)',
    '    local trad_t, trad_normals, trad_orbits, trad_total, new_t,',
    '          new_normals, new_orbits, new_total, norm_t, N_W;',
    '    norm_t := Runtime();',
    '    N_W := Normalizer(S_M, H);',
    '    norm_t := Runtime() - norm_t;',
    '    # Traditional: NormalSubgroups(H) + filter (none here, take all) + orbit-decomp',
    '    trad_t := Runtime();',
    '    trad_normals := Filtered(NormalSubgroups(H), K -> K <> H);',
    '    trad_t := Runtime() - trad_t;',
    '    trad_orbits := Runtime();',
    '    trad_orbits := _OrbitRecs(H, N_W, trad_normals);',
    '    trad_total := norm_t + trad_t + (Runtime() - trad_t - norm_t);',
    '    # S3-only: tiered enum + orbit-decomp on filtered list',
    '    new_t := Runtime();',
    '    new_normals := _TieredEnumerate(H, Q_GROUPS);',
    '    new_t := Runtime() - new_t;',
    '    new_orbits := Runtime();',
    '    new_orbits := _OrbitRecs(H, N_W, new_normals);',
    '    new_total := norm_t + new_t + (Runtime() - new_t - norm_t);',
    '    return rec(',
    '        norm_ms := norm_t,',
    '        trad_enum_ms := trad_t,',
    '        trad_normals := Length(trad_normals),',
    '        trad_orbits := Length(trad_orbits),',
    '        new_enum_ms := new_t,',
    '        new_normals := Length(new_normals),',
    '        new_orbits := Length(new_orbits)',
    '    );',
    'end;',
    '',
    'agg_norm := 0;',
    'agg_trad_enum := 0;',
    'agg_trad_norms := 0;',
    'agg_trad_orbits := 0;',
    'agg_new_enum := 0;',
    'agg_new_norms := 0;',
    'agg_new_orbits := 0;',
    'agg_h := 0;',
]

# For each combo, parse its gens lines and time per-H
for case in case_blocks:
    part = case["partition"]
    combo = case["combo"]
    gen_lines = case["gen_lines"]
    # M_L is sum of partition parts.  For S12 LEFTs (assuming partition is the LEFT's
    # cycle structure), M = sum.  But these are the FULL combo files at S12 — partition
    # has all parts of the combo.  Each H in the combo has FPF action of that cycle type.
    parts_list = [int(x) for x in part.strip("[]").split(",")]
    m_l = sum(parts_list)
    GAP_LINES.append(f'\nPrint("\\n=== {part}/{combo} (M={m_l}, {len(gen_lines)} H) ===\\n");')
    GAP_LINES.append(f'S_M := SymmetricGroup({m_l});')
    GAP_LINES.append(f'combo_norm := 0; combo_trad_e := 0; combo_trad_n := 0; combo_trad_o := 0;')
    GAP_LINES.append(f'combo_new_e := 0; combo_new_n := 0; combo_new_o := 0;')
    for gl in gen_lines:
        GAP_LINES.append(f'H := Group({gl});')
        GAP_LINES.append('res := TimeOneH(H, S_M);')
        GAP_LINES.append('combo_norm := combo_norm + res.norm_ms;')
        GAP_LINES.append('combo_trad_e := combo_trad_e + res.trad_enum_ms;')
        GAP_LINES.append('combo_trad_n := combo_trad_n + res.trad_normals;')
        GAP_LINES.append('combo_trad_o := combo_trad_o + res.trad_orbits;')
        GAP_LINES.append('combo_new_e := combo_new_e + res.new_enum_ms;')
        GAP_LINES.append('combo_new_n := combo_new_n + res.new_normals;')
        GAP_LINES.append('combo_new_o := combo_new_o + res.new_orbits;')
        GAP_LINES.append('agg_h := agg_h + 1;')
    GAP_LINES.append('Print("  norm=", combo_norm, "ms  trad_enum=", combo_trad_e,'
                     '"ms (",combo_trad_n," normals, ", combo_trad_o, " orbits)  '
                     'new_enum=", combo_new_e, "ms (", combo_new_n, " normals, ",'
                     'combo_new_o, " orbits)\\n");')
    GAP_LINES.append('agg_norm := agg_norm + combo_norm;')
    GAP_LINES.append('agg_trad_enum := agg_trad_enum + combo_trad_e;')
    GAP_LINES.append('agg_trad_norms := agg_trad_norms + combo_trad_n;')
    GAP_LINES.append('agg_trad_orbits := agg_trad_orbits + combo_trad_o;')
    GAP_LINES.append('agg_new_enum := agg_new_enum + combo_new_e;')
    GAP_LINES.append('agg_new_norms := agg_new_norms + combo_new_n;')
    GAP_LINES.append('agg_new_orbits := agg_new_orbits + combo_new_o;')

GAP_LINES.append(r'''
Print("\n=== AGGREGATE ===\n");
Print("Total H:               ", agg_h, "\n");
Print("Total Normalizer time: ", agg_norm, "ms\n");
Print("Traditional (NS+all):  enum=", agg_trad_enum, "ms  ", agg_trad_norms, " normals  ", agg_trad_orbits, " orbits\n");
Print("S3-only (tiered):      enum=", agg_new_enum, "ms  ", agg_new_norms, " normals  ", agg_new_orbits, " orbits\n");
if agg_new_enum > 0 then
    Print("Speedup ratio (enum):  ", Float(agg_trad_enum * 1.0 / agg_new_enum), "x\n");
fi;
LogTo();
QUIT;
''')

(ROOT / "compare_h_cache_strategies_s12.g").write_text("\n".join(GAP_LINES), encoding="utf-8")

bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/compare_h_cache_strategies_s12.g"
env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"

print(f"\nRunning comparison test... (log: {LOG})")
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cyg}"'],
    env=env,
)
print(f"GAP rc={proc.returncode}")
if LOG.exists():
    text = LOG.read_text(encoding="utf-8")
    print(text[-3000:])
