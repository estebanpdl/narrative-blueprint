"""Bounded, read-only admission of a single legacy CSV embedding source."""

import csv
import hashlib
import io
import json
import math
from pathlib import Path

from cli.analysis_options import EmbeddingInputError


SPACE_FIELDS = ("provider", "model_name", "model_revision", "task_type", "preprocessing")


def _hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_source(source, limits):
    path = Path(source)
    if path.suffix.lower() != ".csv":
        raise EmbeddingInputError("Diagnostic sources must be local .csv files")
    if not path.is_file():
        raise EmbeddingInputError(f"Analysis source is not a regular file: {path}")
    limit = limits["max_source_bytes"]
    if path.stat().st_size > limit:
        raise EmbeddingInputError(f"Source exceeds max_source_bytes={limit}; select a smaller source")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise EmbeddingInputError(f"Source exceeds max_source_bytes={limit}")
    fingerprint = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise EmbeddingInputError("Source must be UTF-8 CSV") from exc

    documents = []
    seen = set()
    spaces = {field: set() for field in SPACE_FIELDS}
    old_field_limit = csv.field_size_limit()
    csv.field_size_limit(limit)
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        columns = reader.fieldnames or []
        if not {"uuid", "text", "embedding"} <= set(columns):
            raise EmbeddingInputError("Source requires uuid, text and embedding columns")
        if len(columns) != len(set(columns)):
            raise EmbeddingInputError("Duplicate CSV column names are ambiguous")
        for ordinal, row in enumerate(reader, 1):
            if ordinal > limits["max_records"]:
                raise EmbeddingInputError(f"Source exceeds max_records={limits['max_records']}")
            if None in row or any(value is None for value in row.values()):
                raise EmbeddingInputError(f"Row {ordinal}: column count mismatch")
            uuid, narrative = row["uuid"], row["text"]
            if not uuid.strip() or not narrative.strip():
                raise EmbeddingInputError(f"Row {ordinal}: uuid and text must be nonempty")
            if uuid in seen:
                raise EmbeddingInputError(
                    f"Row {ordinal}: repeated uuid; resolve occurrence versus retry identity first"
                )
            seen.add(uuid)
            vector = _validate_vector(row["embedding"], ordinal, limits)
            if documents and len(vector) != len(documents[0]["embedding"]):
                raise EmbeddingInputError(f"Row {ordinal}: inconsistent vector dimension")
            for field in SPACE_FIELDS:
                value = row.get(field) or None
                spaces[field].add(value)
                if len(spaces[field]) > 1:
                    raise EmbeddingInputError(f"Row {ordinal}: mixed or partially missing {field} metadata")
            identity = json.dumps([fingerprint, ordinal, uuid], ensure_ascii=False)
            documents.append({
                "occurrence_id": _hash(identity),
                "source_row": ordinal,
                "source_uuid": uuid,
                "text": narrative,
                "text_hash": _hash(narrative),
                "embedding": vector,
            })
    except (csv.Error, RecursionError) as exc:
        raise EmbeddingInputError(f"Malformed diagnostic source: {exc}") from exc
    finally:
        csv.field_size_limit(old_field_limit)

    count = len(documents)
    dimension = len(documents[0]["embedding"]) if documents else 0
    pairs = count * (count - 1) // 2
    if pairs > limits["max_pairs"]:
        raise EmbeddingInputError(
            f"Possible pairs {pairs} exceed max_pairs={limits['max_pairs']}; "
            "select fewer records or raise the limit within its hard ceiling"
        )
    # Conservative admission model for decoded objects, two graph passes and
    # dense matrices. This is not a measured or enforced process RSS ceiling.
    estimate = 16 * len(raw) + 128 * count * dimension + 32 * count**2 + 8192 * pairs
    if estimate > limits["max_working_bytes"]:
        raise EmbeddingInputError(
            f"Estimated working bytes {estimate} exceed "
            f"max_working_bytes={limits['max_working_bytes']}; select a smaller source"
        )
    metadata = {field: next(iter(values)) if values else None
                for field, values in spaces.items()}
    return documents, {
        "path": str(path.resolve()),
        "sha256": fingerprint,
        "bytes": len(raw),
        "dimension": dimension,
        "reported_space": metadata,
        "possible_pairs": pairs,
        "estimated_working_bytes": estimate,
    }


def _validate_vector(value, ordinal, limits):
    try:
        vector = json.loads(value)
    except (ValueError, RecursionError) as exc:
        raise EmbeddingInputError(f"Row {ordinal}: embedding must be a JSON numeric array") from exc
    if not isinstance(vector, list) or not vector:
        raise EmbeddingInputError(f"Row {ordinal}: embedding must be a nonempty array")
    if len(vector) > limits["max_dimension"]:
        raise EmbeddingInputError(f"Row {ordinal}: dimension exceeds max_dimension={limits['max_dimension']}")
    try:
        valid = all(type(item) in (float, int) and math.isfinite(item) for item in vector)
        norm = math.hypot(*vector) if valid else 0
    except (OverflowError, TypeError):
        valid, norm = False, 0
    if not valid or not math.isfinite(norm) or norm == 0:
        raise EmbeddingInputError(f"Row {ordinal}: vector must be finite, numeric and nonzero")
    # Legacy cosine squares values; extreme magnitudes can overflow/underflow.
    if not 1e-100 <= norm <= 1e100:
        raise EmbeddingInputError(f"Row {ordinal}: vector magnitude is outside the diagnostic numeric range")
    return vector
