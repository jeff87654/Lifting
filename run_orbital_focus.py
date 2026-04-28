"""Focused diagnostic: check if translation vector is non-zero in orbital action."""
import subprocess
import os
import time

LIFTING_DIR = r"C:\Users\jeffr\Downloads\Lifting"
log_file = "C:/Users/jeffr/Downloads/Lifting/orbital_focus.log"

gap_commands = f'''
LogTo("{log_file}");

Read("C:/Users/jeffr/Downloads/Lifting/lifting_method_fast_v2.g");
Read("C:/Users/jeffr/Downloads/Lifting/database/lift_cache.g");

# Patch ComputeOuterActionOnH1 to compute and report translation vector
_ORIG_ComputeOuterActionOnH1 := ComputeOuterActionOnH1;

_NONZERO_TRANSLATIONS := 0;

ComputeOuterActionOnH1 := function(cohomRecord, module, n, S, L, homSL, P)
    local mat, dimH1, field, ngens, dim, Q, M_bar, quotientHom, G, pcgsM,
          nInv, actionMatM, i, j, m, m_S, m_S_conj, m_Q_conj, exps,
          gi_Q, gi_S, gi_S_conj, gi_Q_conj, g_conj,
          C_0, phi_C0, invphi_C0, s_g_conj, mu_j_elem, mu_j_vec,
          corrCocycle, translationVec;

    # Call original to get the matrix
    mat := _ORIG_ComputeOuterActionOnH1(cohomRecord, module, n, S, L, homSL, P);

    dimH1 := cohomRecord.H1Dimension;
    if dimH1 = 0 or mat = [] or mat = fail then
        return mat;
    fi;

    field := module.field;
    ngens := Length(module.generators);
    dim := module.dimension;
    Q := module.ambientGroup;
    M_bar := module.moduleGroup;
    quotientHom := module.quotientHom;
    G := ImagesSource(quotientHom);
    pcgsM := module.pcgsM;

    nInv := n^(-1);

    # Recompute actionMatM (same as in original)
    actionMatM := NullMat(dim, dim, field);
    for i in [1..dim] do
        m := pcgsM[i];
        m_S := PreImagesRepresentative(homSL, m);
        m_S_conj := m_S^n;
        m_Q_conj := Image(homSL, m_S_conj);
        exps := ExponentsOfPcElement(pcgsM, m_Q_conj);
        for j in [1..dim] do
            actionMatM[i][j] := exps[j] * One(field);
        od;
    od;

    # Build base complement C_0 and section inverse
    C_0 := Group(module.preimageGens);
    phi_C0 := GroupHomomorphismByImages(C_0, G, module.preimageGens, module.generators);
    if phi_C0 = fail then
        return mat;
    fi;
    invphi_C0 := InverseGeneralMapping(phi_C0);

    # Compute correction cocycle (the translation)
    corrCocycle := ListWithIdenticalEntries(ngens * dim, Zero(field));
    for j in [1..ngens] do
        gi_Q := module.preimageGens[j];
        gi_S := PreImagesRepresentative(homSL, gi_Q);
        gi_S_conj := gi_S^nInv;
        gi_Q_conj := Image(homSL, gi_S_conj);
        g_conj := Image(quotientHom, gi_Q_conj);

        # Section value at g_conj
        s_g_conj := Image(invphi_C0, g_conj);

        # mu_j = M_bar component of gi_Q_conj
        mu_j_elem := s_g_conj^(-1) * gi_Q_conj;
        mu_j_vec := List(ExponentsOfPcElement(pcgsM, mu_j_elem), x -> x * One(field));

        # Correction: -mu_j * actionMatM
        corrCocycle{{[(j-1)*dim + 1 .. j*dim]}} := -mu_j_vec * actionMatM;
    od;

    # Project correction to H^1
    translationVec := ProjectToH1Coordinates(cohomRecord, corrCocycle);

    if not ForAll(translationVec, x -> x = Zero(field)) then
        _NONZERO_TRANSLATIONS := _NONZERO_TRANSLATIONS + 1;
        Print("  *** NON-ZERO TRANSLATION #", _NONZERO_TRANSLATIONS, " ***\\n");
        Print("    H^1 dim=", dimH1, " p=", module.p, " |Q|=", Size(Q),
              " |M_bar|=", Size(M_bar), " |G|=", Size(G), "\\n");
        Print("    Action matrix: ", mat, "\\n");
        Print("    Translation: ", translationVec, "\\n");
    fi;

    return mat;
end;

# Run [6,6,3]
USE_H1_ORBITAL := true;
Print("Running [6,6,3] with translation diagnostic...\\n");
result := FindFPFClassesForPartition(15, [6,6,3]);
Print("Result: ", Length(result), " classes\\n");
Print("Non-zero translations found: ", _NONZERO_TRANSLATIONS, "\\n");
LogTo();
QUIT;
'''

temp_gap = os.path.join(LIFTING_DIR, "temp_orbital_focus.g")
with open(temp_gap, "w") as f:
    f.write(gap_commands)

gap_runtime = r"C:\Program Files\GAP-4.15.1\runtime"
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_path = "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_orbital_focus.g"

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

print(f"Starting focused diagnostic at {time.strftime('%H:%M:%S')}")
process = subprocess.Popen(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q "{script_path}"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=gap_runtime
)
stdout, stderr = process.communicate(timeout=7200)
print(f"Finished at {time.strftime('%H:%M:%S')}")

if stderr.strip():
    err_lines = [l for l in stderr.split('\n') if 'Error' in l or 'error' in l.lower()]
    if err_lines:
        print(f"ERRORS:\n" + "\n".join(err_lines[:10]))

log_path = log_file.replace("/", os.sep)
if os.path.exists(log_path):
    with open(log_path, "r") as f:
        log = f.read()
    lines = log.split('\n')
    for line in lines:
        if 'TRANSLATION' in line or 'translation' in line.lower() or 'Non-zero' in line:
            print(line)
    print("---")
    for line in lines[-20:]:
        print(line)
else:
    print("No log file found")
    print("STDOUT:", stdout[-2000:])
