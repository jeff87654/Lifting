"""compare_unified_vs_tiered_s12.py — re-profile the same 20 random S12
combos but with three strategies side-by-side:

  1. TRAD-S_M     : Normalizer(S_M, H) + NormalSubgroups + filter
  2. TRAD-W_ML    : Normalizer(W_ML, H) + NormalSubgroups + filter
  3. TIERED-W_ML  : Normalizer(W_ML, H) + per-Q tiered enum

For combos where W_ML differs meaningfully from S_M (multi-block partitions),
unified-W should beat unified-S_M.  Filter is applied to q_size_filter
{1, 2, 3, 6} (S19 Q-types).
"""
import os
import random
import re
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "compare_unified_vs_tiered_s12.log"
if LOG.exists():
    LOG.unlink()

random.seed(42)
all_combos = sorted((ROOT / "parallel_sn_v2" / "12").rglob("*.g"))
sample = random.sample(all_combos, 20)
sample.sort()
print(f"Sampling {len(sample)} S12 combos")

def parse_combo_file(path):
    text = path.read_text(encoding="utf-8")
    joined = re.sub(r"\\\r?\n", "", text)
    return [ln.strip() for ln in joined.splitlines()
            if ln.startswith("[") and not ln.startswith("[Group")]

def part_from_path(p):
    return p.parent.name

def part_tuple(p):
    return tuple(int(x) for x in p.strip("[]").split(","))

case_blocks = []
for cf in sample:
    gen_lines = parse_combo_file(cf)
    if not gen_lines: continue
    case_blocks.append({
        "combo": cf.stem,
        "partition": part_from_path(cf),
        "partition_tuple": part_tuple(part_from_path(cf)),
        "gen_lines": gen_lines,
    })

