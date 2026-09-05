# -*- coding: utf-8 -*-

import json
import os
import sqlite3
import threading

from .database import Database


class SQLiteManager(Database):
    '''Store embedding documents in a local SQLite database.'''

    def __init__(self, output_path: str):
        self.output_path = output_path
        self._lock = threading.Lock()

        output_dir = os.path.dirname(os.path.abspath(self.output_path))
        os.makedirs(output_dir, exist_ok=True)

        self.connection = sqlite3.connect(
            self.output_path,
            check_same_thread=False
        )
        self.connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT,
                text TEXT,
                embedding TEXT NOT NULL,
                model_name TEXT,
                provider TEXT,
                task_type TEXT,
                metadata TEXT
            )
            '''
        )
        self.connection.commit()

    @staticmethod
    def _to_row(document: dict) -> tuple:
        core_fields = {
            'uuid', 'text', 'embedding', 'model_name', 'provider', 'task_type'
        }
        metadata = {
            key: value for key, value in document.items()
            if key not in core_fields
        }
        return (
            str(document['uuid']) if document.get('uuid') is not None else None,
            document.get('text'),
            json.dumps(document['embedding'], separators=(',', ':')),
            document.get('model_name'),
            document.get('provider'),
            document.get('task_type'),
            json.dumps(metadata, ensure_ascii=False) if metadata else None
        )

    @staticmethod
    def _to_document(row: sqlite3.Row) -> dict:
        document = {
            'uuid': row['uuid'],
            'text': row['text'],
            'embedding': json.loads(row['embedding']),
            'model_name': row['model_name'],
            'provider': row['provider']
        }
        if row['task_type'] is not None:
            document['task_type'] = row['task_type']
        if row['metadata']:
            document.update(json.loads(row['metadata']))
        return document

    def insert_one(self, document: dict) -> None:
        self.insert_many([document])

    def insert_many(self, data: list) -> None:
        if not data:
            return

        rows = [self._to_row(document) for document in data]
        with self._lock:
            self.connection.executemany(
                '''
                INSERT INTO embeddings (
                    uuid, text, embedding, model_name, provider,
                    task_type, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                rows
            )
            self.connection.commit()

    def get_collected_uuids(self) -> list:
        cursor = self.connection.execute(
            'SELECT uuid FROM embeddings WHERE uuid IS NOT NULL ORDER BY id'
        )
        return [row[0] for row in cursor.fetchall()]

    def get_documents(self) -> list:
        self.connection.row_factory = sqlite3.Row
        cursor = self.connection.execute(
            '''
            SELECT uuid, text, embedding, model_name, provider,
                   task_type, metadata
            FROM embeddings
            ORDER BY id
            '''
        )
        return [self._to_document(row) for row in cursor.fetchall()]

    def test_access(self) -> bool:
        try:
            self.connection.execute('SELECT 1').fetchone()
            return True
        except sqlite3.Error:
            return False

    def close(self) -> None:
        self.connection.close()
