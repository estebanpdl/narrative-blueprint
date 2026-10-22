"""Tile admission and dense parity, including fully retained and boundary tiles."""

import sqlite3
from types import SimpleNamespace

import numpy as np
import pytest

from narrative_blueprint.analysis.threshold.contracts import AnalysisRefused, Budget, GraphLimits, GraphParameters
from narrative_blueprint.analysis.threshold.graph import discover_edges, select_pairs


@pytest.mark.parametrize("rows", [1, 3, 8, 32])
@pytest.mark.parametrize("threshold", [0.25, 0.75, 1.0])
def test_vectorized_tiles_match_scalar_snapshot_oracle(tmp_path, rows, threshold):
    vectors = np.random.default_rng(17).normal(size=(31, 7)).astype("<f4")
    vectors[1:5] = vectors[0]
    vectors /= np.linalg.norm(vectors, axis=1)[:, None]
    path = tmp_path / "vectors.f32"
    path.write_bytes(vectors.tobytes())
    database = sqlite3.connect(":memory:")
    database.execute("CREATE TABLE edges (i INTEGER,j INTEGER,weight REAL)")
    disks = []
    scratch = SimpleNamespace(budget=Budget(GraphLimits(max_tile_rows=rows)), vectors=path,
                              db=database, disk=lambda extra=0: disks.append(extra))
    parameters = GraphParameters(threshold=threshold)
    try:
        result = discover_edges(scratch, len(vectors), 7, parameters)
        actual = {(i, j): weight for i, j, weight in database.execute("SELECT * FROM edges")}
    finally:
        database.close()
    vectors = vectors.astype(np.float64)
    vectors /= np.linalg.norm(vectors, axis=1)[:, None]
    scores = np.clip(vectors @ vectors.T, -1, 1)
    # Same scalar rule as the earlier implementation, independent dense scores.
    expected = {(i, j): float(scores[i, j]) for i in range(31) for j in range(i + 1, 31)
                if scores[i, j] >= threshold}
    # A unit cosine can round to either side of 1 with different BLAS shapes.
    away = {(i, j) for i in range(31) for j in range(i + 1, 31)
            if abs(scores[i, j] - threshold) > 1e-7}
    assert actual.keys() & away == expected.keys() & away
    assert all(abs(weight - scores[i, j]) < 1e-7 for (i, j), weight in actual.items())
    assert result["comparisons"] == 465
    tiles = (31 + rows - 1) // rows
    assert len(disks) == tiles * (tiles + 1) // 2 + 2


def test_whole_tile_refused_before_any_edge_insert(tmp_path):
    path = tmp_path / "vectors.f32"
    path.write_bytes(np.ones((8, 1), dtype="<f4").tobytes())
    database = sqlite3.connect(":memory:")
    database.execute("CREATE TABLE edges (i INTEGER,j INTEGER,weight REAL)")
    scratch = SimpleNamespace(budget=Budget(GraphLimits(max_edges=20)), vectors=path,
                              db=database, disk=lambda extra=0: None)
    try:
        with pytest.raises(AnalysisRefused, match="max_edges"):
            discover_edges(scratch, 8, 1, GraphParameters())
        assert database.execute("SELECT count(*) FROM edges").fetchone()[0] == 0
    finally:
        database.close()


@pytest.mark.parametrize("diagonal", [False, True])
def test_exact_scalar_pair_parity_at_threshold_and_tolerance(diagonal):
    parameters = GraphParameters()
    values = [0, -1, 1, .75, np.nextafter(.75, 0), np.nextafter(.75, 1),
              .75 - 1e-7, .75 + 1e-7, .75 - 2e-7]
    scores = np.resize(values, (17, 17))
    accepted, boundaries = select_pairs(scores, diagonal, parameters)
    expected = set()
    boundary_count = 0
    for a in range(17):
        for b in range(a + 1 if diagonal else 0, 17):
            weight = float(scores[a, b])
            boundary_count += abs(weight - parameters.threshold) <= parameters.tolerance
            if weight >= parameters.threshold:
                expected.add((a, b))
    assert set(zip(*np.nonzero(accepted))) == expected
    assert boundaries == boundary_count
