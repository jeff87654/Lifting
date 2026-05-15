"""Predictor subprocess wrappers and named task-kind constants.

Three classes of subprocess invocations live here:

  - `run_bootstrap_batch` — inline GAP template that handles single-block
    combos (len(combo) == 1) by writing GeneratorsOfGroup(TransitiveGroup(d,t))
    directly.  Cheap; batched multiple combos per GAP session.
  - `run_predictor` — single-combo invocation of one of the predictor scripts
    (predict_2factor_topt.py / predict_full_general_wreath.py / the fast-path
    runners).  Parses the predictor's JSON stdout.
  - `_run_subprocess_task` — the worker function submitted to
    ProcessPoolExecutor.  Wraps `subprocess.run` plus JSON parse plus
    error-shape normalisation.  Distinguishes batch-shaped (results array)
    vs single-shaped (result object) replies by inspecting `kind`.

Task-kind constants exist so callers can grep for the producer of a kind
without chasing string literals.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from runner.constants import GAP_BASH, GAP_HOME, ROOT, to_cyg


# --- Task-kind tags --------------------------------------------------------
#
# The string values are the wire format: they appear in result dicts written
# to JSON summary files, are used as dict keys in the per-kind aggregation in
# the scheduler, and must not change.  These constants exist only to make
# greppable the call sites that produce each kind.

TASK_KIND_BOOTSTRAP = "bootstrap"
TASK_KIND_BATCH = "batch"
TASK_KIND_SUPER_BATCH = "super_batch"
TASK_KIND_C2 = "c2"
TASK_KIND_C2_FACTOR_BATCH = "c2_factor_batch"
TASK_KIND_WREATH = "wreath"
TASK_KIND_WREATH_VIA_2F = "wreath_via_2f"
TASK_KIND_BD8 = "bd8"
TASK_KIND_ELEMAB = "elemab"

# Kinds whose subprocess returns a results[] array of per-job result objects
# (vs single-shaped kinds that return one result object).
BATCH_KINDS = frozenset({
    TASK_KIND_BATCH,
    TASK_KIND_SUPER_BATCH,
    TASK_KIND_C2_FACTOR_BATCH,
})


# --- Bootstrap (single-block combos) --------------------------------------

BOOTSTRAP_TEMPLATE = r"""
LogTo("__LOG__");
batch := __BATCH__;
for entry in batch do
    d := entry[1];
    t := entry[2];
    output := entry[3];
    T := TransitiveGroup(d, t);
    gens := GeneratorsOfGroup(T);
    PrintTo(output, "# combo: [ [ ", d, ", ", t, " ] ]\n");
    AppendTo(output, "# candidates: 1\n# deduped: 1\n# elapsed_ms: 0\n");
    if Length(gens) > 0 then
        s := JoinStringsWithSeparator(List(gens, String), ",");
    else
        s := "";
    fi;
    AppendTo(output, "[", s, "]\n");
    Print("BOOTSTRAP_OK d=", d, " t=", t, " path=", output, "\n");
od;
LogTo();
QUIT;
"""


def run_bootstrap_batch(entries, tmp_dir):
    """Bootstrap multiple single-block combos in one GAP session.
    `entries` = list of (d, t, output_path)."""
    if not entries:
        return
    tmp_dir.mkdir(parents=True, exist_ok=True)
    log = tmp_dir / "bootstrap.log"
    if log.exists(): log.unlink()
    batch_str = "[" + ",".join(
        f'[{d},{t},"{to_cyg(p)}"]' for d, t, p in entries) + "]"
    run_g = tmp_dir / "bootstrap_run.g"
    run_g.write_text(
        BOOTSTRAP_TEMPLATE
        .replace("__LOG__", to_cyg(log))
        .replace("__BATCH__", batch_str),
        encoding="utf-8"
    )
    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)


# --- Run a non-bootstrap combo --------------------------------------------

def run_predictor(predictor_script, combo_str, output_path, extra_args=None,
                  timeout=3600):
    """Invoke a predictor as a subprocess and return its result dict."""
    args = [sys.executable, str(ROOT / predictor_script),
            "--combo", combo_str,
            "--output-path", str(output_path)]
    if extra_args:
        args.extend(extra_args)
    args.extend(["--timeout", str(timeout)])
    t0 = time.time()
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                               timeout=timeout + 60)
    except subprocess.TimeoutExpired:
        return {"error": "wrapper timeout", "elapsed_s": time.time() - t0}
    if proc.returncode != 0:
        return {"error": f"predictor rc={proc.returncode}",
                "stderr": proc.stderr[-500:],
                "stdout": proc.stdout[-500:]}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": "json parse",
                "stdout": proc.stdout[-500:]}


# --- Subprocess task runner (called by ProcessPoolExecutor) ---------------

def _run_subprocess_task(kind, key, cmd, timeout):
    """Run one task as a subprocess.  Returns dict with kind/key plus
    parsed JSON output (if available).  timeout=None means run indefinitely."""
    t0 = time.time()
    try:
        if timeout is None:
            proc = subprocess.run(cmd, capture_output=True, text=True)
        else:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"kind": kind, "key": key, "error": "timeout",
                "elapsed_s": time.time() - t0}
    if proc.returncode != 0:
        return {"kind": kind, "key": key,
                "error": f"rc={proc.returncode}",
                "stderr": proc.stderr[-500:],
                "stdout": proc.stdout[-500:],
                "elapsed_s": time.time() - t0}
    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"kind": kind, "key": key, "error": "json parse",
                "stdout": proc.stdout[-500:], "stderr": proc.stderr[-500:],
                "elapsed_s": time.time() - t0}
    if kind in BATCH_KINDS:
        return {"kind": kind, "key": key, "results": parsed,
                "elapsed_s": time.time() - t0}
    return {"kind": kind, "key": key, "elapsed_s": time.time() - t0,
            **(parsed if isinstance(parsed, dict) else {"raw": parsed})}
