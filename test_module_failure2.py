import subprocess
import os

gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_module_failure2_output.txt");
Print("Module Construction Failure Debug - Realistic Scenario\\n");
Print("=======================================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");

# Patch GetH1OrbitRepresentatives to add more debugging
_Original_GetH1OrbitRepresentatives := GetH1OrbitRepresentatives;

GetH1OrbitRepresentatives := function(Q, M_bar, ambient)
    local module, result;

    # Create module
    module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));

    if module = fail then
        Print("# DEBUG: ChiefFactorAsModule failed for:\\n");
        Print("#   |Q| = ", Size(Q), "\\n");
        Print("#   |M_bar| = ", Size(M_bar), "\\n");
        Print("#   IsElementaryAbelian(M_bar) = ", IsElementaryAbelian(M_bar), "\\n");

        # Check if complements exist at all
        Print("#   Checking ComplementClassesRepresentatives...\\n");
        result := ComplementClassesRepresentatives(Q, M_bar);
        Print("#   Found ", Length(result), " complement classes\\n");

        if Length(result) = 0 then
            Print("#   => NON-SPLIT EXTENSION - no complements exist\\n");
        else
            Print("#   => Complements exist but module construction failed!\\n");
        fi;

        return ComplementClassesRepresentatives(Q, M_bar);
    fi;

    return _Original_GetH1OrbitRepresentatives(Q, M_bar, ambient);
end;

# Temporarily reduce info output
SetInfoLevel(InfoWarning, 0);

Print("Running S8 enumeration with debug...\\n\\n");

result := CountAllConjugacyClassesFast(8);

Print("\\n\\nS8 Result: ", result, " (expected: 296)\\n");
if result = 296 then
    Print("Status: PASS\\n");
else
    Print("Status: FAIL\\n");
fi;

Print("\\n======================================\\n");
Print("Debug Test Complete\\n");
Print("======================================\\n");
LogTo();
QUIT;
'''

def main():
    print("Module Construction Debug - Realistic Scenario")
    print("=" * 50)
    print()

    with open(r"C:\Users\jeffr\Downloads\Lifting\test_module_failure2_commands.g", "w") as f:
        f.write(gap_commands)

    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_module_failure2_commands.g"

    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'

    try:
        process = subprocess.Popen(
            [bash_exe, "--login", "-c", f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=gap_runtime
        )

        stdout, stderr = process.communicate(timeout=600)

        if stdout:
            print(stdout)

        output_file = r"C:\Users\jeffr\Downloads\Lifting\test_module_failure2_output.txt"
        if os.path.exists(output_file):
            print("\n" + "=" * 50)
            print("From log file (showing DEBUG lines):")
            print("=" * 50)
            with open(output_file, 'r') as f:
                for line in f:
                    if 'DEBUG' in line or 'NON-SPLIT' in line or 'Result' in line or 'Status' in line:
                        print(line.rstrip())

    except subprocess.TimeoutExpired:
        print("Process timed out")
        process.kill()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
