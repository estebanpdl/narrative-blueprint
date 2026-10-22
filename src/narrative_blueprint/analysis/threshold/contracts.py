"""Explicit numeric policy and conservative allocation admission."""

from dataclasses import asdict, dataclass
import ctypes
import math
import os
import time

from narrative_blueprint.corpus.contracts import SnapshotRefused


class AnalysisRefused(SnapshotRefused):
    """An incomplete analysis, never a truncated successful graph."""


@dataclass(frozen=True)
class GraphParameters:
    threshold: float = 0.75
    tolerance: float = 1e-7
    resolution: float = 1.0
    seed: int = 42

    def __post_init__(self):
        if not math.isfinite(self.threshold) or not 0 < self.threshold <= 1:
            raise AnalysisRefused("invalid_threshold", "threshold must be in (0, 1]")
        if not math.isfinite(self.tolerance) or not 0 <= self.tolerance < self.threshold:
            raise AnalysisRefused("invalid_tolerance", "tolerance must be in [0, threshold)")
        if not math.isfinite(self.resolution) or self.resolution <= 0:
            raise AnalysisRefused("invalid_resolution")
        if type(self.seed) is not int or not 0 <= self.seed <= 2**32 - 1:
            raise AnalysisRefused("invalid_seed")


@dataclass(frozen=True)
class GraphLimits:
    max_nodes: int = 100_000
    max_edges: int = 1_000_000
    max_comparisons: int = 100_000_000
    max_tile_rows: int = 256
    max_tile_bytes: int = 64 * 1024**2
    max_graph_bytes: int = 512 * 1024**2
    max_clustering_bytes: int = 1024**3
    max_working_bytes: int = 2 * 1024**3
    max_disk_bytes: int = 4 * 1024**3
    max_export_bytes: int = 1024**3
    max_record_bytes: int = 1024**2
    max_snapshot_bytes: int = 4 * 1024**3
    max_seconds: float = 600.0
    max_view_rows: int = 1000
    max_view_bytes: int = 16 * 1024**2

    def __post_init__(self):
        for name, value in asdict(self).items():
            if name == "max_seconds":
                valid = isinstance(value, (int, float)) and math.isfinite(value) and value > 0
            else:
                valid = type(value) is int and value > 0
            if not valid:
                raise AnalysisRefused("invalid_limit", f"{name} must be positive")

    def check(self, name, demand):
        limit = getattr(self, name)
        if demand > limit:
            raise AnalysisRefused(name, f"demand={demand}, limit={limit}; increase --{name.replace('_', '-')} or use a smaller snapshot")


def process_memory():
    """Current and peak working set on Windows; peak RSS on POSIX."""
    if os.name == "nt":
        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t) for name in (
                    "peak", "current", "pool_peak", "pool", "nonpool_peak",
                    "nonpool", "pagefile", "peak_pagefile", "private")]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess
        handle.restype = ctypes.c_void_p
        query = ctypes.windll.psapi.GetProcessMemoryInfo
        query.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        if not query(handle(), ctypes.byref(counters), counters.cb):
            raise OSError("Cannot measure process memory")
        return {"current_bytes": counters.current, "peak_bytes": counters.peak,
                "private_bytes": counters.private, "peak_private_bytes": counters.peak_pagefile,
                "measurement": "windows-working-set"}
    import resource
    import sys
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    return {"current_bytes": peak, "peak_bytes": peak, "private_bytes": None,
            "peak_private_bytes": None,
            "measurement": "posix-peak-rss"}


def tile_bytes(rows, dimension):
    # Two float64 blocks, float32 read buffers, normalization temporaries,
    # Scores, masks, accepted index/weight arrays and BLAS scratch are bounded
    # by the tile even for a fully accepted block; no NxN allocation.
    return 48 * rows * dimension + 48 * rows * rows + 65536


def graph_bytes(nodes, edges):
    # Calibrated on CPython/NetworkX; see docs/qualification.md for measured
    # shapes and safety margins. Requalify when changing graph representations.
    return 65536 + 1024 * nodes + 512 * edges


def clustering_bytes(nodes, edges):
    """Additional workspace above the admitted graph, including coarsening."""
    return 8 * 1024**2 + 2048 * nodes + 768 * edges


class Budget:
    def __init__(self, limits=None):
        self.limits = limits or GraphLimits()
        self.start = time.perf_counter()
        self.baseline = process_memory()["current_bytes"]
        self.peak = 0
        self.tick()

    def tick(self):
        self.limits.check("max_seconds", time.perf_counter() - self.start)
        memory = process_memory()
        self.peak = max(self.peak, memory["current_bytes"])
        self.limits.check("max_working_bytes", memory["current_bytes"])

    def admit(self, nodes, dimension):
        limits = self.limits
        limits.check("max_nodes", nodes)
        limits.check("max_comparisons", nodes * (nodes - 1) // 2)
        self.admit_graph(nodes, 0)
        fixed = 16 * limits.max_record_bytes + 8 * 1024**2
        allowance = min(limits.max_tile_bytes, limits.max_working_bytes - self.baseline - fixed)
        rows = min(limits.max_tile_rows, max(1, nodes))
        while rows > 1 and tile_bytes(rows, dimension) > allowance:
            rows //= 2
        limits.check("max_tile_bytes", tile_bytes(rows, dimension))
        limits.check("max_working_bytes", self.baseline + fixed + tile_bytes(rows, dimension))
        return rows

    def admit_graph(self, nodes, edges):
        self.limits.check("max_edges", edges)
        graph = graph_bytes(nodes, edges)
        clustering = clustering_bytes(nodes, edges)
        self.limits.check("max_graph_bytes", graph)
        self.limits.check("max_clustering_bytes", clustering)
        self.limits.check("max_working_bytes", self.baseline + graph + clustering + 16 * self.limits.max_record_bytes + 8 * 1024**2)
        return {"graph_bytes": graph, "clustering_bytes": clustering,
                "memory_estimate_version": "networkx-calibrated-1"}
