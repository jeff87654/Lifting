"""Inspect the specific non-perm group in FPF_SUBDIRECT_CACHE for [2,2]."""
import subprocess, os
from pathlib import Path

LIFTING = Path(r"C:\Users\jeffr\Downloads\Lifting")
LOG = LIFTING / "debug_inspect.log"

gap_commands = f'''
LogTo("{LOG.as_posix()}");
USE_TF_DATABASE := false;;
Read("{(LIFTING / "lifting_method_fast_v2.g").as_posix()}");

# Run only S_4 (which involves [2,2])
result := CountAllConjugacyClassesFast(4);
Print("S_4 = ", result, " expected=11\\n");

key := "[ [ 2, 1 ], [ 2, 1 ] ]";
Print("\\n=== Inspecting FPF_SUBDIRECT_CACHE.(", key, ") ===\\n");
if IsBound(FPF_SUBDIRECT_CACHE.(key)) then
    entries := FPF_SUBDIRECT_CACHE.(key);
    Print("Entry count: ", Length(entries), "\\n");
    for i in [1..Length(entries)] do
        G := entries[i];
        Print("\\n  --- Entry ", i, " ---\\n");
        Print("  IsPermGroup: ", IsPermGroup(G), "\\n");
        Print("  IsGroup: ", IsGroup(G), "\\n");
        Print("  IsList: ", IsList(G), "\\n");
        Print("  IsRecord: ", IsRecord(G), "\\n");
        if IsGroup(G) then
            Print("  Size: ", Size(G), "\\n");
            Print("  IsAbelian: ", IsAbelian(G), "\\n");
            Print("  IsMatrixGroup: ", IsMatrixGroup(G), "\\n");
        fi;
        Print("  String: ", String(G), "\\n");
    od;
else
    Print("Key not bound\\n");
fi;

LogTo();
QUIT;
'''

TMP = LIFTING / "temp_inspect.g"
TMP.write_text(gap_commands)
if LOG.exists():
    LOG.unlink()

env = os.environ.copy()
env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
env['CYGWIN'] = 'nodosfilewarning'

proc = subprocess.Popen(
    [r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe", "--login", "-c",
     'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && '
     './gap.exe -q -o 0 "/cygdrive/c/Users/jeffr/Downloads/Lifting/temp_inspect.g"'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    cwd=r"C:\Program Files\GAP-4.15.1\runtime")
stdout, stderr = proc.communicate(timeout=300)
print(stdout[-3000:])
