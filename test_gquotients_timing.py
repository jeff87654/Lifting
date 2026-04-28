"""test_gquotients_timing.py — profile GQuotients(H, Q) on a range of test
groups H and target quotients Q ∈ {C_2, S_3, S_4}.  For smaller groups,
also time NormalSubgroups(H) for comparison.

Goal: determine whether the GQuotients-per-Q-type strategy scales to
S19/S20 and to the full S12-S18 LEFT subgroup catalog.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "test_gquotients_timing.log"
if LOG.exists():
    LOG.unlink()

# Test cases: (description, GAP construction code, do_normalsubgroups_too)
TESTS = [
    # Small / medium
    ("D_8 = TG(4,3)",            "TransitiveGroup(4, 3)",                                 True),
    ("S_4 = TG(4,5)",            "TransitiveGroup(4, 5)",                                 True),
    ("C_3^2",                    "DirectProduct(CyclicGroup(IsPermGroup, 3), CyclicGroup(IsPermGroup, 3))",  True),
    ("D_8^2",                    "DirectProduct(TransitiveGroup(4,3), TransitiveGroup(4,3))",       True),
    ("S_3^2",                    "DirectProduct(SymmetricGroup(3), SymmetricGroup(3))",            True),
    # S12-typical LEFTs
    ("D_8^3 (S12 [4,3]^3 LEFT)", "DirectProduct(TransitiveGroup(4,3), TransitiveGroup(4,3), TransitiveGroup(4,3))", True),
    ("S_4^3 (S12 [4,5]^3)",      "DirectProduct(TransitiveGroup(4,5), TransitiveGroup(4,5), TransitiveGroup(4,5))", True),
    ("S_3^3 (S9 [3,2]^3)",       "DirectProduct(SymmetricGroup(3), SymmetricGroup(3), SymmetricGroup(3))",         True),
    # The big ones — do NormalSubgroups too with longer expected time
    ("D_8^4 (S16 [4,3]^4 LEFT)", "DirectProduct(TransitiveGroup(4,3), TransitiveGroup(4,3), TransitiveGroup(4,3), TransitiveGroup(4,3))", False),
]

GAP_SCRIPT = f'''
LogTo("{str(LOG).replace(chr(92), "/")}");
Print("=== GQuotients vs NormalSubgroups timing ===\\n\\n");

# Target quotients of interest for S19/S20
C2 := CyclicGroup(IsPermGroup, 2);
S3 := SymmetricGroup(3);
C4 := CyclicGroup(IsPermGroup, 4);
V4 := DirectProduct(CyclicGroup(IsPermGroup, 2), CyclicGroup(IsPermGroup, 2));
D8 := TransitiveGroup(4, 3);
A4 := AlternatingGroup(4);
S4 := SymmetricGroup(4);

TARGETS := [
    rec(name := "C_2", G := C2),
    rec(name := "S_3", G := S3),
    rec(name := "S_4", G := S4)
];

# Time helper: returns (elapsed_ms, kernel_count)
TimeGQuotients := function(H, Q)
    local t, gqs, kers;
    t := Runtime();
    gqs := GQuotients(H, Q);
    kers := Set(List(gqs, Kernel));
    return [Runtime() - t, Length(kers), Length(gqs)];
end;

TimeNormalSubgroups := function(H)
    local t, NS;
    t := Runtime();
    NS := NormalSubgroups(H);
    return [Runtime() - t, Length(NS)];
end;
'''

# Build the GAP code for each test
test_code_blocks = []
for name, construct_code, do_ns in TESTS:
    do_ns_gap = "true" if do_ns else "false"
    block = f'''
Print("\\n--- {name} ---\\n");
H := {construct_code};
Print("|H| = ", Size(H), "\\n");
for tgt in TARGETS do
    res := TimeGQuotients(H, tgt.G);
    Print("  GQuotients(H, ", tgt.name, "): ",
          res[1], "ms  kernels=", res[2], " homs=", res[3], "\\n");
od;
if {do_ns_gap} then
    res := TimeNormalSubgroups(H);
    Print("  NormalSubgroups(H):  ", res[1], "ms  count=", res[2], "\\n");
else
    Print("  NormalSubgroups(H):  (skipped — would take many minutes)\\n");
fi;
'''
    test_code_blocks.append(block)

GAP_SCRIPT += "\n".join(test_code_blocks)
GAP_SCRIPT += '''
Print("\\n=== done ===\\n");
LogTo();
QUIT;
'''

(ROOT / "test_gquotients_timing.g").write_text(GAP_SCRIPT, encoding="utf-8")

bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_gquotients_timing.g"

env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"

print(f"Running GQuotients timing tests... (log: {LOG})")
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cyg}"'],
    env=env,
)
print(f"GAP rc={proc.returncode}")
print()
print(LOG.read_text(encoding="utf-8") if LOG.exists() else "(no log)")
