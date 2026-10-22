# -*- coding: utf-8 -*-

import json
import os
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

from .database import Database


class ParquetFileManager(Database):
    '''Store embedding documents in a columnar Parquet file.'''

    SCHEMA = pa.schema([
        pa.field('uuid', pa.string()),
        pa.field('text', pa.string()),
        pa.field('embedding', pa.list_(pa.float64()), nullable=False),
        pa.field('model_name', pa.string()),
        pa.field('provider', pa.string()),
        pa.field('task_type', pa.string()),
        pa.field('metadata', pa.string())
    ])

    def __init__(self, output_path: str):
        self.output_path = output_path
        self._writer = None
        self._temporary_path = None

        output_dir = os.path.dirname(os.path.abspath(self.output_path))
        os.makedirs(output_dir, exist_ok=True)

    @staticmethod
    def _to_record(document: dict) -> dict:
        core_fields = {
            'uuid', 'text', 'embedding', 'model_name', 'provider', 'task_type'
        }
        metadata = {
            key: value for key, value in document.items()
            if key not in core_fields
        }
        return {
            'uuid': (
                str(document['uuid'])
                if document.get('uuid') is not None else None
            ),
            'text': document.get('text'),
            'embedding': document['embedding'],
            'model_name': document.get('model_name'),
            'provider': document.get('provider'),
            'task_type': document.get('task_type'),
            'metadata': (
                json.dumps(metadata, ensure_ascii=False)
                if metadata else None
            )
        }

    @staticmethod
    def _to_document(record: dict) -> dict:
        document = {
            'uuid': record['uuid'],
            'text': record['text'],
            'embedding': record['embedding'],
            'model_name': record['model_name'],
            'provider': record['provider']
        }
        if record['task_type'] is not None:
            document['task_type'] = record['task_type']
        if record['metadata']:
            document.update(json.loads(record['metadata']))
        return document

    def _ensure_writer(self) -> None:
        if self._writer is not None:
            return

        output_dir = os.path.dirname(os.path.abspath(self.output_path))
        prefix = f'.{os.path.basename(self.output_path)}.'
        temporary_file = tempfile.NamedTemporaryFile(
            prefix=prefix,
            suffix='.tmp',
            dir=output_dir,
            delete=False
        )
        self._temporary_path = temporary_file.name
        temporary_file.close()

        self._writer = pq.ParquetWriter(
            self._temporary_path,
            self.SCHEMA,
            compression='zstd'
        )

        try:
            if os.path.exists(self.output_path):
                existing_file = pq.ParquetFile(self.output_path)
                if existing_file.schema_arrow != self.SCHEMA:
                    raise ValueError(
                        f'Existing Parquet schema is incompatible: '
                        f'{self.output_path}'
                    )
                for batch in existing_file.iter_batches():
                    self._writer.write_batch(batch)
        except Exception:
            self._writer.close()
            self._writer = None
            os.remove(self._temporary_path)
            self._temporary_path = None
            raise

    def insert_one(self, document: dict) -> None:
        self.insert_many([document])

    def insert_many(self, data: list) -> None:
        if not data:
            return

        self._ensure_writer()
        records = [self._to_record(document) for document in data]
        table = pa.Table.from_pylist(records, schema=self.SCHEMA)
        self._writer.write_table(table)

    def finalize(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None

        if self._temporary_path is not None:
            os.replace(self._temporary_path, self.output_path)
            self._temporary_path = None

    def get_collected_uuids(self) -> list:
        self.finalize()
        if not os.path.exists(self.output_path):
            return []
        table = pq.read_table(self.output_path, columns=['uuid'])
        return [uuid for uuid in table.column('uuid').to_pylist() if uuid]

    def get_documents(self) -> list:
        self.finalize()
        if not os.path.exists(self.output_path):
            return []
        return [
            self._to_document(record)
            for record in pq.read_table(self.output_path).to_pylist()
        ]

    def test_access(self) -> bool:
        output_dir = os.path.dirname(os.path.abspath(self.output_path))
        return os.path.isdir(output_dir) and os.access(output_dir, os.W_OK)

    def close(self) -> None:
        self.finalize()

    def abort(self) -> None:
        """Discard unpublished staging without retrying a failed replacement."""
        try:
            if self._writer is not None:
                self._writer.close()
        finally:
            self._writer = None
            if self._temporary_path is not None:
                os.remove(self._temporary_path)
                self._temporary_path = None

    def iter_documents(self, *, fields=None, limits=None):
        from narrative_blueprint.corpus.contracts import FIELDS
        from narrative_blueprint.corpus.sources import local_documents
        if self._writer is not None or self._temporary_path is not None:
            raise RuntimeError('Finalize pending writes explicitly before reading')
        return local_documents(self.output_path, fields=FIELDS if fields is None else fields, limits=limits)
