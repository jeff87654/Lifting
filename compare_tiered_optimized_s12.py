"""compare_tiered_optimized_s12.py — re-profile S12 combos comparing
  TRAD-W vs TIERED-W vs TIERED-W-OPT (shared per-H setup + |Q| | |H| skip)

The OPT version:
  - Compute DerivedSubgroup(H) ONCE
  - Compute abelianization hom ONCE
  - For each Q: skip if |Q| does not divide |H|
  - For prime Q: reuse cached A, just MaximalSubgroupClassReps of index p
  - For abelian non-prime Q: GQuotients on A (smaller) instead of H
  - For non-abelian Q: GQuotients on H (only after |Q| | |H| check passes)
"""
import os
import random
import re
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "compare_tiered_optimized_s12.log"
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

case_blocks = []
for cf in sample:
    gen_lines = parse_combo_file(cf)
    if not gen_lines: continue
    case_blocks.append({
        "combo": cf.stem,
        "partition": part_from_path(cf),
        "partition_tuple": tuple(int(x) for x in part_from_path(cf).strip("[]").split(",")),
        "gen_lines": gen_lines,
    })

GAP_LINES = [
    f'LogTo("{str(LOG).replace(chr(92), "/")}");',
    'Print("=== TRAD-W vs TIERED-W vs TIERED-W-OPT on 20 S12 combos ===\\n");',
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
    '# Original (per-Q setup, no shared)',
    '_TieredOrig := function(H)',
    '    local result, Q, sz, DH, hom, A, max_subs;',
    '    result := [];',
    '    for Q in Q_GROUPS do',
    '        sz := Size(Q);',
    '        if IsPrimeInt(sz) then',
    '            DH := DerivedSubgroup(H);',
    '            if Index(H, DH) mod sz <> 0 then continue; fi;',
    '            hom := NaturalHomomorphismByNormalSubgroup(H, DH);',
    '            A := Range(hom);',
    '            max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = sz);',
    '            Append(result, List(max_subs, K -> PreImage(hom, K)));',
    '        else',
    '            Append(result, Set(List(GQuotients(H, Q), Kernel)));',
    '        fi;',
    '    od;',
    '    return Set(result);',
    'end;',
    '',
    '# Optimized: shared per-H setup + |Q| | |H| skip',
    '_TieredOpt := function(H)',
    '    local DH, abel_hom, A, q_size_H, result, Q, sz, p, max_subs, epi;',
    '    q_size_H := Size(H);',
    '    DH := DerivedSubgroup(H);',
    '    if Size(DH) = q_size_H then',
    '        abel_hom := fail; A := fail;',
    '    else',
    '        abel_hom := NaturalHomomorphismByNormalSubgroup(H, DH);',
    '        A := Range(abel_hom);',
    '    fi;',
    '    result := [];',
    '    for Q in Q_GROUPS do',
    '        sz := Size(Q);',
    '        if q_size_H mod sz <> 0 then continue; fi;     # |Q| | |H| short-circuit',
    '        if IsPrimeInt(sz) then',
    '            if abel_hom = fail then continue; fi;',
    '            if Size(A) mod sz <> 0 then continue; fi;',
    '            max_subs := Filtered(MaximalSubgroupClassReps(A), K -> Index(A, K) = sz);',
    '            Append(result, List(max_subs, K -> PreImage(abel_hom, K)));',
    '        elif IsAbelian(Q) then',
    '            if abel_hom = fail then continue; fi;',
    '            for epi in GQuotients(A, Q) do',
    '                Add(result, PreImage(abel_hom, Kernel(epi)));',
    '            od;',
    '        else',
    '            Append(result, Set(List(GQuotients(H, Q), Kernel)));',
    '        fi;',
    '    od;',
    '    return Set(result);',
    'end;',
    '',
    'TimeOneH := function(H, S_M, W_ML)',
    '    local norm_W_t, N_W, ns_t, ns, filt_t, ns_filt,',
    '          trad_W_orb_t, tier_t, tier_kers, tier_W_orb_t,',
    '          opt_t, opt_kers, opt_W_orb_t;',
    '    norm_W_t := Runtime();',
    '    N_W := Normalizer(W_ML, H);',
    '    norm_W_t := Runtime() - norm_W_t;',
    '    ns_t := Runtime();',
    '    ns := NormalSubgroups(H);',
    '    ns_t := Runtime() - ns_t;',
    '    filt_t := Runtime();',
    '    ns_filt := Filtered(ns, K -> K <> H and Size(H)/Size(K) in Q_SIZE_FILTER);',
    '    filt_t := Runtime() - filt_t;',
    '    trad_W_orb_t := Runtime();',
    '    _OrbitRecs(H, N_W, ns_filt);',
    '    trad_W_orb_t := Runtime() - trad_W_orb_t;',
    '    tier_t := Runtime();',
    '    tier_kers := _TieredOrig(H);',
    '    tier_t := Runtime() - tier_t;',
    '    tier_W_orb_t := Runtime();',
    '    _OrbitRecs(H, N_W, tier_kers);',
    '    tier_W_orb_t := Runtime() - tier_W_orb_t;',
    '    opt_t := Runtime();',
    '    opt_kers := _TieredOpt(H);',
    '    opt_t := Runtime() - opt_t;',
    '    opt_W_orb_t := Runtime();',
    '    _OrbitRecs(H, N_W, opt_kers);',
    '    opt_W_orb_t := Runtime() - opt_W_orb_t;',
    '    return rec(',
    '        norm_W := norm_W_t, ns := ns_t, filt := filt_t,',
    '        trad_W_orb := trad_W_orb_t,',
    '        tier := tier_t, tier_W_orb := tier_W_orb_t, tier_count := Length(tier_kers),',
    '        opt := opt_t, opt_W_orb := opt_W_orb_t, opt_count := Length(opt_kers)',
    '    );',
    'end;',
    '',
    'agg := rec(',
    '    norm_W := 0, ns := 0, filt := 0, trad_W_orb := 0,',
    '    tier := 0, tier_W_orb := 0, opt := 0, opt_W_orb := 0,',
    '    h := 0, mismatch := 0',
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
    GAP_LINES.append(f'cb := rec(norm_W := 0, ns := 0, filt := 0, trad_W_orb := 0,'
                     f' tier := 0, tier_W_orb := 0, opt := 0, opt_W_orb := 0);')
    for gl in gen_lines:
        GAP_LINES.append(f'H := Group({gl});')
        GAP_LINES.append('res := TimeOneH(H, S_M, W_ML);')
        GAP_LINES.append('cb.norm_W := cb.norm_W + res.norm_W;')
        GAP_LINES.append('cb.ns := cb.ns + res.ns;')
        GAP_LINES.append('cb.filt := cb.filt + res.filt;')
        GAP_LINES.append('cb.trad_W_orb := cb.trad_W_orb + res.trad_W_orb;')
        GAP_LINES.append('cb.tier := cb.tier + res.tier;')
        GAP_LINES.append('cb.tier_W_orb := cb.tier_W_orb + res.tier_W_orb;')
        GAP_LINES.append('cb.opt := cb.opt + res.opt;')
        GAP_LINES.append('cb.opt_W_orb := cb.opt_W_orb + res.opt_W_orb;')
        GAP_LINES.append('agg.h := agg.h + 1;')
        GAP_LINES.append('if res.tier_count <> res.opt_count then agg.mismatch := agg.mismatch + 1; fi;')
    GAP_LINES.append('Print("  TRAD-W=", cb.norm_W + cb.ns + cb.filt + cb.trad_W_orb,'
                     '"ms  TIERED=", cb.norm_W + cb.tier + cb.tier_W_orb,'
                     '"ms  OPT=", cb.norm_W + cb.opt + cb.opt_W_orb, "ms\\n");')
    GAP_LINES.append('agg.norm_W := agg.norm_W + cb.norm_W;')
    GAP_LINES.append('agg.ns := agg.ns + cb.ns;')
    GAP_LINES.append('agg.filt := agg.filt + cb.filt;')
    GAP_LINES.append('agg.trad_W_orb := agg.trad_W_orb + cb.trad_W_orb;')
    GAP_LINES.append('agg.tier := agg.tier + cb.tier;')
    GAP_LINES.append('agg.tier_W_orb := agg.tier_W_orb + cb.tier_W_orb;')
    GAP_LINES.append('agg.opt := agg.opt + cb.opt;')
    GAP_LINES.append('agg.opt_W_orb := agg.opt_W_orb + cb.opt_W_orb;')

GAP_LINES.append(r'''
Print("\n=== AGGREGATE (across all H) ===\n");
Print("Total H:           ", agg.h, "\n");
Print("Mismatches (count vs opt): ", agg.mismatch, "\n\n");
Print("Norm in W_ML:      ", agg.norm_W, "ms\n");
Print("NormalSubgroups:   ", agg.ns, "ms\n");
Print("Filter:            ", agg.filt, "ms\n");
Print("OrbitDecomp/N_W:   ", agg.trad_W_orb, "ms\n");
Print("Tiered (orig) enum:", agg.tier, "ms\n");
Print("Tiered orbit:      ", agg.tier_W_orb, "ms\n");
Print("OPT enum:          ", agg.opt, "ms\n");
Print("OPT orbit:         ", agg.opt_W_orb, "ms\n\n");
Print("=== TOTAL TIME PER STRATEGY ===\n");
Print("TRAD-W:            ", agg.norm_W + agg.ns + agg.filt + agg.trad_W_orb, "ms\n");
Print("TIERED (orig):     ", agg.norm_W + agg.tier + agg.tier_W_orb, "ms\n");
Print("TIERED-OPT:        ", agg.norm_W + agg.opt + agg.opt_W_orb, "ms\n");
LogTo();
QUIT;
''')

(ROOT / "compare_tiered_optimized_s12.g").write_text("\n".join(GAP_LINES), encoding="utf-8")
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/compare_tiered_optimized_s12.g"
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
    print(text[-3500:])
