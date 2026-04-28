import subprocess
import os

gap_commands = '''
LogTo("C:/Users/jeffr/Downloads/Lifting/test_module_failure_output.txt");
Print("Module Construction Failure Debug\\n");
Print("===================================\\n\\n");

Read("C:/Users/jeffr/Downloads/Lifting/cohomology.g");
Read("C:/Users/jeffr/Downloads/Lifting/modules.g");
Read("C:/Users/jeffr/Downloads/Lifting/h1_action.g");

# Simulate what happens during lifting for S8 partition [8]

Print("Test: S8 lifting - partition [8]\\n");
Print("---------------------------------\\n\\n");

S8 := SymmetricGroup(8);
Print("S8 = ", S8, "\\n");

# Get chief series
cs := ChiefSeries(S8);
Print("Chief series of S8: ", List(cs, Size), "\\n");

for i in [1..Length(cs)-1] do
    M := cs[i];
    N := cs[i+1];
    Print("\\nLayer ", i, ": M = ", Size(M), ", N = ", Size(N), "\\n");

    if Size(M) > Size(N) then
        hom := NaturalHomomorphismByNormalSubgroup(S8, N);
        Q := ImagesSource(hom);
        M_bar := Image(hom, M);

        Print("  Q = S8/N, |Q| = ", Size(Q), "\\n");
        Print("  M_bar = M/N, |M_bar| = ", Size(M_bar), "\\n");
        Print("  IsElementaryAbelian(M_bar): ", IsElementaryAbelian(M_bar), "\\n");

        if IsElementaryAbelian(M_bar) and Size(M_bar) > 1 then
            Print("  Trying ChiefFactorAsModule...\\n");

            # Debug: first check ComplementClassesRepresentatives
            Print("    ComplementClassesRepresentatives(Q, M_bar)...\\n");
            comps := ComplementClassesRepresentatives(Q, M_bar);
            Print("    Found ", Length(comps), " complement classes\\n");

            if Length(comps) > 0 then
                Print("    First complement: ", Size(comps[1]), "\\n");
                Print("    Intersection with M_bar: ", Size(Intersection(comps[1], M_bar)), "\\n");
            fi;

            module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
            if module = fail then
                Print("  => ChiefFactorAsModule FAILED!\\n");
            else
                Print("  => ChiefFactorAsModule succeeded, dim = ", module.dimension, "\\n");
            fi;
        fi;
    fi;
od;

# Now test actual lifting scenario - S/L quotients
Print("\\n\\n======================================\\n");
Print("Testing actual lifting scenarios\\n");
Print("======================================\\n\\n");

# Simulate what happens during lifting:
# We have S as a subgroup of direct product, and we're lifting through chief series

# Take a subdirect product of S3 x S3 as an example
S3 := SymmetricGroup(3);
P := DirectProduct(S3, S3);
emb1 := Embedding(P, 1);
emb2 := Embedding(P, 2);

# Diagonal subgroup (FPF subdirect product)
diag := Group(List(GeneratorsOfGroup(S3), g -> Image(emb1, g) * Image(emb2, g)));
Print("Diagonal S3 in S3 x S3: ", Size(diag), "\\n");

# Get chief series of diagonal
cs := ChiefSeries(diag);
Print("Chief series: ", List(cs, Size), "\\n");

for i in [1..Length(cs)-1] do
    M := cs[i];
    N := cs[i+1];
    Print("\\nLayer ", i, ": |M| = ", Size(M), ", |N| = ", Size(N), "\\n");

    if Size(M) > Size(N) then
        hom := NaturalHomomorphismByNormalSubgroup(diag, N);
        Q := ImagesSource(hom);
        M_bar := Image(hom, M);

        Print("  |Q| = ", Size(Q), ", |M_bar| = ", Size(M_bar), "\\n");
        Print("  IsElementaryAbelian(M_bar): ", IsElementaryAbelian(M_bar), "\\n");

        comps := ComplementClassesRepresentatives(Q, M_bar);
        Print("  Complement classes: ", Length(comps), "\\n");

        if IsElementaryAbelian(M_bar) and Size(M_bar) > 1 then
            module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
            if module = fail then
                Print("  => ChiefFactorAsModule FAILED\\n");
            else
                Print("  => ChiefFactorAsModule OK, dim = ", module.dimension, "\\n");
            fi;
        fi;
    fi;
od;

# Most critical test: What happens with typical S8 subdirect products?
Print("\\n\\n======================================\\n");
Print("Testing S8 subdirect scenario (partition [4,4])\\n");
Print("======================================\\n\\n");

S4 := SymmetricGroup(4);
P := DirectProduct(S4, S4);
emb1 := Embedding(P, 1);
emb2 := Embedding(P, 2);

# Diagonal subgroup
diagS4 := Group(List(GeneratorsOfGroup(S4), g -> Image(emb1, g) * Image(emb2, g)));
Print("Diagonal S4 in S4 x S4: |diag| = ", Size(diagS4), "\\n");

cs := ChiefSeries(diagS4);
Print("Chief series: ", List(cs, Size), "\\n");

for i in [1..Length(cs)-1] do
    M := cs[i];
    N := cs[i+1];
    Print("\\nLayer ", i, ": |M| = ", Size(M), ", |N| = ", Size(N), "\\n");

    if Size(M) > Size(N) then
        hom := NaturalHomomorphismByNormalSubgroup(diagS4, N);
        Q := ImagesSource(hom);
        M_bar := Image(hom, M);

        Print("  |Q| = ", Size(Q), ", |M_bar| = ", Size(M_bar), "\\n");
        Print("  IsElementaryAbelian(M_bar): ", IsElementaryAbelian(M_bar), "\\n");

        comps := ComplementClassesRepresentatives(Q, M_bar);
        Print("  Complement classes: ", Length(comps), "\\n");

        if IsElementaryAbelian(M_bar) and Size(M_bar) > 1 then
            module := ChiefFactorAsModule(Q, M_bar, TrivialSubgroup(M_bar));
            if module = fail then
                Print("  => ChiefFactorAsModule FAILED\\n");
            else
                Print("  => ChiefFactorAsModule OK\\n");
                Print("     dim(module) = ", module.dimension, "\\n");
                Print("     |generators| = ", Length(module.generators), "\\n");
                Print("     |preimageGens| = ", Length(module.preimageGens), "\\n");
            fi;
        fi;
    fi;
od;

Print("\\n======================================\\n");
Print("Debug Test Complete\\n");
Print("======================================\\n");
LogTo();
QUIT;
'''

def main():
    print("Module Construction Failure Debug Test")
    print("=" * 50)
    print()

    with open(r"C:\Users\jeffr\Downloads\Lifting\test_module_failure_commands.g", "w") as f:
        f.write(gap_commands)

    gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
    bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
    script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/test_module_failure_commands.g"

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

        stdout, stderr = process.communicate(timeout=300)

        if stdout:
            print("Output:")
            print(stdout)

        output_file = r"C:\Users\jeffr\Downloads\Lifting\test_module_failure_output.txt"
        if os.path.exists(output_file):
            print("\n" + "=" * 50)
            print("Full output from log file:")
            print("=" * 50)
            with open(output_file, 'r') as f:
                print(f.read())

    except subprocess.TimeoutExpired:
        print("Process timed out")
        process.kill()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
