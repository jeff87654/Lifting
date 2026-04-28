"""Watchdog: launch 4 S_18 workers and resume them on clean restarts.

Runs worker_{wid}.g scripts in parallel. Each worker's GAP script loops
over its myPartitions list; on the hourly _FORCE_RESTART it writes
"RESTART after partition X (partial)" to its heartbeat and calls
QuitGap(0). The watchdog relaunches whenever:
  - the heartbeat ends in "RESTART ..." (intentional restart request), or
  - the process exited with a non-zero code (crash / kill).
A worker is considered done when it exits with rc=0 and its heartbeat
does not end in RESTART — that's the QUIT at the end of the .g script
after finishing all myPartitions.

Default workers: 266 267 268 269 (most recently active per heartbeat).
Override via CLI: python watchdog_4workers.py 100 101 102 103
"""
import os
import subprocess
import sys
import time

DEFAULT_WORKERS = [266, 267, 268, 269]

BASE_DIR = r"C:\Users\jeffr\Downloads\Lifting"
OUTPUT_DIR = os.path.join(BASE_DIR, "parallel_s18")
GAP_RUNTIME = r"C:\Program Files\GAP-4.15.1\runtime"
BASH_EXE = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"
GAP_BIN_PATH = r"C:\Program Files\GAP-4.15.1\runtime\bin"
GAP_CWD = "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1"

# Cooldown between a worker's exit and its relaunch
RESTART_COOLDOWN_S = 5

# Cap on relaunches per worker to avoid tight crash loops
MAX_RELAUNCHES_PER_WORKER = 200

# Extended cooldown if a worker exits in under this many seconds — likely
# a startup-time crash rather than the hourly _FORCE_RESTART
SHORT_RUN_SECONDS = 30
SHORT_RUN_COOLDOWN_S = 60

# Poll cadence
POLL_INTERVAL_S = 30


def gap_env():
    env = os.environ.copy()
    env["PATH"] = GAP_BIN_PATH + ";" + env.get("PATH", "")
    env["CYGWIN"] = "nodosfilewarning"
    return env


def worker_paths(wid):
    script_win = os.path.join(OUTPUT_DIR, f"worker_{wid}.g")
    script_cyg = "/cygdrive/c/" + script_win[3:].replace("\\", "/")
    heartbeat = os.path.join(OUTPUT_DIR, f"worker_{wid}_heartbeat.txt")
    results = os.path.join(OUTPUT_DIR, f"worker_{wid}_results.txt")
    return script_win, script_cyg, heartbeat, results


def read_heartbeat(wid):
    _, _, hb, _ = worker_paths(wid)
    if not os.path.exists(hb):
        return ""
    try:
        with open(hb, "r") as f:
            return f.read().strip()
    except OSError:
        return ""


def heartbeat_wants_restart(hb):
    """The worker's QuitGap(0) path writes a line starting with 'RESTART'."""
    if not hb:
        return False
    last = hb.splitlines()[-1].strip() if hb else ""
    return last.startswith("RESTART")


def launch_worker(wid):
    script_win, script_cyg, _, _ = worker_paths(wid)
    if not os.path.exists(script_win):
        return None, f"worker_{wid}.g not found at {script_win}"
    cmd = [
        BASH_EXE, "--login", "-c",
        f'cd "{GAP_CWD}" && ./gap.exe -q -o 0 "{script_cyg}"',
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=gap_env(),
        cwd=GAP_RUNTIME,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    return proc, None


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def main(worker_ids):
    log(f"Starting watchdog for workers: {worker_ids}")
    # state[wid] = { "proc": Popen|None, "relaunches": int,
    #                "started_at": float, "done": bool }
    state = {
        wid: {"proc": None, "relaunches": 0, "started_at": 0.0, "done": False}
        for wid in worker_ids
    }

    # Initial launch: always start a worker unless its last heartbeat shows
    # a completed-final-partition state without a RESTART. We can't cheaply
    # tell from the heartbeat whether a non-RESTART "completed" line refers
    # to the final partition, so err on the side of launching — a worker
    # that finished everything will replay its loop, skip all partitions
    # via checkpoints (fast), and exit cleanly. The watchdog will then see
    # rc=0 and no RESTART heartbeat and mark it done.
    for wid in worker_ids:
        proc, err = launch_worker(wid)
        if err:
            log(f"W{wid}: {err}")
            state[wid]["done"] = True
            continue
        state[wid]["proc"] = proc
        state[wid]["started_at"] = time.time()
        log(f"W{wid}: launched PID={proc.pid}")

    # Monitor + relaunch loop
    while True:
        time.sleep(POLL_INTERVAL_S)
        any_running = False
        for wid in worker_ids:
            st = state[wid]
            if st["done"]:
                continue
            proc = st["proc"]
            if proc is None:
                continue

            rc = proc.poll()
            if rc is None:
                any_running = True
                hb = read_heartbeat(wid).splitlines()
                preview = hb[-1][:100] if hb else "(no heartbeat)"
                log(f"W{wid}: running PID={proc.pid} — {preview}")
                continue

            # Worker exited. Decide: done or relaunch.
            elapsed = time.time() - st["started_at"]
            hb = read_heartbeat(wid)
            last_hb = hb.splitlines()[-1][:120] if hb else "(no heartbeat)"
            wants_restart = heartbeat_wants_restart(hb)
            log(
                f"W{wid}: exited rc={rc} after {elapsed:.0f}s "
                f"— heartbeat: {last_hb} — wants_restart={wants_restart}"
            )

            if rc == 0 and not wants_restart:
                log(f"W{wid}: clean exit and no RESTART request — done")
                st["proc"] = None
                st["done"] = True
                continue

            if st["relaunches"] >= MAX_RELAUNCHES_PER_WORKER:
                log(f"W{wid}: hit max relaunches ({MAX_RELAUNCHES_PER_WORKER}) — giving up")
                st["proc"] = None
                st["done"] = True
                continue

            cooldown = RESTART_COOLDOWN_S
            if elapsed < SHORT_RUN_SECONDS:
                cooldown = SHORT_RUN_COOLDOWN_S
                log(f"W{wid}: short run ({elapsed:.0f}s) — cooldown {cooldown}s")

            time.sleep(cooldown)
            st["relaunches"] += 1
            new_proc, err = launch_worker(wid)
            if err:
                log(f"W{wid}: relaunch failed: {err}")
                st["proc"] = None
                st["done"] = True
                continue
            st["proc"] = new_proc
            st["started_at"] = time.time()
            log(f"W{wid}: relaunched (#{st['relaunches']}) PID={new_proc.pid}")
            any_running = True

        if not any_running:
            log("All workers finished (or gave up). Exiting watchdog.")
            break


if __name__ == "__main__":
    wids = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else DEFAULT_WORKERS
    if len(wids) == 0:
        print("usage: python watchdog_4workers.py [wid1 wid2 ...]", file=sys.stderr)
        sys.exit(2)
    main(wids)
