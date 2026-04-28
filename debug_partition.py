import subprocess
import os

# Debug a specific partition to find the issue

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

# Debug [4,4] partition specifically
gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/debug_partition_output.txt");
Print("Debugging specific partitions for S8\\n");
Print("==========================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Test: Count directly using ConjugacyClassesSubgroups for S4 x S4
# to verify [4,4] partition count

Print("\\n=== Direct verification of partition [4,4] ===\\n");

S4 := SymmetricGroup(4);
shifted2 := ShiftGroup(S4, 4);

P44 := DirectProduct(S4, S4);
Print("P = S4 x S4, |P| = ", Size(P44), "\\n");

# Get all conjugacy classes
all_classes := ConjugacyClassesSubgroups(P44);
Print("Total conjugacy classes: ", Length(all_classes), "\\n");

# Check which are FPF subdirects
shifted := [S4, shifted2];
offs := [0, 4];

fpf_count := 0;
for cls in all_classes do
    if IsFPFSubdirect(Representative(cls), shifted, offs) then
        fpf_count := fpf_count + 1;
    fi;
od;
Print("Direct FPF subdirect count for [4,4]: ", fpf_count, "\\n");

# Now test with lifting
Print("\\nTesting [4,4] with lifting algorithm:\\n");
P := Group(Concatenation(GeneratorsOfGroup(S4), GeneratorsOfGroup(shifted2)));
lifting_result := FindFPFClassesByLifting(P, shifted, offs);
Print("Lifting FPF count: ", Length(lifting_result), "\\n");

if fpf_count <> Length(lifting_result) then
    Print("MISMATCH! Direct=", fpf_count, " Lifting=", Length(lifting_result), "\\n");
else
    Print("OK - counts match\\n");
fi;

LogTo();
QUIT;
'''

# Write commands to temp file
with open(r"C:\Users\jeffr\Downloads\Lifting\temp_debug_partition.g", "w") as f:
    f.write(gap_commands)

script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_debug_partition.g"

print("Debugging specific partition...")
print()

try:
    process = subprocess.Popen(
        [bash_exe, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=gap_runtime
    )

    stdout, stderr = process.communicate(timeout=600)  # 10 min timeout

    if stdout:
        print("Output:")
        print(stdout)
    if stderr:
        print("Errors:")
        print(stderr)

    # Read output file
    output_file = r"C:\Users\jeffr\Downloads\Lifting\debug_partition_output.txt"
    if os.path.exists(output_file):
        print("\nOutput from log file:")
        print("=" * 50)
        with open(output_file, 'r') as f:
            print(f.read())

except subprocess.TimeoutExpired:
    print("Process timed out after 10 minutes")
    process.kill()
except Exception as e:
    print(f"Error: {e}")
