"""Diagnostic: spawn one c2_fast task via the same ProcessPoolExecutor."""
import os, sys
os.environ['PREDICT_SN_DIR'] = r'C:\Users\jeffr\Downloads\Lifting\parallel_sn_v2'
os.environ['PREDICT_TMP_DIR'] = r'C:\Users\jeffr\Downloads\Lifting\predict_species_tmp\_two_factor_v2'
os.environ['PREDICT_H_CACHE_DIR'] = r'C:\Users\jeffr\Downloads\Lifting\predict_species_tmp\_h_cache_v2'

from concurrent.futures import ProcessPoolExecutor
from build_sn_v2 import _run_subprocess_task

if __name__ == "__main__":
    cmd = [sys.executable, 'run_c2_fast_path.py',
           '--combo', '[2,1]_[2,1]_[2,1]_[2,1]_[2,1]_[2,1]_[2,1]_[2,1]',
           '--output-path', r'C:\Users\jeffr\Downloads\Lifting\test_pool_c2.g',
           '--timeout', '300']
    with ProcessPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_run_subprocess_task, "c2", "test_c2", cmd, 300)
        res = fut.result()
    for k, v in res.items():
        s = str(v)
        if len(s) > 2000: s = s[:1000] + "..." + s[-1000:]
        print(f"{k}: {s}")
