"""debug_wml_orientation.py — confirm W_ML orientation bug for distinguished
[3,3,2,2]/[2,1]_[2,1]_[3,1]_[3,2] LEFT source.

LEFT source = parallel_sn_v2/7/[3,2,2]/[2,1]_[2,1]_[3,1].g:
  L1 := <(1,2)(3,4),(5,6,7)>           (C_2 x C_3, |L1|=6)
  L2 := <(1,2),(3,4),(5,6,7)>          (V_4 x C_3, |L2|=12)

Compare two W_ML choices:
  W_DESC = S_3 x (S_2 wr S_2)    (m_left_partition=[3,2,2] descending)
  W_ASC  = (S_2 wr S_2) x S_3    (m_left_partition=[2,2,3] ascending — matches source embedding)

For each LEFT subgroup L_i:
  trad K-set N_i = Filtered(NormalSubgroups(L_i), K -> K <> L_i)
  Compute |N_W(L_i)|, orbits of N_W on N_i for each W choice.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = ROOT / "debug_wml_orientation.log"
if LOG.exists():
    LOG.unlink()

GAP_SCRIPT = f'''
LogTo("{str(LOG).replace(chr(92), "/")}");

L1 := Group([(1,2)(3,4),(5,6,7)]);
L2 := Group([(1,2),(3,4),(5,6,7)]);

# W_DESC: S_3 on 1-3, (S_2 wr S_2) on 4-7  (partition [3,2,2] descending)
W_DESC_S3 := SymmetricGroup([1..3]);
W_DESC_W2 := WreathProduct(SymmetricGroup(2), SymmetricGroup(2));
# Shift WreathProduct(S_2,S_2) to act on points 4..7
W_DESC_W2_shift := Group(List(GeneratorsOfGroup(W_DESC_W2),
                              g -> g^(MappingPermListList([1..4],[4..7]))));
W_DESC := Group(Concatenation(GeneratorsOfGroup(W_DESC_S3),
                              GeneratorsOfGroup(W_DESC_W2_shift)));

# W_ASC: (S_2 wr S_2) on 1-4, S_3 on 5-7   (partition [2,2,3] ascending)
W_ASC_W2 := WreathProduct(SymmetricGroup(2), SymmetricGroup(2));   # acts on 1-4 by default
W_ASC_S3 := Group(List(GeneratorsOfGroup(SymmetricGroup(3)),
                       g -> g^(MappingPermListList([1..3],[5..7]))));
W_ASC := Group(Concatenation(GeneratorsOfGroup(W_ASC_W2),
                              GeneratorsOfGroup(W_ASC_S3)));

ConjAction := function(K, g) return K^g; end;

ReportFor := function(name, L)
    local N_L_DESC, N_L_ASC, K_set, orbs_DESC, orbs_ASC;
    Print("\\n=== ", name, " |L|=", Size(L), " ===\\n");
    K_set := Filtered(NormalSubgroups(L), K -> K <> L);
    Print("K-count=", Length(K_set), "\\n");

    Print("L in W_DESC = ", IsSubset(W_DESC, L), "\\n");
    Print("L in W_ASC  = ", IsSubset(W_ASC, L), "\\n");

    if IsSubset(W_DESC, L) then
        N_L_DESC := Normalizer(W_DESC, L);
        Print("|N_W_DESC(L)|=", Size(N_L_DESC), "\\n");
        orbs_DESC := Orbits(N_L_DESC, K_set, ConjAction);
        Print("W_DESC orbits: ", Length(orbs_DESC), "\\n");
        for o in orbs_DESC do
            Print("  size=", Length(o), " quot=", IdGroup(L/o[1]), "\\n");
        od;
    fi;

    if IsSubset(W_ASC, L) then
        N_L_ASC := Normalizer(W_ASC, L);
        Print("|N_W_ASC(L)|=", Size(N_L_ASC), "\\n");
        orbs_ASC := Orbits(N_L_ASC, K_set, ConjAction);
        Print("W_ASC orbits: ", Length(orbs_ASC), "\\n");
        for o in orbs_ASC do
            Print("  size=", Length(o), " quot=", IdGroup(L/o[1]), "\\n");
        od;
    fi;
end;

ReportFor("L1 = <(1,2)(3,4),(5,6,7)>", L1);
ReportFor("L2 = <(1,2),(3,4),(5,6,7)>", L2);

LogTo();
QUIT;
'''

(ROOT / "debug_wml_orientation.g").write_text(GAP_SCRIPT, encoding="utf-8")
bash_exe = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
script_cyg = "/cygdrive/c/Users/jeffr/Downloads/Lifting/debug_wml_orientation.g"
env = os.environ.copy()
env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
env["CYGWIN"] = "nodosfilewarning"
proc = subprocess.run(
    [bash_exe, "--login", "-c",
     f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{script_cyg}"'],
    env=env, capture_output=True)
print(LOG.read_text(encoding="utf-8") if LOG.exists() else "(no log)")
print("---STDERR---")
print(proc.stderr.decode(errors="ignore")[:2000])
