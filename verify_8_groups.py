"""Verify the 8 prebugfix groups for combo [2,1]_[6,16]_[10,32] in partition
[10,6,2]:

  1. Sanity: each has the right size (product of factor sizes: 2*48*3840).
     Wait — |TG(2,1)| * |TG(6,16)| * |TG(10,32)| = 2 * 48 * 3840 = 368640.
  2. Each is an FPF subdirect (IsFPFSubdirect returns true).
  3. Pairwise non-N-conjugate where N = N_{S_18}(T_{10}) x ... acting on S_18.
  4. How does the current set of 6 relate — which of the 8 are covered?

Also run current 6 to confirm they're also valid + distinct.
"""
import subprocess, os

code = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/verify_8.log");
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# --- 8 prebugfix groups ---
prebug_gens_list := [
  [(1,2,10)(3,4,5)(6,7,8),(1,3,2,6)(4,5,8,7),(1,2)(4,7)(5,8)(9,10),(3,6)(4,7)(5,8),(11,12,13,14,15,16),(11,12),(17,18)],
  [(17,18),(4,8)(5,7)(9,10)(15,16),(1,8,3)(2,6,4)(5,10,7),(1,10)(2,9)(3,6)(4,7),(11,12,16),(12,15,14),(12,16,14,13,15)],
  [(1,5,9,10,4)(2,6,7,8,3)(11,12,14,13,16),(1,9,8,3)(4,6,10,5)(11,12,15,16)(13,14),(2,4)(3,8)(7,10)(11,15)(12,13)(14,16),(17,18)],
  [(15,16)(17,18),(4,8)(5,7)(9,10),(1,8,3)(2,6,4)(5,10,7),(1,10)(2,9)(3,6)(4,7),(11,12,16),(12,15,14),(12,16,14,13,15)],
  [(15,16)(17,18),(4,8)(5,7)(9,10)(15,16),(1,8,3)(2,6,4)(5,10,7),(1,10)(2,9)(3,6)(4,7),(11,12,16),(12,15,14),(12,16,14,13,15)],
  [(4,8)(5,7)(9,10)(17,18),(1,8,3)(2,6,4)(5,10,7),(1,10)(2,9)(3,6)(4,7),(11,12,13,14,15,16),(11,12)],
  [(4,8)(5,7)(9,10)(15,16)(17,18),(1,8,3)(2,6,4)(5,10,7),(1,10)(2,9)(3,6)(4,7),(11,12,16),(12,15,14),(12,16,14,13,15)],
  [(1,5,3,7)(4,10,9,8)(11,14,12,13)(15,16),(1,7,10,5,2)(3,4,8,6,9)(11,13,14,15,16),(2,6)(4,9)(8,10)(15,16)(17,18)]
];;

current_gens_list := [
  [(11,12,13,14,15,16),(11,12),(1,2,10)(3,4,5)(6,7,8),(1,3,2,6)(4,5,8,7),(1,2)(4,7)(5,8)(9,10),(3,6)(4,7)(5,8)(17,18)],
  [(11,12,13,14,15),(14,15,16),(1,7,2)(3,5,6)(4,10,9),(1,5)(2,9)(4,6)(8,10),(1,10)(2,9)(3,6)(4,7),(3,6)(4,7)(5,8)(11,12)(17,18)],
  [(11,12,13,14,15,16),(11,12),(1,2,10)(3,4,5)(6,7,8),(1,3,2,6)(4,5,8,7),(1,2)(4,7)(5,8)(9,10),(3,6)(4,7)(5,8),(17,18)],
  [(11,12,13,14,15),(14,15,16),(4,8)(5,7)(9,10)(17,18),(1,4,5,7,10)(2,8,9,6,3),(1,2,5,10,7)(3,9,6,8,4),(3,6)(4,7)(5,8)(11,12)],
  [(11,12,13,14,15),(14,15,16),(4,8)(5,7)(9,10),(1,4,5,7,10)(2,8,9,6,3),(1,2,5,10,7)(3,9,6,8,4),(11,12)(17,18)],
  [(11,12,13,14,15),(14,15,16),(1,7,2)(3,5,6)(4,10,9),(1,5)(2,9)(4,6)(8,10),(1,10)(2,9)(3,6)(4,7),(17,18),(3,6)(4,7)(5,8)(11,12)]
];;

prebug := List(prebug_gens_list, g -> Group(g));;
current := List(current_gens_list, g -> Group(g));;

# Factors and partition normalizer
T2 := TransitiveGroup(2, 1);;
T6 := TransitiveGroup(6, 16);;
T10 := TransitiveGroup(10, 32);;
offsets := [0, 2, 8];;  # [2,1] on 1..2, [6,16] on 3..8, [10,32] on 9..18 — BUT sort by size desc first.
# Actually partition [10,6,2] is stored descending, so:
#   block1 (deg 10) = points 1..10
#   block2 (deg 6)  = points 11..16
#   block3 (deg 2)  = points 17..18
shifted := [ShiftGroup(T10, 0), ShiftGroup(T6, 10), ShiftGroup(T2, 16)];;
shifted_factors := shifted;;
part_offsets := [0, 10, 16];;

