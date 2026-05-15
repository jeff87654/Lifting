"""Persistent state managed by the runner: h_to_qs catalog + transitive-group counts.

`merge_h_to_qs_fragments` consolidates per-worker fragment files into the
master catalog at the start of each `n` and after each `n` finishes.  Workers
append fragments under `<h_cache>/_meta_q_catalog/fragments/`; consumed
fragments move to `.consumed/` so a partial crash doesn't lose data.

`get_num_transitive_groups` caches `NrTransitiveGroups(d)` for `d = 1..n_max`
in `<work_dir>/_num_transitive.json` so subsequent runs don't pay the GAP
startup just to ask the same questions.
"""
from __future__ import annotations
import json
import os
import re
import subprocess
from pathlib import Path

from runner.constants import GAP_BASH, GAP_HOME, to_cyg


def merge_h_to_qs_fragments(h_cache_dir):
    """Consolidate per-session h_to_qs fragments into the master file.

    Each fragment is a GAP file written by a worker session containing
    ``META_H_TO_QS_NEW := [[h_id_str, qid_list], ...]`` plus a
    ``META_H_TO_QS_NEW_SAVED_OK := true;`` sentinel.  This function
    parses all such files, merges with the existing master, dedups by
    h_id_str (latest entry wins), and atomically writes the master.
    Successfully merged fragments are moved to ``fragments/.consumed/``.
    """
    meta_dir = Path(h_cache_dir) / "_meta_q_catalog"
    if not meta_dir.exists():
        return  # catalog not seeded -- nothing to do
    master = meta_dir / "h_to_qs.g"
    frag_dir = meta_dir / "fragments"
    consumed_dir = frag_dir / ".consumed"
    if not frag_dir.exists():
        return
    fragments = [p for p in frag_dir.glob("*.g") if p.is_file()]
    if not fragments:
        return

    # Parse a GAP list-of-pairs literal: [["[ ... ]", [[..]..]], ...]
    # by stripping whitespace then ast.literal_eval (single→double quote
    # rewriting unnecessary; GAP uses double quotes for strings).
    import ast, re as _re

    def _parse_entries(path, var_re):
        text = path.read_text(encoding="utf-8", errors="ignore")
        m = var_re.search(text)
        if not m:
            return []
        raw = m.group(1)
        # Compress whitespace inside list literal so literal_eval is fast.
        compact = _re.sub(r"\s+", " ", raw)
        try:
            return ast.literal_eval(compact)
        except (ValueError, SyntaxError):
            return []

    master_re = _re.compile(r"META_H_TO_QS\s*:=\s*(\[.*?\])\s*;", _re.DOTALL)
    new_re = _re.compile(r"META_H_TO_QS_NEW\s*:=\s*(\[.*?\])\s*;", _re.DOTALL)

    merged = {}
    if master.exists():
        for entry in _parse_entries(master, master_re):
            if isinstance(entry, list) and len(entry) == 2:
                merged[entry[0]] = entry[1]

    n_frags = 0
    n_added = 0
    for frag in fragments:
        for entry in _parse_entries(frag, new_re):
            if isinstance(entry, list) and len(entry) == 2:
                if entry[0] not in merged:
                    n_added += 1
                merged[entry[0]] = entry[1]
        n_frags += 1

    if n_frags == 0:
        return

    # Atomic write of new master.
    consumed_dir.mkdir(exist_ok=True)
    tmp = master.with_suffix(".g.tmp")
    lines = ["META_H_TO_QS := ["]
    for k in sorted(merged):
        # Emit the GAP literal: ["...", [...]]. Use repr-like dumping.
        v = merged[k]
        # GAP and Python both use [a, b, c] for lists with same syntax.
        # Strings must be double-quoted; Python's repr uses single by default.
        k_lit = '"' + k.replace('\\', '\\\\').replace('"', '\\"') + '"'
        v_lit = repr(v).replace("'", '"')  # python -> gap string syntax
        lines.append(f"  [{k_lit}, {v_lit}],")
    lines.append("];")
    lines.append("META_H_TO_QS_SAVED_OK := true;")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.replace(master)

    # Archive fragments.
    import shutil
    for frag in fragments:
        try:
            shutil.move(str(frag), str(consumed_dir / frag.name))
        except OSError:
            try:
                frag.unlink()
            except OSError:
                pass

    print(f"[merge_h_to_qs] merged {n_frags} fragment(s); "
          f"+{n_added} new H entries; master now has {len(merged)} entries",
          flush=True)


def get_num_transitive_groups(n_max, work_dir):
    """Cache `NrTransitiveGroups(d)` for `d = 1..n_max`.  One GAP call on
    cache miss; subsequent calls read the JSON cache."""
    cache_file = work_dir / "_num_transitive.json"
    cached = {}
    if cache_file.exists():
        cached = {int(k): v for k, v in json.loads(cache_file.read_text()).items()}
        # Extend cache if n_max grew since last run.
        if all(d in cached for d in range(1, n_max + 1)):
            return cached
    work_dir.mkdir(parents=True, exist_ok=True)
    log = work_dir / "_num_transitive.log"
    run_g = work_dir / "_num_transitive_run.g"
    run_g.write_text(
        f'LogTo("{to_cyg(log)}");\n'
        f'for d in [1..{n_max}] do\n'
        f'    Print("NRT ", d, " ", NrTransitiveGroups(d), "\\n");\n'
        f'od;\n'
        f'LogTo();\nQUIT;\n', encoding="utf-8"
    )
    cmd = [GAP_BASH, "--login", "-c",
           f'cd "{GAP_HOME}" && ./gap.exe -q -o 0 "{to_cyg(run_g)}"']
    env = os.environ.copy()
    env["PATH"] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    log_text = log.read_text(encoding="utf-8") if log.exists() else ""
    result = {}
    for m in re.finditer(r"NRT\s+(\d+)\s+(\d+)", log_text):
        result[int(m.group(1))] = int(m.group(2))
    cache_file.write_text(json.dumps(result), encoding="utf-8")
    return result
