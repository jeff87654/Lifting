"""Profile combo (T(6,14), T(5,5)) -- partition [6,5] of S_11.

Same phase breakdown as profile_slow_combo.py.
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "profile_combo_6_14_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_TF_STRICT_MISS := false;

shift_group := function(G, offset)
  return Group(List(GeneratorsOfGroup(G),
    g -> PermList(Concatenation(
      [1..offset],
      List([1..LargestMovedPoint(G)], i -> offset + i^g)))));
end;

# Partition [6,5]: T(6,14) on pts 1..6, T(5,5)=S_5 on pts 7..11
t1_raw := TransitiveGroup(6, 14);
t2_raw := TransitiveGroup(5, 5);
Print("T(6,14) = ", StructureDescription(t1_raw), " |=", Size(t1_raw), "\\n");
Print("T(5,5)  = ", StructureDescription(t2_raw), " |=", Size(t2_raw), "\\n");

t1 := t1_raw;
t2 := shift_group(t2_raw, 6);

P := Group(Concatenation(
  GeneratorsOfGroup(t1),
  GeneratorsOfGroup(t2)));
shifted := [t1, t2];
offs := [0, 6];

Print("|P| = ", Size(P), ", |Radical(P)| = ", Size(RadicalGroup(P)), "\\n");
Print("IsSolvable(P) = ", IsSolvableGroup(P), "\\n");

time_phase := function(label, f)
  local t0, result, elapsed;
  t0 := Runtime();
  result := f();
  elapsed := Runtime() - t0;
  Print("[", elapsed, "ms] ", label, "\\n");
  return result;
end;

# ---- Phase 1: series ----
Print("\\n=== Phase 1: series construction ===\\n");
series_rec := time_phase("HoltBuildLiftSeries(P)",
  function() return HoltBuildLiftSeries(P); end);
Print("  radical=", Size(series_rec.radical), ", layers=",
      Length(series_rec.layers), "\\n");
Print("  layer sizes: ", List(series_rec.layers,
  lay -> Concatenation(String(lay.p), "^", String(lay.d))), "\\n");

# ---- Phase 2: HoltTopClasses ----
Print("\\n=== Phase 2: HoltTopClasses ===\\n");
top_classes := time_phase("HoltTopClasses(P, series_rec)",
  function() return HoltTopClasses(P, series_rec); end);
Print("  ", Length(top_classes), " top classes, sizes: ", List(top_classes, Size), "\\n");

# ---- Phase 3: clean ----
Print("\\n=== Phase 3: HoltFPFSubgroupClassesOfProduct (clean) ===\\n");
BreakOnError := false;
t0 := Runtime();
clean_result := CALL_WITH_CATCH(
  function() return HoltFPFSubgroupClassesOfProduct(P, shifted, offs); end,
  []);
elapsed := Runtime() - t0;
BreakOnError := true;
Print("[", elapsed, "ms] clean path finished (success=", clean_result[1], ")\\n");
if clean_result[1] then
  Print("  ", Length(clean_result[2]), " FPF classes via clean\\n");
fi;

# ---- Phase 4: max-rec ----
Print("\\n=== Phase 4: HoltFPFViaMaximals (max-rec) ===\\n");
t0 := Runtime();
maxrec_result := HoltFPFViaMaximals(P, shifted, offs);
elapsed := Runtime() - t0;
Print("[", elapsed, "ms] HoltFPFViaMaximals returned ",
      Length(maxrec_result), " FPF classes\\n");

# Phase 4a: breakdown
Print("\\n=== Phase 4a: HoltSubgroupsViaMaximals breakdown ===\\n");
t0 := Runtime();
all_subs := HoltSubgroupsViaMaximals(P);
elapsed := Runtime() - t0;
Print("[", elapsed, "ms] HoltSubgroupsViaMaximals: ", Length(all_subs), " subgroups\\n");
t0 := Runtime();
fpf_filtered := Filtered(all_subs, H -> IsFPFSubdirect(H, shifted, offs));
elapsed := Runtime() - t0;
Print("[", elapsed, "ms] IsFPFSubdirect filter: ", Length(fpf_filtered), " survived\\n");

# ---- Phase 5: legacy ----
Print("\\n=== Phase 5: legacy FindFPFClassesByLifting ===\\n");
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
legacy_result := FindFPFClassesByLifting(P, shifted, offs);
elapsed := Runtime() - t0;
Print("[", elapsed, "ms] legacy returned ", Length(legacy_result), " FPF classes\\n");

Print("\\n========== SUMMARY ==========\\n");
Print("Partition [6,5], factors T(6,14) x T(5,5)\\n");
Print("|P| = ", Size(P), "\\n");
Print("FPF counts: max-rec=", Length(maxrec_result),
      ", legacy=", Length(legacy_result), "\\n");
Print("match: ", Length(maxrec_result) = Length(legacy_result), "\\n");

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "temp_profile_6_14.g")
with open(cmd_file, "w", encoding="utf-8") as f:
    f.write(gap_commands)

bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = cmd_file.replace("C:\\", "/cygdrive/c/").replace("\\", "/")
gap_dir = '/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1'

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

if os.path.exists(LOG_FILE):
    os.remove(LOG_FILE)

proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "{gap_dir}" && ./gap.exe -q -o 0 "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env=env, timeout=1800,
)

os.remove(cmd_file)

# Parse phase lines from log
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.rstrip()
            if s.startswith("[") or s.startswith("===") or s.startswith("  "):
                print(s)

ok = "match: true" in proc.stdout
print(f"\n[{'PASS' if ok else 'FAIL'}] profile run")
sys.exit(0 if ok else 1)
