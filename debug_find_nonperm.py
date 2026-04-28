"""Run S_n far enough to populate FPF_SUBDIRECT_CACHE, then walk it manually
and identify which entry contains a non-perm group + which code path put it there.
"""
import subprocess, os
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = LIFTING / "debug_find_nonperm.log"

gap_commands = f'''
LogTo("{LOG.as_posix()}");
USE_TF_DATABASE := false;;
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");

# Run S2-S10 to populate FPF cache
known := [1, 2, 4, 11, 19, 56, 96, 296, 554, 1593];
for n in [2..10] do
    result := CountAllConjugacyClassesFast(n);
    if result <> known[n] then
        Print("MISMATCH at S_", n, ": got ", result, " expected ", known[n], "\\n");
    fi;
od;

# Walk the FPF cache, find non-perm entries
Print("\\n=== Scanning FPF_SUBDIRECT_CACHE for non-perm groups ===\\n");
nonperm_count := 0;
total_groups := 0;
for key in RecNames(FPF_SUBDIRECT_CACHE) do
    for G in FPF_SUBDIRECT_CACHE.(key) do
        total_groups := total_groups + 1;
        if not IsPermGroup(G) then
            nonperm_count := nonperm_count + 1;
            Print("  Non-perm group at key=", key, "\\n");
            Print("    Family: ", FamilyObj(G), "\\n");
            Print("    Type: ", TypeObj(G), "\\n");
            Print("    Size: ", Size(G), "\\n");
            Print("    Generators: ", GeneratorsOfGroup(G), "\\n");
            Print("    First gen: ", GeneratorsOfGroup(G)[1], "\\n");
            Print("    First gen family: ", FamilyObj(GeneratorsOfGroup(G)[1]), "\\n");
            if nonperm_count >= 5 then
                Print("  (stopping after 5 examples)\\n");
                break;
            fi;
        fi;
    od;
    if nonperm_count >= 5 then break; fi;
od;

Print("\\nTotal groups in cache: ", total_groups, "\\n");
Print("Non-perm groups: ", nonperm_count, "\\n");

LogTo();
QUIT;
'''

TMP = LIFTING / "temp_find_nonperm.g"
TMP.write_text(gap_commands)
if LOG.exists():
    LOG.unlink()

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

proc = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_find_nonperm.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
stdout, stderr = proc.communicate(timeout=600)
print(stdout[-3000:])
