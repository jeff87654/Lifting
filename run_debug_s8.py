import subprocess
import os

log_file = "C:/Users/jeffr/Downloads/Lifting/gap_output_debug_s8.log"

gap_commands = f'''
LogTo("{log_file}");
Print("Debug S8 Test\\n");
Print("==============\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Clear all caches
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;

# Test 1: S8 with orbit invariant (current code)
Print("\\n=== Test 1: S8 with orbit invariant ===\\n");
result1 := CountAllConjugacyClassesFast(8);
Print("S8 result with orbit inv: ", result1, "\\n");

# Now redefine invariant functions WITHOUT orbit structure
# Save the current functions
OrigComputeSubgroupInvariant := ComputeSubgroupInvariant;
OrigCheapSubgroupInvariant := CheapSubgroupInvariant;

# Redefine without orbit structure
ComputeSubgroupInvariant := function(H)
    local inv, center, derived, abelianInv, orderStats, elts, o, sizeH;
    sizeH := Size(H);
    inv := [sizeH, DerivedLength(H), Length(ConjugacyClasses(H))];
    center := Center(H);
    Add(inv, Size(center));
    derived := DerivedSubgroup(H);
    Add(inv, Size(derived));
    abelianInv := ShallowCopy(AbelianInvariants(H));
    Sort(abelianInv);
    Add(inv, abelianInv);
    Add(inv, Exponent(H));
    if sizeH <= 500 then
        orderStats := rec();
        for elts in ConjugacyClasses(H) do
            o := Order(Representative(elts));
            if not IsBound(orderStats.(String(o))) then
                orderStats.(String(o)) := 0;
            fi;
            orderStats.(String(o)) := orderStats.(String(o)) + Size(elts);
        od;
        Add(inv, SortedList(List(RecNames(orderStats),
            n -> [Int(n), orderStats.(n)])));
    else
        Add(inv, []);
    fi;
    return inv;
end;

CheapSubgroupInvariant := function(H)
    local inv, abelianInv;
    inv := [Size(H)];
    Add(inv, Size(DerivedSubgroup(H)));
    Add(inv, Size(Center(H)));
    Add(inv, Exponent(H));
    Add(inv, NrConjugacyClasses(H));
    abelianInv := ShallowCopy(AbelianInvariants(H));
    Sort(abelianInv);
    Add(inv, abelianInv);
    return inv;
end;

# Test 2: S8 without orbit invariant
Print("\\n=== Test 2: S8 without orbit invariant ===\\n");
FPF_SUBDIRECT_CACHE := rec();
LIFT_CACHE := rec();
if IsBound(ClearH1Cache) then ClearH1Cache(); fi;
result2 := CountAllConjugacyClassesFast(8);
Print("S8 result without orbit inv: ", result2, "\\n\\n");

Print("Expected: 296\\n");
Print("With orbit inv: ", result1, "\\n");
Print("Without orbit inv: ", result2, "\\n");
LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_commands.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_commands.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print("Running S8 debug tests...")

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
    cwd=gap_runtime
)

stdout, stderr = process.communicate(timeout=300)

log_path = r"C:\Users\jeffr\Downloads\Lifting\gap_output_debug_s8.log"
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    lines = log.split('\n')
    for line in lines:
        if any(kw in line for kw in ['result', 'Expected', 'Total S_', 'Partition', 'Final count', 'Test']):
            print(line.strip())
else:
    print("Log not found")
    print("stdout:", stdout[-1000:])
    print("stderr:", stderr[-500:])
