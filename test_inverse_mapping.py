import subprocess
import os

gap_commands = '''
Read("C:/Users/jeffr/Downloads/Lifting/cohomology.g");
Read("C:/Users/jeffr/Downloads/Lifting/modules.g");

# Test the InverseGeneralMapping approach on a simple case
TestInverseMapping := function()
    local S4, V4, hom, G, baseComplements, baseComplement, phi, invphi, pcgsG, gens_Q, gens_G;

    Print("=== Testing InverseGeneralMapping on S4/V4 ===\\n");

    S4 := SymmetricGroup(4);
    V4 := Group([(1,2)(3,4), (1,3)(2,4)]);

    hom := NaturalHomomorphismByNormalSubgroup(S4, V4);
    G := ImagesSource(hom);

    Print("G = ", G, "\\n");
    Print("|G| = ", Size(G), "\\n");
    Print("GeneratorsOfGroup(G) = ", GeneratorsOfGroup(G), "\\n");

    baseComplements := ComplementClassesRepresentatives(S4, V4);
    Print("Number of complement classes: ", Length(baseComplements), "\\n");

    baseComplement := baseComplements[1];
    Print("baseComplement = ", baseComplement, "\\n");
    Print("GeneratorsOfGroup(baseComplement) = ", GeneratorsOfGroup(baseComplement), "\\n");

    # Try to build isomorphism
    Print("\\n--- Building phi ---\\n");
    Print("Images of baseComplement generators in G:\\n");
    for c in GeneratorsOfGroup(baseComplement) do
        Print("  ", c, " -> ", Image(hom, c), "\\n");
    od;

    phi := GroupHomomorphismByImages(
        baseComplement, G,
        GeneratorsOfGroup(baseComplement),
        List(GeneratorsOfGroup(baseComplement), x -> Image(hom, x))
    );

    Print("phi = ", phi, "\\n");

    if phi = fail then
        Print("ERROR: phi construction failed!\\n");
        return;
    fi;

    Print("IsBijective(phi) = ", IsBijective(phi), "\\n");

    if IsBijective(phi) then
        invphi := InverseGeneralMapping(phi);
        Print("invphi = ", invphi, "\\n");

        pcgsG := Pcgs(G);
        Print("Pcgs(G) = ", List(pcgsG), "\\n");

        # Get preimages of Pcgs elements
        Print("\\n--- Preimages of Pcgs(G) elements ---\\n");
        for g in pcgsG do
            Print("  ", g, " -> ", Image(invphi, g), "\\n");
        od;
    fi;
end;

TestInverseMapping();

# Now test a case that might fail - a quotient group
Print("\\n\\n=== Testing on quotient group (S3 x S3) / N ===\\n");

S3x := Group((1,2,3), (1,2));
S3y := Group((4,5,6), (4,5));
S3xS3 := Group(Concatenation(GeneratorsOfGroup(S3x), GeneratorsOfGroup(S3y)));
Print("|S3 x S3| = ", Size(S3xS3), "\\n");

# Find an elementary abelian normal subgroup
for N in NormalSubgroups(S3xS3) do
    if Size(N) > 1 and Size(N) < Size(S3xS3) and IsElementaryAbelian(N) then
        Print("\\nTesting with N of size ", Size(N), "\\n");
        Print("N = ", N, "\\n");

        hom2 := NaturalHomomorphismByNormalSubgroup(S3xS3, N);
        G2 := ImagesSource(hom2);

        Print("G2 = ", G2, "\\n");
        Print("|G2| = ", Size(G2), "\\n");

        baseComplements2 := ComplementClassesRepresentatives(S3xS3, N);
        Print("Number of complement classes: ", Length(baseComplements2), "\\n");

        if Length(baseComplements2) > 0 then
            baseComplement2 := baseComplements2[1];
            Print("baseComplement2 generators: ", GeneratorsOfGroup(baseComplement2), "\\n");

            phi2 := GroupHomomorphismByImages(
                baseComplement2, G2,
                GeneratorsOfGroup(baseComplement2),
                List(GeneratorsOfGroup(baseComplement2), x -> Image(hom2, x))
            );

            Print("phi2 = ", phi2, "\\n");

            if phi2 <> fail then
                Print("IsBijective(phi2) = ", IsBijective(phi2), "\\n");
            fi;
        fi;

        break;
    fi;
od;

QUIT;
'''

with open(r"C:\Users\jeffr\Downloads\Lifting\temp_inverse.g", "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_inverse.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=120)
print(stdout)
if stderr:
    print("STDERR:", stderr)
