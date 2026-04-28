"""Standalone watchdog for [12,4,2] partition. Auto-resumes on exit."""
import time, os, shutil
import run_s18 as r

PARTITION = (12, 4, 2)

def next_wid():
    ckpt_base = os.path.join(r.OUTPUT_DIR, "checkpoints")
    wids = set()
    if os.path.isdir(ckpt_base):
        for e in os.listdir(ckpt_base):
            if e.startswith("worker_"):
                try: wids.add(int(e.replace("worker_", "")))
                except ValueError: pass
    return max(wids) + 1 if wids else 0

def launch(prev_wid=None):
    wid = next_wid()
    ckpt_dir = os.path.join(r.OUTPUT_DIR, "checkpoints", f"worker_{wid}")
    os.makedirs(ckpt_dir, exist_ok=True)
    if prev_wid is not None:
        old = os.path.join(r.OUTPUT_DIR, "checkpoints", f"worker_{prev_wid}")
        if os.path.isdir(old):
            for f in os.listdir(old):
                if "12_4_2" in f:
                    src, dst = os.path.join(old, f), os.path.join(ckpt_dir, f)
                    if not os.path.exists(dst):
                        shutil.copy2(src, dst)
    script = r.create_worker_gap_script([PARTITION], wid, r.OUTPUT_DIR)
    proc = r.launch_gap_worker(script, wid)
    print(f"[{time.strftime('%H:%M:%S')}] Worker {wid} launched (PID {proc.pid})")
    return wid, proc

# Check if already complete
summary = os.path.join(r.OUTPUT_DIR, r.partition_dir_name(PARTITION), "summary.txt")

wid, proc = launch(145)  # inherit from W145's checkpoint

while True:
    rc = proc.wait()
    elapsed = "?"
    print(f"[{time.strftime('%H:%M:%S')}] Worker {wid} exited (rc={rc})")
    if os.path.exists(summary):
        print(f"[12,4,2] COMPLETE!")
        with open(summary) as f:
            print(f.read())
        break
    time.sleep(30)
    wid, proc = launch(wid)