GAP_LINES = [
    f'LogTo("{str(LOG).replace(chr(92), "/")}");',
    'Print("=== TRAD-S vs TRAD-W vs TIERED-W on 20 S12 combos ===\\n");',
    '',
    'Q_C2 := CyclicGroup(IsPermGroup, 2);',
    'Q_C3 := CyclicGroup(IsPermGroup, 3);',
    'Q_S3 := SymmetricGroup(3);',
    'Q_GROUPS := [Q_C2, Q_C3, Q_S3];',
    'Q_SIZE_FILTER := [1, 2, 3, 6];',
    '',
    'ConjAction := function(K, g) return K^g; end;',
    'SafeId := function(G)',
    '    local n;',
    '    n := Size(G);',
    '    if IdGroupsAvailable(n) then return [n, 0, IdGroup(G)]; fi;',
    '    return [n, 1, AbelianInvariants(G), List(DerivedSeries(G), Size)];',
    'end;',
    '',
    'BlockWreathFromPartition := function(partition)',
    '    local factors, i, j, m, mult;',
    '    factors := [];',
    '    i := 1;',
    '    while i <= Length(partition) do',
    '        m := partition[i];',
    '        mult := 0; j := i;',
    '        while j <= Length(partition) and partition[j] = m do',
    '            mult := mult + 1; j := j + 1;',
    '        od;',
    '        if mult = 1 then Add(factors, SymmetricGroup(m));',
    '        else Add(factors, WreathProduct(SymmetricGroup(m), SymmetricGroup(mult)));',
    '        fi;',
    '        i := j;',
    '    od;',
    '    if Length(factors) = 1 then return factors[1]; fi;',
    '    return DirectProduct(factors);',
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
    '_TieredEnumerate := function(H)',
    '    local result, Q, sz;',
    '    result := [];',
    '    for Q in Q_GROUPS do',
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
    '_OrbitRecs := function(H, N, normals)',
    '    local K_orbit, K_H, hom_H, Q_H, Stab, orbits;',
    '    orbits := [];',
    '    for K_orbit in Orbits(N, normals, ConjAction) do',
    '        K_H := K_orbit[1];',
    '        hom_H := NaturalHomomorphismByNormalSubgroup(H, K_H);',
    '        Q_H := Range(hom_H);',
    '        Stab := Stabilizer(N, K_H, ConjAction);',
    '        Add(orbits, rec(qsize := Size(Q_H), qid := SafeId(Q_H)));',
    '    od;',
    '    return orbits;',
    'end;',
    '',
    'TimeOneH := function(H, S_M, W_ML)',
    '    local norm_S_t, N_S, norm_W_t, N_W,',
    '          ns_t, ns, filt_t, ns_filt,',
    '          trad_S_orb_t, trad_S_orbs,',
    '          trad_W_orb_t, trad_W_orbs,',
    '          tier_t, tier_kers, tier_W_orb_t, tier_W_orbs;',
    '    norm_S_t := Runtime();',
    '    N_S := Normalizer(S_M, H);',
    '    norm_S_t := Runtime() - norm_S_t;',
    '    norm_W_t := Runtime();',
    '    N_W := Normalizer(W_ML, H);',
    '    norm_W_t := Runtime() - norm_W_t;',
    '    ns_t := Runtime();',
    '    ns := NormalSubgroups(H);',
    '    ns_t := Runtime() - ns_t;',
    '    filt_t := Runtime();',
    '    ns_filt := Filtered(ns, K -> K <> H and Size(H)/Size(K) in Q_SIZE_FILTER);',
    '    filt_t := Runtime() - filt_t;',
    '    trad_S_orb_t := Runtime();',
    '    trad_S_orbs := _OrbitRecs(H, N_S, ns_filt);',
    '    trad_S_orb_t := Runtime() - trad_S_orb_t;',
    '    trad_W_orb_t := Runtime();',
    '    trad_W_orbs := _OrbitRecs(H, N_W, ns_filt);',
    '    trad_W_orb_t := Runtime() - trad_W_orb_t;',
    '    tier_t := Runtime();',
    '    tier_kers := _TieredEnumerate(H);',
    '    tier_t := Runtime() - tier_t;',
    '    tier_W_orb_t := Runtime();',
    '    tier_W_orbs := _OrbitRecs(H, N_W, tier_kers);',
    '    tier_W_orb_t := Runtime() - tier_W_orb_t;',
    '    return rec(',
    '        norm_S := norm_S_t, norm_W := norm_W_t,',
    '        ns := ns_t, filt := filt_t,',
    '        ns_count := Length(ns), ns_filt_count := Length(ns_filt),',
    '        tier_count := Length(tier_kers),',
    '        trad_S_orb := trad_S_orb_t, trad_S_n := Length(trad_S_orbs),',
    '        trad_W_orb := trad_W_orb_t, trad_W_n := Length(trad_W_orbs),',
    '        tier := tier_t, tier_W_orb := tier_W_orb_t, tier_W_n := Length(tier_W_orbs)',
    '    );',
    'end;',
    '',
    'agg := rec(',
    '    norm_S := 0, norm_W := 0,',
    '    ns := 0, filt := 0,',
    '    trad_S_orb := 0, trad_W_orb := 0,',
    '    tier := 0, tier_W_orb := 0, h := 0',
    ');',
]

