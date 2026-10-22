"""Independent exact-kNN oracle and bounded export admission regressions."""

import csv
import hashlib
import io
from types import SimpleNamespace

import numpy as np
import pytest

from benchmarks.qualification.knn import exact_knn
from narrative_blueprint.analysis.threshold.contracts import AnalysisRefused, GraphLimits
from narrative_blueprint.analysis.threshold.outputs import Exports, HEADERS


@pytest.mark.parametrize("symmetry", ["union", "mutual"])
def test_knn_matches_dense_oracle_and_stable_id_ties(symmetry):
    vectors = np.array([[1., 0.], [1., 0.], [1., 0.], [.8, .6], [0., 1.]])
    ids = ["b", "a", "d", "c", "e"]
    unit = vectors / np.linalg.norm(vectors, axis=1)[:, None]
    dense = unit @ unit.T
    directed = {}
    for i in range(len(ids)):
        ranked = sorted((j for j in range(len(ids)) if j != i), key=lambda j: (-dense[i, j], ids[j]))[:1]
        for j in ranked:
            if dense[i, j] >= .75:
                directed[(ids[i], ids[j])] = dense[i, j]
    expected = {tuple(sorted((a, b))) for a, b in directed if symmetry == "union" or (b, a) in directed}
    actual = exact_knn(vectors, ids, 1, .75, symmetry, rows=2)
    assert actual.keys() == expected
    assert all(a != b for a, b in actual)
    reverse = exact_knn(vectors[::-1], ids[::-1], 1, .75, symmetry, rows=2)
    assert reverse == actual
    if symmetry == "mutual":
        assert expected == {("a", "b")}


def test_export_chunking_preserves_bytes_and_bounds_disk_checks(tmp_path):
    checks = []
    scratch = SimpleNamespace(directory=tmp_path, budget=SimpleNamespace(limits=GraphLimits()),
                              disk=lambda extra=0: checks.append(extra))
    values = [("=literal", "unicode ñ\nquoted", i, 1, 2, "bridge") for i in range(5000)]
    expected = io.StringIO(newline="")
    writer = csv.writer(expected)
    writer.writerow(HEADERS["edges.csv"])
    writer.writerows(values)
    data = expected.getvalue().encode("utf-8")
    exports = Exports(scratch)
    exports.write_csv("edges.csv", iter(values))
    assert (tmp_path / "edges.csv").read_bytes() == data
    assert exports.files["edges.csv"] == {"rows": 5000, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    assert len(checks) < 10
    assert max(checks) <= 2 * 65536


def test_export_checks_limit_before_pending_data_is_written(tmp_path):
    scratch = SimpleNamespace(directory=tmp_path, budget=SimpleNamespace(limits=GraphLimits(max_export_bytes=100)),
                              disk=lambda extra=0: None)
    with pytest.raises(AnalysisRefused, match="max_export_bytes"):
        Exports(scratch).write_csv("edges.csv", [("a", "b", .8, 1, 1, "internal")])
    assert (tmp_path / "edges.csv").stat().st_size == 0
