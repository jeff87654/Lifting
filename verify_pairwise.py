#!/usr/bin/env python3
"""
verify_pairwise.py — load S18 actual groups for a specific combo, check
pairwise non-conjugacy under S_18 via RepresentativeAction.  If any pair
is S_18-conjugate, S18 dedup overcounted; otherwise the predictor undercounted.
"""
import subprocess, os, sys, re, time
from pathlib import Path

ROOT = Path(r"C:\Users\jeffr\Downloads\Lifting")
S18_DIR = ROOT / "parallel_s18"

GAP_BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_HOME = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"


def to_cyg(p) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/cygdrive/{s[0].lower()}{s[2:]}"
    return s


def parse_combo_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = text.replace("\\\n", "").replace("\\\r\n", "")
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    text = "\n".join(lines)
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1; continue
        if text[i] != "[":
            i += 1; continue
        depth = 0
        j = i
        while j < n:
            ch = text[j]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0: break
            j += 1
        if j >= n: break
        out.append(text[i:j+1])
        i = j + 1
    return out


GAP_SCRIPT = r'''
LogTo("__LOG__");
Read("__SUBS__");

S18 := SymmetricGroup(18);
n := Length(SUBGROUPS);
Print("Loaded ", n, " subgroups\n");

# Compute order + abelian invariants as cheap discriminators
for i in [1..n] do
    Print("G", i, ": |G|=", Size(SUBGROUPS[i]),
          " AbelInv=", AbelianInvariants(SUBGROUPS[i]),
          " IdAbel=", AbelianInvariants(SUBGROUPS[i]),
          "\n");
od;

# Pairwise RepresentativeAction in S_18
Print("\nPairwise RepresentativeAction checks (S_18):\n");
n_conj := 0;
n_nonconj := 0;
for i in [1..n-1] do
    for j in [i+1..n] do
        # Quick filter: same order
        if Size(SUBGROUPS[i]) <> Size(SUBGROUPS[j]) then
            Print("  ", i, "~", j, ": diff order, skip\n");
            n_nonconj := n_nonconj + 1;
            continue;
        fi;
        t0 := Runtime();
        rep := RepresentativeAction(S18, SUBGROUPS[i], SUBGROUPS[j]);
        elapsed := Runtime() - t0;
        if rep <> fail then
            Print("  ", i, "~", j, ": CONJUGATE (", elapsed, "ms)\n");
            n_conj := n_conj + 1;
        else
            Print("  ", i, "~", j, ": non-conjugate (", elapsed, "ms)\n");
            n_nonconj := n_nonconj + 1;
        fi;
    od;
od;

Print("\nSUMMARY: ", n_conj, " conjugate pairs, ", n_nonconj, " non-conjugate pairs\n");
Print("If n_conj > 0: S18 overcounted (some claimed-distinct classes are conjugate)\n");
Print("If n_conj = 0: S18 is correct, predictor undercounted\n");
LogTo();
QUIT;
'''


def main():
    if len(sys.argv) < 3:
        print("usage: verify_pairwise.py <partition> <combo_str>")
        print('  e.g. verify_pairwise.py "[6,4,4,4]" "[4,2]_[4,4]_[4,4]_[6,16]"')
        sys.exit(1)
    partition = sys.argv[1]
    combo = sys.argv[2]
    src = S18_DIR / partition / f"{combo}.g"
    if not src.exists():
        print(f"missing: {src}")
        sys.exit(1)

    work = ROOT / "predict_species_tmp" / "_verify" / partition.strip("[]").replace(",", "_") / combo.replace("[", "").replace("]", "").replace(",", "_")
    work.mkdir(parents=True, exist_ok=True)

    subs = parse_combo_file(src)
    subs_g = work / "subs.g"
    with open(subs_g, "w") as f:
        f.write("# Subgroups for verification\nSUBGROUPS := [\n")
        for i, s in enumerate(subs):
            sep = "," if i < len(subs) - 1 else ""
            f.write(f"  Group({s}){sep}\n")
        f.write("];\n")

    log = work / "verify.log"
    if log.exists(): log.unlink()
    run_g = work / "run.g"
    run_g.write_text(GAP_SCRIPT.replace("__LOG__", to_cyg(log)).replace("__SUBS__", to_cyg(subs_g)))

    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"

    print(f"Running pairwise verification for {partition} {combo} ({len(subs)} groups)...")
    t0 = time.time()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=3600)
    elapsed = time.time() - t0
    print(f"Done in {elapsed:.1f}s")

    if log.exists():
        print(log.read_text())


if __name__ == "__main__":
    main()
