"""Profile the slow combo [T(5,5), T(4,1), T(2,1)] on S_11, |P|=960.

Breaks the dispatcher routing into timed phases:
  phase 1: series construction (HoltBuildLiftSeries vs *FromProduct)
  phase 2: HoltTopClasses / HoltLoadTFClasses (TF database lookup)
  phase 3: HoltFPFSubgroupClassesOfProduct (clean Holt, likely errors)
  phase 4: HoltFPFViaMaximals (max-recursion fallback)
  phase 5: HoltSubgroupsViaMaximals recursion depth breakdown

Also runs the legacy FindFPFClassesByLifting for timing comparison.
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "profile_slow_combo_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");
USE_HOLT_ENGINE := true;
HOLT_TF_STRICT_MISS := false;

# ---- Build the combo exactly as the outer loop does ----
# Partition [5,4,2]: T(5,5)=S_5 on pts 1..5, T(4,1)=C_4 on 6..9, T(2,1)=C_2 on 10..11.

shift_group := function(G, offset)
  return Group(List(GeneratorsOfGroup(G),
    g -> PermList(Concatenation(
      [1..offset],
      List([1..LargestMovedPoint(G)], i -> offset + i^g)))));
end;

t1 := TransitiveGroup(5, 5);                  # S_5
t2 := shift_group(TransitiveGroup(4, 1), 5);  # C_4 shifted to 6..9
t3 := shift_group(TransitiveGroup(2, 1), 9);  # C_2 shifted to 10..11

P := Group(Concatenation(
  GeneratorsOfGroup(t1),
  GeneratorsOfGroup(t2),
  GeneratorsOfGroup(t3)));
shifted := [t1, t2, t3];
offs := [0, 5, 9];

Print("|P| = ", Size(P), " (expect 960)\\n");
Print("|RadicalGroup(P)| = ", Size(RadicalGroup(P)), "\\n");

time_phase := function(label, f)
  local t0, result, elapsed;
  t0 := Runtime();
  result := f();
  elapsed := Runtime() - t0;
  Print("[", elapsed, "ms] ", label, "\\n");
  return result;
end;

# ---- Phase 1: series construction ----
Print("\\n=== Phase 1: series construction ===\\n");
series_generic := time_phase("HoltBuildLiftSeries(P)",
  function() return HoltBuildLiftSeries(P); end);
Print("  radical=", Size(series_generic.radical), ", layers=",
      Length(series_generic.layers), "\\n");

# If P is solvable we'd use FromProduct; |P|=960 has A_5 factor so non-solvable.
Print("  IsSolvable(P) = ", IsSolvableGroup(P), "\\n");
if IsSolvableGroup(P) then
  series_prod := time_phase("HoltBuildLiftSeriesFromProduct(P, shifted)",
    function() return HoltBuildLiftSeriesFromProduct(P, shifted); end);
  Print("  radical=", Size(series_prod.radical), ", layers=",
        Length(series_prod.layers), "\\n");
fi;

# ---- Phase 2: HoltTopClasses ----
Print("\\n=== Phase 2: HoltTopClasses (TF db lookup) ===\\n");
top_classes := time_phase("HoltTopClasses(P, series_generic)",
  function() return HoltTopClasses(P, series_generic); end);
Print("  ", Length(top_classes), " top classes\\n");
Print("  top class sizes: ", List(top_classes, Size), "\\n");

# ---- Phase 3: clean path (likely errors) ----
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

# ---- Phase 4: max-rec fallback ----
Print("\\n=== Phase 4: HoltFPFViaMaximals (max-rec) ===\\n");
t0 := Runtime();
maxrec_result := HoltFPFViaMaximals(P, shifted, offs);
elapsed := Runtime() - t0;
Print("[", elapsed, "ms] HoltFPFViaMaximals returned ",
      Length(maxrec_result), " FPF classes\\n");

# ---- Phase 4a: just the subgroup enumeration, no FPF filter ----
Print("\\n=== Phase 4a: HoltSubgroupsViaMaximals breakdown ===\\n");
t0 := Runtime();
all_subs := HoltSubgroupsViaMaximals(P);
elapsed := Runtime() - t0;
Print("[", elapsed, "ms] HoltSubgroupsViaMaximals: ", Length(all_subs), " subgroups\\n");
t0 := Runtime();
fpf_filtered := Filtered(all_subs, H -> IsFPFSubdirect(H, shifted, offs));
elapsed := Runtime() - t0;
Print("[", elapsed, "ms] IsFPFSubdirect filter: ", Length(fpf_filtered), " survived\\n");

# ---- Phase 5: legacy for comparison ----
Print("\\n=== Phase 5: legacy FindFPFClassesByLifting ===\\n");
FPF_SUBDIRECT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
t0 := Runtime();
legacy_result := FindFPFClassesByLifting(P, shifted, offs);
elapsed := Runtime() - t0;
Print("[", elapsed, "ms] legacy returned ", Length(legacy_result), " FPF classes\\n");

# ---- Summary ----
Print("\\n========== SUMMARY ==========\\n");
Print("|P|=960 = S_5 x C_4 x C_2 (non-solvable)\\n");
Print("FPF class counts: max-rec=", Length(maxrec_result),
      ", legacy=", Length(legacy_result), "\\n");
Print("match: ", Length(maxrec_result) = Length(legacy_result), "\\n");

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "temp_profile_slow_combo.g")
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
    text=True, env=env, timeout=900,
)

print("=== stdout tail ===")
print(proc.stdout[-5000:])

os.remove(cmd_file)

# Parse and print the phase breakdown compactly
if os.path.exists(LOG_FILE):
    print("\n=== PHASE BREAKDOWN (from log) ===")
    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("[") or line.startswith("==="):
                print(line.rstrip())

ok = "match: true" in proc.stdout
print(f"\n[{'PASS' if ok else 'FAIL'}] profile run")
sys.exit(0 if ok else 1)
