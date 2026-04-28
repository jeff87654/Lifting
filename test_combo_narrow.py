"""Narrow down: which prior combo causes combo 13 to crash?"""

import subprocess
import os
import time

def test_combos(combo_list, label):
    gap_commands = f'''
BreakOnError := false;
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
PrintTo("C:/Users/jeffr/Downloads/Lifting/narrow_result.txt", "{label}\\n");
'''
    for before, after in combo_list:
        gap_commands += f'''
AppendTo("C:/Users/jeffr/Downloads/Lifting/narrow_result.txt", "Testing {before} -> {after}...\\n");
{{
    local T42, T43, T21, shifted, offs, P, r;
    T42 := TransitiveGroup(4, 2);
    T43 := TransitiveGroup(4, 3);
    T21 := TransitiveGroup(2, 1);
    offs := [0, 4, 8];
'''
        if before == "7":
            gap_commands += '''
    shifted := [T42, ShiftGroup(TransitiveGroup(4,2), 4), ShiftGroup(T21, 8)];
'''
        elif before == "8":
            gap_commands += '''
    shifted := [T42, ShiftGroup(T43, 4), ShiftGroup(T21, 8)];
'''
        gap_commands += f'''
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
    r := FindFPFClassesByLifting(P, shifted, offs);
    AppendTo("C:/Users/jeffr/Downloads/Lifting/narrow_result.txt",
        "  {before}: ", Length(r), " results\\n");
    GASMAN("collect");
'''
        gap_commands += '''
    shifted := [T43, ShiftGroup(TransitiveGroup(4,3), 4), ShiftGroup(T21, 8)];
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
    r := FindFPFClassesByLifting(P, shifted, offs);
    AppendTo("C:/Users/jeffr/Downloads/Lifting/narrow_result.txt",
        "  13: ", Length(r), " results\\n");
};
'''

    gap_commands += '''
AppendTo("C:/Users/jeffr/Downloads/Lifting/narrow_result.txt", "DONE\\n");
QUIT;
'''

    with open(r"C:\Users\jeffr\Downloads\Lifting\temp_narrow.g", "w") as f:
        f.write(gap_commands)

    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_narrow.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    result_file = r"C:\Users\jeffr\Downloads\Lifting\narrow_result.txt"
    if os.path.exists(result_file):
        os.remove(result_file)

    start = time.time()
    with open(os.devnull, "w") as devnull:
        process = subprocess.Popen(
            [bash_exe, "--login", "-c",
             f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 2G "{script_path}"'],
            stdout=devnull,
            stderr=devnull,
            text=True,
            env=env,
            cwd=gap_runtime
        )
        process.wait(timeout=120)

    elapsed = time.time() - start
    print(f"  {label}: {elapsed:.1f}s, exit={process.returncode}")

    if os.path.exists(result_file):
        with open(result_file, 'r') as f:
            content = f.read()
            print(f"  -> {content.strip()}")
            return "DONE" in content
    return False

# Test A: just combo 13 alone (should work)
gap_commands_a = '''
BreakOnError := false;
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
PrintTo("C:/Users/jeffr/Downloads/Lifting/narrow_result.txt", "Test A: combo 13 alone\\n");
{
    local T43, T21, shifted, offs, P, r;
    T43 := TransitiveGroup(4, 3);
    T21 := TransitiveGroup(2, 1);
    offs := [0, 4, 8];
    shifted := [T43, ShiftGroup(TransitiveGroup(4,3), 4), ShiftGroup(T21, 8)];
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
    r := FindFPFClassesByLifting(P, shifted, offs);
    AppendTo("C:/Users/jeffr/Downloads/Lifting/narrow_result.txt",
        "  Result: ", Length(r), "\\nDONE\\n");
};
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_narrow.g", "w") as f:
    f.write(gap_commands_a)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_narrow.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

result_file = r"C:\Users\jeffr\Downloads\Lifting\narrow_result.txt"
if os.path.exists(result_file):
    os.remove(result_file)

print("Test A: combo 13 alone...")
start = time.time()
with open(os.devnull, "w") as devnull:
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 2G "{script_path}"'],
        stdout=devnull, stderr=devnull, text=True, env=env, cwd=gap_runtime
    )
    process.wait(timeout=120)
elapsed = time.time() - start
print(f"  Time: {elapsed:.1f}s, exit={process.returncode}")
if os.path.exists(result_file):
    with open(result_file, 'r') as f:
        print(f"  -> {f.read().strip()}")

# Test B: combo 7 then 13
gap_commands_b = '''
BreakOnError := false;
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
PrintTo("C:/Users/jeffr/Downloads/Lifting/narrow_result.txt", "Test B: 7 then 13\\n");
{
    local T42, T43, T21, shifted, offs, P, r;
    T42 := TransitiveGroup(4, 2);
    T43 := TransitiveGroup(4, 3);
    T21 := TransitiveGroup(2, 1);
    offs := [0, 4, 8];

    shifted := [T42, ShiftGroup(TransitiveGroup(4,2), 4), ShiftGroup(T21, 8)];
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
    r := FindFPFClassesByLifting(P, shifted, offs);
    AppendTo("C:/Users/jeffr/Downloads/Lifting/narrow_result.txt",
        "  7: ", Length(r), "\\n");
    GASMAN("collect");

    shifted := [T43, ShiftGroup(TransitiveGroup(4,3), 4), ShiftGroup(T21, 8)];
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
    r := FindFPFClassesByLifting(P, shifted, offs);
    AppendTo("C:/Users/jeffr/Downloads/Lifting/narrow_result.txt",
        "  13: ", Length(r), "\\nDONE\\n");
};
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_narrow.g", "w") as f:
    f.write(gap_commands_b)

if os.path.exists(result_file):
    os.remove(result_file)

print("\nTest B: combo 7 then 13...")
start = time.time()
with open(os.devnull, "w") as devnull:
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 2G "{script_path}"'],
        stdout=devnull, stderr=devnull, text=True, env=env, cwd=gap_runtime
    )
    process.wait(timeout=120)
