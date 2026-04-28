"""Test HoltRefineToElementaryAbelianLayers on representative p-group sections.

Verifies:
  - Each successive factor is EA p-group for the given p.
  - Chain endpoints match input N and C.
  - Non-p-group input returns [N, C] without refining.
  - Works for cyclic C_{p^k}, abelian-non-EA (C_4xC_2, C_9xC_3), and
    non-abelian 2-groups (D_8, Q_8).
"""

import os, subprocess, sys

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
LOG_FILE = os.path.join(LIFTING_DIR, "holt_engine", "tests", "refine_ea_log.txt")

gap_commands = f'''
LogTo("{LOG_FILE.replace(os.sep, "/")}");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/holt_engine/loader.g");

# ------------------------------------------------------------
# Helper: check that chain [H_0, ..., H_m] has EA p-group factors
# ------------------------------------------------------------
CheckEAChain := function(chain, p)
  local i, factor_size, d, quot_hom, quot;
  if Length(chain) < 2 then return true; fi;
  for i in [1..Length(chain)-1] do
    if Size(chain[i+1]) mod Size(chain[i]) <> 0 then
      Print("    FAIL: non-divisible sizes ", Size(chain[i]), " -> ", Size(chain[i+1]), "\\n");
      return false;
    fi;
    factor_size := Size(chain[i+1]) / Size(chain[i]);
    if factor_size = 1 then continue; fi;  # allow trivial steps
    d := LogInt(factor_size, p);
    if p^d <> factor_size then
      Print("    FAIL: factor size ", factor_size, " not a p-power for p=", p, "\\n");
      return false;
    fi;
    quot_hom := SafeNaturalHomByNSG(chain[i+1], chain[i]);
    if quot_hom = fail then
      Print("    FAIL: could not form quotient\\n");
      return false;
    fi;
    quot := ImagesSource(quot_hom);
    if not IsElementaryAbelian(quot) then
      Print("    FAIL: factor not EA (size=", factor_size, ")\\n");
      return false;
    fi;
  od;
  return true;
end;

test_count := 0;
pass_count := 0;

DoTest := function(name, G, N, C, p)
  local chain, ok;
  test_count := test_count + 1;
  Print("\\n--- ", name, " (|C|=", Size(C), ", |N|=", Size(N), ", p=", p, ") ---\\n");
  chain := HoltRefineToElementaryAbelianLayers(G, N, C, p);
  Print("  chain sizes: ", List(chain, Size), "\\n");
  ok := true;
  # Endpoints
  if Size(chain[1]) <> Size(N) then
    Print("    FAIL: chain[1] != N\\n"); ok := false;
  fi;
  if Size(chain[Length(chain)]) <> Size(C) then
    Print("    FAIL: chain[last] != C\\n"); ok := false;
  fi;
  # EA factors
  if not CheckEAChain(chain, p) then ok := false; fi;
  if ok then
    pass_count := pass_count + 1;
    Print("  OK\\n");
  fi;
end;

# ------------------------------------------------------------
# Test 1: V_4 = C_2 x C_2 (already EA) inside S_4, section 1 < V_4
# ------------------------------------------------------------
s4 := SymmetricGroup(4);
v4 := Group([(1,2)(3,4), (1,3)(2,4)]);
triv := TrivialSubgroup(s4);
DoTest("V_4 (already EA)", s4, triv, v4, 2);

# ------------------------------------------------------------
# Test 2: C_4 (cyclic, not EA) as section of D_8
# ------------------------------------------------------------
d8 := DihedralGroup(IsPermGroup, 8);
c4 := Subgroup(d8, [First(GeneratorsOfGroup(d8), g -> Order(g) = 4)]);
triv_d8 := TrivialSubgroup(d8);
DoTest("C_4 in D_8", d8, triv_d8, c4, 2);

# ------------------------------------------------------------
# Test 3: D_8 itself (non-abelian 2-group) section of D_8
# ------------------------------------------------------------
DoTest("D_8 full section", d8, triv_d8, d8, 2);

# ------------------------------------------------------------
# Test 4: Q_8 quaternion group (non-abelian 2-group)
# ------------------------------------------------------------
q8 := SmallGroup(8, 4);  # Q_8
q8_perm := Image(IsomorphismPermGroup(q8));
triv_q8 := TrivialSubgroup(q8_perm);
DoTest("Q_8 full section", q8_perm, triv_q8, q8_perm, 2);

# ------------------------------------------------------------
# Test 5: C_8 (cyclic of order 8, not EA) should refine to chain of C_2's
# ------------------------------------------------------------
c8 := CyclicGroup(IsPermGroup, 8);
triv_c8 := TrivialSubgroup(c8);
DoTest("C_8 cyclic", c8, triv_c8, c8, 2);

# ------------------------------------------------------------
# Test 6: C_4 x C_2 abelian not EA
# ------------------------------------------------------------
c4xc2 := DirectProduct(CyclicGroup(IsPermGroup, 4), CyclicGroup(IsPermGroup, 2));
triv_c4xc2 := TrivialSubgroup(c4xc2);
DoTest("C_4 x C_2 abelian", c4xc2, triv_c4xc2, c4xc2, 2);

# ------------------------------------------------------------
# Test 7: C_9 x C_3 at prime 3
# ------------------------------------------------------------
c9xc3 := DirectProduct(CyclicGroup(IsPermGroup, 9), CyclicGroup(IsPermGroup, 3));
triv_c9xc3 := TrivialSubgroup(c9xc3);
DoTest("C_9 x C_3 at p=3", c9xc3, triv_c9xc3, c9xc3, 3);

# ------------------------------------------------------------
# Test 8: non-p-group (C_6 = C_2 x C_3) at p=2 should return [N, C]
# ------------------------------------------------------------
c6 := CyclicGroup(IsPermGroup, 6);
triv_c6 := TrivialSubgroup(c6);
test_count := test_count + 1;
Print("\\n--- C_6 at p=2 (should NOT refine, mixed-prime) ---\\n");
chain := HoltRefineToElementaryAbelianLayers(c6, triv_c6, c6, 2);
Print("  chain length: ", Length(chain), " (expect 2)\\n");
if Length(chain) = 2 and Size(chain[1]) = 1 and Size(chain[2]) = 6 then
  pass_count := pass_count + 1;
  Print("  OK (returned [N, C] as expected)\\n");
else
  Print("  FAIL: expected [N, C], got sizes ", List(chain, Size), "\\n");
fi;

# ------------------------------------------------------------
# Test 9: trivial section C = N
# ------------------------------------------------------------
test_count := test_count + 1;
Print("\\n--- trivial section ---\\n");
chain := HoltRefineToElementaryAbelianLayers(s4, v4, v4, 2);
if Length(chain) = 1 and Size(chain[1]) = 4 then
  pass_count := pass_count + 1;
  Print("  OK (single-element chain for C = N)\\n");
else
  Print("  FAIL: expected [C], got sizes ", List(chain, Size), "\\n");
fi;

Print("\\n=== SUMMARY ===\\n");
Print("Passed: ", pass_count, "/", test_count, "\\n");
Print("All pass: ", pass_count = test_count, "\\n");

LogTo();
QUIT;
''';

cmd_file = os.path.join(LIFTING_DIR, "holt_engine", "tests", "temp_refine_ea.g")
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
    text=True, env=env, timeout=600,
)

print("=== stdout ===")
print(proc.stdout[-5000:])
if proc.stderr.strip():
    print("=== stderr ===")
    print(proc.stderr[-1500:])

os.remove(cmd_file)

ok = "All pass: true" in proc.stdout
print(f"\n[{'PASS' if ok else 'FAIL'}] HoltRefineToElementaryAbelianLayers")
sys.exit(0 if ok else 1)
