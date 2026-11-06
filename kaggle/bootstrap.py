#!/usr/bin/env python3
"""Kaggle kernel entry point: unpack the repo from the private dataset, then run one driver plan.
The kernel push copies this file per plan with PLAN and RB_HOURS filled in (see kaggle/push.sh)."""
import glob
import os
import subprocess
import sys
import tarfile

PLAN = "__PLAN__"
HOURS = "__HOURS__"
DEST = "/tmp/rb/repo"

archives = glob.glob("/kaggle/input/**/repo.tar.gz", recursive=True)
trees = [os.path.dirname(os.path.dirname(p)) for p in glob.glob("/kaggle/input/**/ragbench/run.py", recursive=True)]
os.makedirs(DEST, exist_ok=True)
if archives:
    with tarfile.open(archives[0]) as tar:
        tar.extractall(DEST)
elif trees:  # Kaggle may have unpacked the archive itself
    subprocess.run(["cp", "-r", trees[0] + "/.", DEST], check=True)
else:
    sys.exit("repo not found under /kaggle/input: " + str(glob.glob("/kaggle/input/**", recursive=True)[:50]))
sys.exit(subprocess.run([sys.executable, "-u", os.path.join(DEST, "kaggle", "driver.py"), PLAN],
                        cwd=DEST, env={**os.environ, "RB_HOURS": HOURS}).returncode)
