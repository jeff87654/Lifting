"""Mini watchdog for w507 only.
Launches w507 and relaunches whenever it exits cleanly with a RESTART
heartbeat (i.e., hit the hourly _FORCE_RESTART). Exits when w507's
heartbeat shows 'completed partition [6,4,4,2,2]' — meaning it finished
all combos.
"""
import subprocess, os, time

BASE = r"C:\Users\jeffr\Downloads\Lifting"
SCRIPT_CYG = "/cygdrive/c/Users/jeffr/Downloads/Lifting/parallel_s18/worker_507.g"
HEARTBEAT = os.path.join(BASE, "parallel_s18", "worker_507_heartbeat.txt")
WATCHDOG_LOG = os.path.join(BASE, "watchdog_w507.log")
BASH = r"C:\Program Files\GAP-4.15.1\runtime\bin\bash.exe"

def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(WATCHDOG_LOG, 'a') as f:
        f.write(line + '\n')

def read_hb():
    if not os.path.exists(HEARTBEAT):
        return ''
    try:
        with open(HEARTBEAT) as f:
            return f.read().strip()
    except OSError:
        return ''

def launch():
    env = os.environ.copy()
    env['PATH'] = r"C:\Program Files\GAP-4.15.1\runtime\bin;" + env.get('PATH', '')
    env['CYGWIN'] = 'nodosfilewarning'
    p = subprocess.Popen(
        [BASH, "--login", "-c",
         f'cd "/cygdrive/c/Program Files/GAP-4.15.1/runtime/opt/gap-4.15.1" && ./gap.exe -q -o 0 "{SCRIPT_CYG}"'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
        cwd=r"C:\Program Files\GAP-4.15.1\runtime",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    log(f"launched w507 PID={p.pid}")
    return p

log("watchdog_w507 starting")
relaunch_count = 0
MAX_RELAUNCHES = 20  # enough for any realistic scenario

p = launch()
while True:
    rc = p.poll()
    if rc is None:
        time.sleep(30)
        continue
    hb = read_hb()
    log(f"w507 exited rc={rc}, last heartbeat: {hb[-120:] if hb else '(empty)'}")
    last_line = hb.splitlines()[-1].strip() if hb else ''
    if last_line.startswith('completed partition'):
        log("w507 finished all combos. watchdog exiting.")
        break
    if relaunch_count >= MAX_RELAUNCHES:
        log(f"hit max relaunches ({MAX_RELAUNCHES}); exiting")
        break
    relaunch_count += 1
    time.sleep(5)
    p = launch()

log("watchdog_w507 done")
