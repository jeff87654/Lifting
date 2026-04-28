"""Test combo 13 without loading the database."""

import subprocess
import os
import time

# Temporarily rename the database loader so it doesn't auto-load
db_loader = r"C:\Users\jeffr\Downloads\Lifting\database\load_database.g"
db_backup = r"C:\Users\jeffr\Downloads\Lifting\database\load_database.g.bak"

# Rename to prevent loading
os.rename(db_loader, db_backup)

try:
    gap_commands = '''
BreakOnError := false;

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

PrintTo("C:/Users/jeffr/Downloads/Lifting/combo13_nodb.txt", "Testing without DB...\\n");

T42 := TransitiveGroup(4, 2);
T43 := TransitiveGroup(4, 3);
T21 := TransitiveGroup(2, 1);

# Combo 7
shifted7 := [T42, ShiftGroup(TransitiveGroup(4,2), 4), ShiftGroup(T21, 8)];
offs := [0, 4, 8];
P7 := Group(Concatenation(List(shifted7, GeneratorsOfGroup)));
AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_nodb.txt", "Combo 7...\\n");
r7 := FindFPFClassesByLifting(P7, shifted7, offs);
AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_nodb.txt",
    "  Result: ", Length(r7), "\\n");

# Combo 8
shifted8 := [T42, ShiftGroup(T43, 4), ShiftGroup(T21, 8)];
P8 := Group(Concatenation(List(shifted8, GeneratorsOfGroup)));
AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_nodb.txt", "Combo 8...\\n");
r8 := FindFPFClassesByLifting(P8, shifted8, offs);
AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_nodb.txt",
    "  Result: ", Length(r8), "\\n");

GASMAN("collect");

# Combo 13
shifted13 := [T43, ShiftGroup(TransitiveGroup(4,3), 4), ShiftGroup(T21, 8)];
P13 := Group(Concatenation(List(shifted13, GeneratorsOfGroup)));
AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_nodb.txt",
    "Combo 13, |P|=", Size(P13), "...\\n");
r13 := FindFPFClassesByLifting(P13, shifted13, offs);
AppendTo("C:/Users/jeffr/Downloads/Lifting/combo13_nodb.txt",
    "  Result: ", Length(r13), "\\n\\nDone!\\n");

QUIT;
'''

    with open(r"C:\Users\jeffr\Downloads\Lifting\temp_combo13_nodb.g", "w") as f:
        f.write(gap_commands)

    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_combo13_nodb.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    trace_file = r"C:\Users\jeffr\Downloads\Lifting\combo13_nodb.txt"
    if os.path.exists(trace_file):
        os.remove(trace_file)

    print("Testing combo 13 WITHOUT database...")
    start = time.time()

    with open(r"C:\Users\jeffr\Downloads\Lifting\combo13_nodb_stdout.txt", "w") as stdout_f:
        process = subprocess.Popen(
            [bash_exe, "--login", "-c",
             f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 2G "{script_path}"'],
            stdout=stdout_f,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=gap_runtime
        )
        process.wait(timeout=300)

    elapsed = time.time() - start
    print(f"Time: {elapsed:.1f}s, Exit: {process.returncode}")

    if os.path.exists(trace_file):
        print("\nTrace:")
        with open(trace_file, 'r') as f:
            print(f.read())

finally:
    # Restore the database loader
    os.rename(db_backup, db_loader)
    print("\nDatabase loader restored.")