elapsed = time.time() - start
print(f"  Time: {elapsed:.1f}s, exit={process.returncode}")
if os.path.exists(result_file):
    with open(result_file, 'r') as f:
        print(f"  -> {f.read().strip()}")

# Test C: combo 8 then 13
gap_commands_c = '''
BreakOnError := false;
Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
PrintTo("C:/Users/jeffr/Downloads/Lifting/narrow_result.txt", "Test C: 8 then 13\\n");
{
    local T42, T43, T21, shifted, offs, P, r;
    T42 := TransitiveGroup(4, 2);
    T43 := TransitiveGroup(4, 3);
    T21 := TransitiveGroup(2, 1);
    offs := [0, 4, 8];

    shifted := [T42, ShiftGroup(T43, 4), ShiftGroup(T21, 8)];
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
    r := FindFPFClassesByLifting(P, shifted, offs);
    AppendTo("C:/Users/jeffr/Downloads/Lifting/narrow_result.txt",
        "  8: ", Length(r), "\\n");
    GASMAN("collect");

    shifted := [T43, ShiftGroup(TransitiveGroup(4,3), 4), ShiftGroup(T21, 8)];
    P := Group(Concatenation(List(shifted, GeneratorsOfGroup)));
    r := FindFPFClassesByLifting(P, shifted, offs);
    AppendTo("C:/Users/jeffr/Downloads/Lifting/narrow_result.txt",
        "  13: ", Length(r), "\\nDONE\\n");
};
QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_narrow.g", "w") as f:
    f.write(gap_commands_c)

if os.path.exists(result_file):
    os.remove(result_file)

print("\nTest C: combo 8 then 13...")
start = time.time()
with open(os.devnull, "w") as devnull:
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 2G "{script_path}"'],
        stdout=devnull, stderr=devnull, text=True, env=env, cwd=gap_runtime
    )
    process.wait(timeout=120)
elapsed = time.time() - start
print(f"  Time: {elapsed:.1f}s, exit={process.returncode}")
if os.path.exists(result_file):
    with open(result_file, 'r') as f:
        print(f"  -> {f.read().strip()}")
