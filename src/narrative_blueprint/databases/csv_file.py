# -*- coding: utf-8 -*-

import csv
import json
import os
import threading

from .database import Database


class CSVFileManager(Database):
    '''Store embedding documents in a CSV file.'''

    PREFERRED_FIELDS = [
        'uuid', 'text', 'embedding', 'model_name', 'provider', 'task_type'
    ]

    def __init__(self, output_path: str):
        self.output_path = output_path
        self._lock = threading.Lock()
        self._fieldnames = []

        output_dir = os.path.dirname(os.path.abspath(self.output_path))
        os.makedirs(output_dir, exist_ok=True)

        if (
            os.path.exists(self.output_path)
            and os.path.getsize(self.output_path) > 0
        ):
            with open(self.output_path, 'r', encoding='utf-8', newline='') as file:
                reader = csv.DictReader(file)
                self._fieldnames = reader.fieldnames or []

    @staticmethod
    def _serialize(document: dict) -> dict:
        serialized = dict(document)
        if 'embedding' in serialized:
            serialized['embedding'] = json.dumps(
                serialized['embedding'], separators=(',', ':')
            )
        return serialized

    @staticmethod
    def _deserialize(document: dict) -> dict:
        deserialized = dict(document)
        embedding = deserialized.get('embedding')
        if embedding:
            deserialized['embedding'] = json.loads(embedding)
        return deserialized

    def _ordered_fieldnames(self, data: list[dict]) -> list[str]:
        fields = set(self._fieldnames)
        for document in data:
            fields.update(document.keys())

        preferred = [field for field in self.PREFERRED_FIELDS if field in fields]
        remaining = sorted(fields.difference(preferred))
        return preferred + remaining

    def _read_documents(self) -> list[dict]:
        if (
            not os.path.exists(self.output_path)
            or os.path.getsize(self.output_path) == 0
        ):
            return []
        with open(self.output_path, 'r', encoding='utf-8', newline='') as file:
            return [self._deserialize(row) for row in csv.DictReader(file)]

    def _rewrite(self, documents: list[dict]) -> None:
        with open(self.output_path, 'w', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=self._fieldnames)
            writer.writeheader()
            writer.writerows(self._serialize(item) for item in documents)

    def insert_one(self, document: dict) -> None:
        self.insert_many([document])

    def insert_many(self, data: list) -> None:
        if not data:
            return

        with self._lock:
            new_fieldnames = self._ordered_fieldnames(data)
            fieldnames_changed = new_fieldnames != self._fieldnames
            file_exists = (
                os.path.exists(self.output_path)
                and os.path.getsize(self.output_path) > 0
            )

            self._fieldnames = new_fieldnames

            if fieldnames_changed or not file_exists:
                existing_documents = self._read_documents() if file_exists else []
                self._rewrite(existing_documents + list(data))
                return

            with open(self.output_path, 'a', encoding='utf-8', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=self._fieldnames)
                writer.writerows(self._serialize(item) for item in data)

    def get_collected_uuids(self) -> list:
        if (
            not os.path.exists(self.output_path)
            or os.path.getsize(self.output_path) == 0
        ):
            return []
        with open(self.output_path, 'r', encoding='utf-8', newline='') as file:
            return [
                row['uuid'] for row in csv.DictReader(file)
                if row.get('uuid')
            ]

    def get_documents(self) -> list:
        return self._read_documents()

    def iter_documents(self, *, fields=None, limits=None):
        from narrative_blueprint.corpus.contracts import FIELDS
        from narrative_blueprint.corpus.sources import local_documents
        return local_documents(self.output_path, fields=FIELDS if fields is None else fields, limits=limits)

    def test_access(self) -> bool:
        output_dir = os.path.dirname(os.path.abspath(self.output_path))
        return os.path.isdir(output_dir) and os.access(output_dir, os.W_OK)
