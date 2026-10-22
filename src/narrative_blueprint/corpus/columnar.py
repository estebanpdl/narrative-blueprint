"""Parquet decoding admission and an injected, fake-testable Mongo contract."""

from contextlib import contextmanager

from .contracts import FIELDS, SnapshotLimits, SnapshotRefused, encoded, project


def parquet_rows(path, fields, limits):
    import pyarrow.parquet as pq

    # Bound footer strings/containers as well as projected decompressed row groups.
    with pq.ParquetFile(path, pre_buffer=False, memory_map=False,
                        thrift_string_size_limit=limits.max_record_bytes,
                        thrift_container_size_limit=limits.max_batch_bytes) as source:
        names = source.schema_arrow.names
        if len(names) != len(set(names)) or not {"uuid", "text", "embedding"} <= set(names):
            raise SnapshotRefused("source_schema")
        selected = [field for field in (*fields, "metadata") if field in names]
        limits.check("max_records", source.metadata.num_rows)
        for number in range(source.metadata.num_row_groups):
            group = source.metadata.row_group(number)
            size = sum(group.column(i).total_uncompressed_size
                       for i in range(group.num_columns)
                       if group.column(i).path_in_schema.split(".")[0] in selected)
            limits.check("max_batch_bytes", size)
            batch_size = min(limits.max_batch_records,
                             max(1, limits.max_batch_bytes // limits.max_record_bytes))
            for batch in source.iter_batches(batch_size=batch_size, row_groups=[number],
                                               columns=selected, use_threads=False):
                limits.check("max_batch_bytes", batch.nbytes)
                for offset in range(batch.num_rows):
                    item = batch.slice(offset, 1)
                    limits.check("max_record_bytes", item.nbytes)
                    yield project(item.to_pylist()[0], fields)


@contextmanager
def mongo_documents(collection, *, fields=FIELDS, limits=None, query=None):
    """Caller owns client and consistent read session; cursor is always closed.

    Live Mongo resource/consistency qualification is not implied. Server/driver
    BSON response buffers precede these application checks.
    """
    limits = limits or SnapshotLimits()
    if not set(fields) <= set(FIELDS):
        raise SnapshotRefused("projection")
    projection = {field: 1 for field in (*fields, "metadata")}
    projection["_id"] = 0
    cursor = collection.find(query or {}, projection)

    def records():
        total = 0
        for ordinal, row in enumerate(cursor, 1):
            limits.check("max_records", ordinal)
            payload = encoded(row)
            limits.check("max_record_bytes", len(payload))
            total += len(payload)
            limits.check("max_source_bytes", total)
            yield project(row, fields)

    stream = records()
    try:
        cursor.sort("_id", 1).batch_size(
            min(limits.max_batch_records, max(1, limits.max_batch_bytes // limits.max_record_bytes)))
        yield stream
    finally:
        stream.close()
        cursor.close()
