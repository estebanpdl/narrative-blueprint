"""Run one fresh process per measurement, sequentially, with owned temporary data."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def offline():
    import importlib.abc
    import socket

    class NoProviders(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, *args):
            if fullname.split(".")[0] in {"openai", "google", "pymongo", "dotenv"}:
                raise RuntimeError("Provider imports disabled during local qualification")
    sys.meta_path.insert(0, NoProviders())
    def forbidden(*args, **kwargs):
        raise RuntimeError("Network disabled during local qualification")
    socket.socket.connect = forbidden
    socket.create_connection = forbidden
    for key in tuple(os.environ):
        if key.upper().startswith(("OPENAI_", "GEMINI_", "GOOGLE_API_")):
            os.environ.pop(key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("calibration", "pipeline", "knn"))
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.work_root = args.work_root.resolve()
    args.report = args.report.resolve()
    args.work_root.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    if args.worker:
        offline()
        # Each worker owns exactly this new child. TemporaryDirectory removes
        # only that resolved child; supplied sources/reports are never inside it.
        with tempfile.TemporaryDirectory(prefix="qualification-", dir=args.work_root) as temporary:
            root = Path(temporary).resolve()
            if root.parent != args.work_root or not root.name.startswith("qualification-"):
                raise RuntimeError("Invalid temporary workspace")
            os.environ["TEMP"] = os.environ["TMP"] = str(root)
            tempfile.tempdir = str(root)
            if args.kind == "calibration":
                from qualification.calibration import calibrate
                result = calibrate(args.cases[0], root)
            elif args.kind == "pipeline":
                from qualification.profiles import run_profile
                result = run_profile(args.cases[0], root, args.source)
            else:
                from qualification.knn import compare_case
                result = compare_case(args.cases[0], root)
        result["temporary_outputs_deleted"] = not root.exists()
        args.report.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
        return
    if args.kind == "calibration":
        from qualification.calibration import CASES
    elif args.kind == "pipeline":
        from qualification.profiles import CASES
    else:
        from qualification.knn import CASES
    cases = args.cases or [case for case in CASES if case != "local-sample"]
    reports = []
    for case in cases:
        report = args.report.with_name(args.report.stem + "-" + case + ".json")
        command = [sys.executable, str(Path(__file__).resolve()), args.kind, "--worker",
                   "--cases", case, "--work-root", str(args.work_root), "--report", str(report)]
        if args.source:
            command += ["--source", str(args.source.resolve())]
        env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                   NUMEXPR_NUM_THREADS="1", TEMP=str(args.work_root), TMP=str(args.work_root))
        subprocess.run(command, env=env, check=True)
        result = json.loads(report.read_text(encoding="utf-8"))
        reports.append(result)
        print(json.dumps({key: result[key] for key in ("case", "status", "nodes", "edges", "communities") if key in result}), flush=True)
    args.report.write_text(json.dumps({"kind": args.kind, "runs": reports}, indent=2, allow_nan=False), encoding="utf-8")
    if any(run.get("expectation_met") is False or run.get("sampling_errors") for run in reports):
        raise RuntimeError("Unexpected qualification outcome; inspect the saved aggregate report")


if __name__ == "__main__":
    main()
