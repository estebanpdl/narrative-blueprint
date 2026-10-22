"""Resource and record contracts shared by snapshot readers and writers."""

from dataclasses import asdict, dataclass
import hashlib
import json

SPACE_FIELDS = ("provider", "model_name", "model_revision", "task_type", "preprocessing")
FIELDS = ("uuid", "text", "embedding", *SPACE_FIELDS, "occurrence_id", "generation_id")


class SnapshotRefused(ValueError):
    """Value-free, machine-readable admission or consistency refusal."""

    def __init__(self, reason, detail=""):
        self.reason = reason
        super().__init__(f"{reason}: {detail}" if detail else reason)


@dataclass(frozen=True)
class SnapshotLimits:
    max_source_bytes: int = 1024**3
    max_records: int = 1_000_000
    max_record_bytes: int = 1024**2
    max_batch_records: int = 128
    max_batch_bytes: int = 32 * 1024**2
    max_working_bytes: int = 256 * 1024**2
    max_disk_bytes: int = 4 * 1024**3

    def __post_init__(self):
        for key, value in asdict(self).items():
            if type(value) is not int or value <= 0:
                raise SnapshotRefused("invalid_limit", f"{key} must be a positive integer")
        # Covers decoded Python objects, vector conversion/normalization copies,
        # and a bounded SQLite cache. This is admission, not an OS memory quota.
        self.check("max_working_bytes", 4 * self.max_batch_bytes + 16 * self.max_record_bytes)

    def check(self, name, demand):
        limit = getattr(self, name)
        if demand > limit:
            raise SnapshotRefused(name, f"demand={demand}, limit={limit}; increase --{name.replace('_', '-')} or select/convert a smaller source")


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def project(row, fields):
    """Recover only requested extension fields; metadata cannot override columns."""
    extra = row.get("metadata")
    if extra:
        try:
            extra = json.loads(extra)
        except (ValueError, TypeError, RecursionError) as exc:
            raise SnapshotRefused("invalid_metadata") from exc
        if not isinstance(extra, dict):
            raise SnapshotRefused("invalid_metadata")
    else:
        extra = {}
    result = {}
    for field in fields:
        value = row.get(field)
        if field in extra:
            if value is not None and value != extra[field]:
                raise SnapshotRefused("conflicting_metadata")
            value = extra[field]
        result[field] = value
    return result
