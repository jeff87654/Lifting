"""inline_prodcopy.py — surgery on bench_prodcopy.g to inline ProcessPairBatch
into the H1xH2 loop. Tests whether function-wrapper is the slowdown source.
"""
import re
from pathlib import Path

src = Path("bench_prodcopy.g").read_text()

# Find ProcessPairBatch definition: starts at "ProcessPairBatch := function(...)"
# and ends at the matching "end;" — followed by the next blank line and TOTAL_ORB :=
m = re.search(r"^    ProcessPairBatch := function\(H1data, H2data, H1, H2\)(.*?)^    end;\n",
              src, re.MULTILINE | re.DOTALL)
if not m:
    raise RuntimeError("ProcessPairBatch not found")
func_body_full = m.group(1)
func_def_full = m.group(0)

# The function body: extract everything between the `local` line and `return rec(...)`
mb = re.search(r"local [^;]+;\n(.*?)        return rec\(orbits := total, swap_fixed := swap_fixed\);",
               func_body_full, re.DOTALL)
if not mb:
    raise RuntimeError("function body not parseable")
body = mb.group(1)
# Re-indent to match outer loop level (8 spaces inside `for j` loop -> still 8 spaces is fine)
# Find local declarations to lift out
locals_match = re.search(r"local (.+?);", func_body_full, re.DOTALL)
locals_decl = locals_match.group(1).replace("\n              ", "")

# Replace the function call site:
#   res_pair := ProcessPairBatch(H1data_j, H2data_j, H1_j, H2_j);
# with:
#   # inlined ProcessPairBatch body (assigns to total, swap_fixed)
#   { aliases: H1data := H1data_j; H2data := H2data_j; H1 := H1_j; H2 := H2_j; }
#   <body>
#   res_pair := rec(orbits := total, swap_fixed := swap_fixed);

inline_block = (
    "            # >>> INLINED ProcessPairBatch (was a function) <<<\n"
    "            H1data := H1data_j; H2data := H2data_j;\n"
    "            H1 := H1_j; H2 := H2_j;\n"
    "            total := 0; swap_fixed := 0;\n"
    + body +
    "            res_pair := rec(orbits := total, swap_fixed := swap_fixed);\n"
    "            # >>> END INLINED <<<\n"
)

# Drop the function definition entirely
new = src.replace(func_def_full, "    # ProcessPairBatch was inlined below; def removed.\n")

# Replace the function call
call_line = "            res_pair := ProcessPairBatch(H1data_j, H2data_j, H1_j, H2_j);\n"
if call_line not in new:
    raise RuntimeError("call site not found")
new = new.replace(call_line, inline_block)

# Inject `local` declarations near top of JOB loop body (after `JOB := JOBS[job_idx];`)
# so that the inlined body's variables are scoped properly.
# Find the for job_idx loop start and inject locals.
job_start = re.search(r"for job_idx in \[1\.\.Length\(JOBS\)\] do\n    JOB := JOBS\[job_idx\];\n",
                       new)
if not job_start:
    raise RuntimeError("job loop start not found")
inject = (
    "    JOB := JOBS[job_idx];\n"
    "    # Locals previously inside ProcessPairBatch — now in JOB loop scope:\n"
    "    # (declared globally for inlined body; GAP will infer types.)\n"
)
new = new.replace("    JOB := JOBS[job_idx];\n", inject, 1)

# Also need: H1data, H2data, H1, H2, total, swap_fixed, h1orb, h2idxs, h2idx, h2orb,
# key, isoTH, isos, n, gensQ, KeyOf, idx, seen, n_orb, queue, j, phi, alpha, beta,
# neighbor, nkey, k, fp, orbit_id, i, swap_phi, swap_key, swap_iso_idx,
# swap_orbit_id, h1_orb_idx, orbit_reps_phi, h_0, t_0, swap_orb_id_arr.
# In GAP, these will be implicit globals when no local declaration. That's fine for
# this test — single-threaded, no clash.

# Redirect log/output to a new sandbox
out_dir = Path("bench_prodcopy_inlined_tmp")
out_dir.mkdir(exist_ok=True)
new = new.replace("/cygdrive/c/Users/jeffr/Downloads/Lifting/bench_prodcopy_tmp/prodcopy.log",
                  "/cygdrive/c/Users/jeffr/Downloads/Lifting/bench_prodcopy_inlined_tmp/prodcopy.log")
new = new.replace("/cygdrive/c/Users/jeffr/Downloads/Lifting/bench_prodcopy_tmp/result.g",
                  "/cygdrive/c/Users/jeffr/Downloads/Lifting/bench_prodcopy_inlined_tmp/result.g")

(out_dir / "run.g").write_text(new)
print(f"wrote {out_dir/'run.g'} ({len(new)} chars)")
print(f"diff lines vs original:")
import difflib
diff = list(difflib.unified_diff(src.splitlines(), new.splitlines(), n=1, lineterm=""))
for line in diff[:40]: print(line)
