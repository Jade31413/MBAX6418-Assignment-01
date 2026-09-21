"""Rebuild saved analysis offline; opt in to missing model calls with --classify."""
import argparse
from pathlib import Path
import subprocess
import sys


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--classify", action="store_true", help="Prepare samples and run/resume model calls (needs COURSE_API_KEY)")
    args = p.parse_args()
    scripts = Path(__file__).resolve().parent
    def run(name, *args):
        subprocess.run([sys.executable, str(scripts / name), *args], check=True)
    if args.classify:
        run("prepare_data.py")
        for mode in ("smoke", "baseline", "balanced"):
            run("classify.py", mode)
    for mode in ("baseline", "balanced"):
        run("score.py", mode)
        run("add_emotions.py", mode)
    run("prepare_dashboard.py")
    run("build_dashboard.py")
    run("verify_outputs.py")
    run("build_report.py")
