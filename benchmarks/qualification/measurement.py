"""Value-free resource measurements for a single, fresh worker process."""

from contextlib import contextmanager
from importlib.metadata import version
import os
from pathlib import Path
import platform
import sys
import threading
import time

from narrative_blueprint.analysis.threshold.contracts import process_memory


def environment():
    from threadpoolctl import threadpool_info
    return {"python": sys.version, "executable": sys.executable,
            "platform": platform.platform(), "cpu_count": os.cpu_count(),
            "versions": {name: version(name) for name in
                         ("numpy", "networkx", "scikit-learn", "threadpoolctl")},
            "threads": [{key: item.get(key) for key in
                         ("internal_api", "num_threads", "version", "architecture")}
                        for item in threadpool_info()]}


class Measurement:
    """Sample working set/private bytes and owned files; retain no source values."""

    def __init__(self, root, interval=0.05):
        self.root = Path(root)
        self.interval = interval
        self.stages = {}
        self.active = []
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.errors = []

    def sample(self):
        try:
            memory = process_memory()
            size = 0
            for path in self.root.rglob("*"):
                try:
                    if path.is_file():
                        size += path.stat().st_size
                except FileNotFoundError:
                    pass  # Publication renames files during sampling.
            with self.lock:
                for name in self.active:
                    stage = self.stages[name]
                    for key in ("current_bytes", "private_bytes"):
                        if memory[key] is not None:
                            stage["sampled_peak_" + key] = max(stage.get("sampled_peak_" + key, 0), memory[key])
                    stage["sampled_peak_owned_disk_bytes"] = max(stage.get("sampled_peak_owned_disk_bytes", 0), size)
        except Exception as exc:
            self.errors.append(type(exc).__name__)

    def poll(self):
        while not self.stop.wait(self.interval):
            self.sample()

    def __enter__(self):
        self.thread = threading.Thread(target=self.poll, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()

    @contextmanager
    def stage(self, name):
        started = time.perf_counter()
        with self.lock:
            self.stages[name] = {"start_memory": process_memory()}
            self.active.append(name)
        self.sample()
        try:
            yield
        finally:
            self.sample()
            with self.lock:
                self.active.remove(name)
                self.stages[name].update(seconds=time.perf_counter() - started,
                                         end_memory=process_memory())

    def wrap(self, function, name):
        def measured(*args, **kwargs):
            with self.stage(name):
                return function(*args, **kwargs)
        return measured
