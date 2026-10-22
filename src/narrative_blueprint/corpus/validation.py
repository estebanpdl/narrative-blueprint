"""Pure validation of reported recipes and finite normalized vectors."""

from array import array
import json
import math
import sys

from .contracts import SPACE_FIELDS, SnapshotRefused, digest, encoded


def reported_space(row):
    recipe = {}
    for field in SPACE_FIELDS:
        value = row.get(field)
        if value is not None and not isinstance(value, str):
            raise SnapshotRefused("invalid_metadata")
        recipe[field] = value or None
    return recipe


def normalized_vector(value, limits):
    """Scale before norm calculation to avoid overflow and subnormal underflow."""
    if value is None or value == "":
        return None, None, "missing_vector"
    if isinstance(value, str):
        limits.check("max_record_bytes", len(value.encode("utf-8")))
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):
            return None, None, "malformed_vector"
    if value is None:
        return None, None, "missing_vector"
    if not isinstance(value, list) or not value:
        return None, None, "invalid_vector_shape"
    limits.check("max_batch_bytes", len(value) * 64)
    if any(type(item) not in (int, float) for item in value):
        return None, None, "nonnumeric_vector"
    try:
        numeric = array("d", value)
    except (OverflowError, ValueError):
        return None, None, "nonfinite_vector"
    if not all(math.isfinite(item) for item in numeric):
        return None, None, "nonfinite_vector"
    scale = max(abs(item) for item in numeric)
    if scale == 0:
        return None, None, "zero_vector"
    norm = math.sqrt(math.fsum((item / scale)**2 for item in numeric))
    normalized = array("f", ((item / scale) / norm for item in numeric))
    if sys.byteorder != "little":
        normalized.byteswap()
        numeric.byteswap()
    return normalized.tobytes(), digest(numeric.tobytes()), None


def document_signature(document):
    """Hash the exact stored response payload without retaining it in the ledger."""
    vector = document.get("embedding")
    if isinstance(vector, str):
        try:
            vector = json.loads(vector)
        except (ValueError, RecursionError):
            pass
    fields = {key: document.get(key) for key in ("uuid", "text")}
    fields.update({key: document.get(key) or None for key in SPACE_FIELDS})
    if isinstance(vector, list) and all(type(value) in (int, float) for value in vector):
        try:
            vector = [float(value) for value in vector]
        except OverflowError:
            pass
    fields["embedding"] = vector
    return digest(encoded(fields))