# Per-combo normalizer N for this partition.
N := BuildPerComboNormalizer([10, 6, 2], [T10, T6, T2], 18);;
Print("|N| = ", Size(N), "\\n\\n");

# --- Step 1: check each group's size matches product of factor sizes ---
expected_size := Size(T2) * Size(T6) * Size(T10);;
Print("Expected size: |T2|*|T6|*|T10| = ", Size(T2), "*", Size(T6), "*", Size(T10),
      " = ", expected_size, "\\n\\n");

Print("--- Prebugfix (8 groups) ---\\n");
for i in [1..Length(prebug)] do
    Print("  prebug[", i, "]: |G| = ", Size(prebug[i]), " ",
          "FPF = ", IsFPFSubdirect(prebug[i], shifted_factors, part_offsets),
          "\\n");
od;
Print("\\n");

Print("--- Current (6 groups) ---\\n");
for i in [1..Length(current)] do
    Print("  current[", i, "]: |G| = ", Size(current[i]), " ",
          "FPF = ", IsFPFSubdirect(current[i], shifted_factors, part_offsets),
          "\\n");
od;
Print("\\n");

# --- Step 2: pairwise N-conjugation among prebugfix ---
Print("--- Prebugfix pairwise N-conjugation ---\\n");
for i in [1..Length(prebug)] do
    for j in [i+1..Length(prebug)] do
        if Size(prebug[i]) = Size(prebug[j]) then
            if RepresentativeAction(N, prebug[i], prebug[j]) <> fail then
                Print("  prebug[", i, "] ~ prebug[", j, "] (N-conjugate!)\\n");
            fi;
        fi;
    od;
od;
Print("\\n");

# --- Step 3: pairwise N-conjugation among current ---
Print("--- Current pairwise N-conjugation ---\\n");
for i in [1..Length(current)] do
    for j in [i+1..Length(current)] do
        if Size(current[i]) = Size(current[j]) then
            if RepresentativeAction(N, current[i], current[j]) <> fail then
                Print("  current[", i, "] ~ current[", j, "] (N-conjugate!)\\n");
            fi;
        fi;
    od;
od;
Print("\\n");

# --- Step 4: which prebug groups are N-conjugate to some current ---
Print("--- Prebug vs Current ---\\n");
for i in [1..Length(prebug)] do
    matched := 0;
    for j in [1..Length(current)] do
        if Size(prebug[i]) = Size(current[j]) then
            if RepresentativeAction(N, prebug[i], current[j]) <> fail then
                matched := j;
                break;
            fi;
        fi;
    od;
    if matched > 0 then
        Print("  prebug[", i, "] ~ current[", matched, "]\\n");
    else
        Print("  prebug[", i, "] NOT MATCHED in current (size=", Size(prebug[i]), ")\\n");
    fi;
od;
Print("\\n");

# --- Step 5: For unmatched prebug groups, check FPF more carefully ---
# and check if they're actually FPF subdirect in the strict sense.
Print("--- Detailed check of unmatched prebug groups ---\\n");
for i in [1..Length(prebug)] do
    matched := 0;
    for j in [1..Length(current)] do
        if Size(prebug[i]) = Size(current[j]) then
            if RepresentativeAction(N, prebug[i], current[j]) <> fail then
                matched := j; break;
            fi;
        fi;
    od;
    if matched = 0 then
        Print("  prebug[", i, "]:\\n");
        Print("    |G| = ", Size(prebug[i]), "\\n");
        Print("    IsFPFSubdirect = ", IsFPFSubdirect(prebug[i], shifted_factors, part_offsets), "\\n");
        # Check orbits
        orbits := Orbits(prebug[i], [1..18]);
        Print("    Orbits: ", List(orbits, o -> Length(o)), "\\n");
        # Check transitivity on each block
        # Block 1: 1..10
        restr1 := Stabilizer(prebug[i], [11..18], OnTuples);
        # Actually let's just check projection to each block.
        # For projection to block 1 (1..10), take image of each gen restricted.
        # This is awkward in GAP. Let's instead check if orbits cover each block.
        Print("    Orbits on 1..10: ", Filtered(orbits, o -> ForAll(o, x -> x <= 10)), "\\n");
        Print("    Orbits on 11..16: ", Filtered(orbits, o -> ForAll(o, x -> x > 10 and x <= 16)), "\\n");
        Print("    Orbits on 17..18: ", Filtered(orbits, o -> ForAll(o, x -> x > 16)), "\\n");
    fi;
od;

LogTo();
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\tmp_verify_8.g", "w") as f:
    f.write(code)

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

p = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/tmp_verify_8.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
try:
    p.communicate(timeout=900)
except subprocess.TimeoutExpired:
    p.kill(); p.communicate()

log = open(r"C:\Users\jeffr\Downloads\Lifting\verify_8.log").read()
# Show just the verification output, skip load messages
started = False
for line in log.splitlines():
    if "|N| =" in line:
        started = True
    if started:
        print(line)
