"""Diagnostic: spawn one wreath task via the same ProcessPoolExecutor +
_run_subprocess_task path as build_sn_v2 uses."""
import os, sys, time
os.environ['PREDICT_SN_DIR'] = r'C:\Users\jeffr\Downloads\Lifting\parallel_sn_v2'
os.environ['PREDICT_TMP_DIR'] = r'C:\Users\jeffr\Downloads\Lifting\predict_species_tmp\_two_factor_v2'
os.environ['PREDICT_H_CACHE_DIR'] = r'C:\Users\jeffr\Downloads\Lifting\predict_species_tmp\_h_cache_v2'

from concurrent.futures import ProcessPoolExecutor
from build_sn_v2 import _run_subprocess_task

if __name__ == "__main__":
    cmd = [sys.executable, 'predict_full_general_wreath.py',
           '--combo', '[6,1]_[6,1]_[6,1]',
           '--target-n', '18',
           '--output-path', r'C:\Users\jeffr\Downloads\Lifting\test_pool_61_3.g',
           '--timeout', '300']
    with ProcessPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_run_subprocess_task, "wreath", "test_61_3", cmd, 300)
        res = fut.result()
    for k, v in res.items():
        s = str(v)
        if len(s) > 1500: s = s[:600] + "..." + s[-600:]
        print(f"{k}: {s}")