for case in case_blocks:
    part = case["partition"]
    combo = case["combo"]
    gen_lines = case["gen_lines"]
    parts_list = list(case["partition_tuple"])
    m_l = sum(parts_list)
    parts_gap = "[" + ",".join(str(d) for d in parts_list) + "]"
    GAP_LINES.append(f'\nPrint("\\n=== {part}/{combo} (M={m_l}, {len(gen_lines)} H) ===\\n");')
    GAP_LINES.append(f'S_M := SymmetricGroup({m_l});')
    GAP_LINES.append(f'W_ML := BlockWreathFromPartition({parts_gap});')
    GAP_LINES.append(f'cb := rec(norm_S := 0, norm_W := 0, ns := 0, filt := 0,'
                     f' trad_S_orb := 0, trad_W_orb := 0, tier := 0, tier_W_orb := 0);')
    for gl in gen_lines:
        GAP_LINES.append(f'H := Group({gl});')
        GAP_LINES.append('res := TimeOneH(H, S_M, W_ML);')
        GAP_LINES.append('cb.norm_S := cb.norm_S + res.norm_S;')
        GAP_LINES.append('cb.norm_W := cb.norm_W + res.norm_W;')
        GAP_LINES.append('cb.ns := cb.ns + res.ns;')
        GAP_LINES.append('cb.filt := cb.filt + res.filt;')
        GAP_LINES.append('cb.trad_S_orb := cb.trad_S_orb + res.trad_S_orb;')
        GAP_LINES.append('cb.trad_W_orb := cb.trad_W_orb + res.trad_W_orb;')
        GAP_LINES.append('cb.tier := cb.tier + res.tier;')
        GAP_LINES.append('cb.tier_W_orb := cb.tier_W_orb + res.tier_W_orb;')
        GAP_LINES.append('agg.h := agg.h + 1;')
    GAP_LINES.append('Print("  TRAD-S=", cb.norm_S + cb.ns + cb.filt + cb.trad_S_orb,'
                     '"ms  TRAD-W=", cb.norm_W + cb.ns + cb.filt + cb.trad_W_orb,'
                     '"ms  TIERED-W=", cb.norm_W + cb.tier + cb.tier_W_orb, "ms"); ')
    GAP_LINES.append('Print(" (norm_S=", cb.norm_S, " norm_W=", cb.norm_W, " ns=", cb.ns,'
                     '" filt=", cb.filt, " orb_S=", cb.trad_S_orb, " orb_W=", cb.trad_W_orb,'
                     '" tier_enum=", cb.tier, " tier_orb=", cb.tier_W_orb, ")\\n");')
    GAP_LINES.append('agg.norm_S := agg.norm_S + cb.norm_S;')
    GAP_LINES.append('agg.norm_W := agg.norm_W + cb.norm_W;')
    GAP_LINES.append('agg.ns := agg.ns + cb.ns;')
    GAP_LINES.append('agg.filt := agg.filt + cb.filt;')
    GAP_LINES.append('agg.trad_S_orb := agg.trad_S_orb + cb.trad_S_orb;')
    GAP_LINES.append('agg.trad_W_orb := agg.trad_W_orb + cb.trad_W_orb;')
    GAP_LINES.append('agg.tier := agg.tier + cb.tier;')
    GAP_LINES.append('agg.tier_W_orb := agg.tier_W_orb + cb.tier_W_orb;')

GAP_LINES.append(r'''
Print("\n=== AGGREGATE (across all H) ===\n");
Print("Total H:        ", agg.h, "\n");
Print("Norm in S_M:    ", agg.norm_S, "ms\n");
Print("Norm in W_ML:   ", agg.norm_W, "ms\n");
Print("NormalSubgroups:", agg.ns, "ms\n");
Print("Filter:         ", agg.filt, "ms\n");
Print("OrbitDecomp/N_S:", agg.trad_S_orb, "ms\n");
Print("OrbitDecomp/N_W:", agg.trad_W_orb, "ms\n");
Print("Tiered enum:    ", agg.tier, "ms\n");
Print("Tiered orb/N_W: ", agg.tier_W_orb, "ms\n");
Print("\n=== TOTAL TIME PER STRATEGY (all H) ===\n");
Print("TRAD-S (Norm-S + NS + filter + orb-S):    ", agg.norm_S + agg.ns + agg.filt + agg.trad_S_orb, "ms\n");
Print("TRAD-W (Norm-W + NS + filter + orb-W):    ", agg.norm_W + agg.ns + agg.filt + agg.trad_W_orb, "ms\n");
Print("TIERED-W (Norm-W + tiered + orb-W):       ", agg.norm_W + agg.tier + agg.tier_W_orb, "ms\n");
LogTo();
QUIT;
''')

(ROOT / "compare_unified_vs_tiered_s12.g").write_text("\n".join(GAP_LINES), encoding="utf-8")

bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/compare_unified_vs_tiered_s12.g"
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
    text = LOG.read_text(encoding="utf-8")
    print(text[-3000:])
