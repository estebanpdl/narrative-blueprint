# -*- coding: utf-8 -*-

import os
import tempfile
import unittest
from unittest.mock import Mock

from narrative_blueprint.analysis.embedding_analysis import EmbeddingAnalysis
from narrative_blueprint.cli.parser import create_main_parser
from narrative_blueprint.databases import CSVFileManager, ParquetFileManager, SQLiteManager
from narrative_blueprint.embeddings.base import VectorModel
from narrative_blueprint.embeddings.gemini_embeddings import GeminiEmbeddingModel
from narrative_blueprint.runners.embeddings_runner import _get_embedding_storage, handle_embeddings


class FakeVectorModel(VectorModel):
    def estimate_tokens(self, text: str) -> int:
        return len(text)

    def _safe_embed_request(self, uuids, batch_data, request_id,
                            retry_max=3) -> None:
        return

    def compute_embeddings(self, uuids, data, storage) -> None:
        storage.insert_many([
            {
                'uuid': uuid,
                'text': text,
                'embedding': [float(index), 1.0],
                'model_name': 'fake-model',
                'provider': 'Fake'
            }
            for index, (uuid, text) in enumerate(zip(uuids, data))
        ])


class EmbeddingStorageTests(unittest.TestCase):
    DOCUMENTS = [
        {
            'uuid': 'one',
            'text': 'First narrative',
            'embedding': [0.1, 0.2, 0.3],
            'model_name': 'gemini-embedding-001',
            'provider': 'Google',
            'task_type': 'CLUSTERING'
        },
        {
            'uuid': 'two',
            'text': 'Second, narrative',
            'embedding': [0.4, 0.5, 0.6],
            'model_name': 'gemini-embedding-001',
            'provider': 'Google',
            'task_type': 'CLUSTERING'
        }
    ]

    def test_csv_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'embeddings.csv')
            storage = CSVFileManager(path)
            storage.insert_one(self.DOCUMENTS[0])
            storage.insert_one(self.DOCUMENTS[1])

            reopened = CSVFileManager(path)
            self.assertEqual(reopened.get_documents(), self.DOCUMENTS)
            self.assertEqual(reopened.get_collected_uuids(), ['one', 'two'])

    def test_sqlite_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'embeddings.sqlite')
            storage = SQLiteManager(path)
            storage.insert_many(self.DOCUMENTS)
            storage.close()

            reopened = SQLiteManager(path)
            self.assertEqual(reopened.get_documents(), self.DOCUMENTS)
            self.assertEqual(reopened.get_collected_uuids(), ['one', 'two'])
            reopened.close()

    def test_parquet_round_trip_and_append(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'embeddings.parquet')
            storage = ParquetFileManager(path)
            storage.insert_one(self.DOCUMENTS[0])
            storage.finalize()

            appended = ParquetFileManager(path)
            appended.insert_one(self.DOCUMENTS[1])
            appended.finalize()

            reopened = ParquetFileManager(path)
            self.assertEqual(reopened.get_documents(), self.DOCUMENTS)
            self.assertEqual(reopened.get_collected_uuids(), ['one', 'two'])

    def test_skip_analysis_only_stores_embeddings(self):
        with tempfile.TemporaryDirectory() as directory:
            narratives_path = os.path.join(directory, 'narratives.csv')
            embeddings_path = os.path.join(directory, 'embeddings.csv')
            with open(narratives_path, 'w', encoding='utf-8') as file:
                file.write('uuid,narrative\none,First narrative\n')

            storage = CSVFileManager(embeddings_path)
            analysis = EmbeddingAnalysis(
                vector_model=FakeVectorModel(),
                storage=storage,
                args={
                    'narrative_path': narratives_path,
                    'output': None,
                    'skip_analysis': True,
                    'threshold': 0.75
                }
            )
            analysis.run_embedding_analysis()

            self.assertEqual(len(storage.get_documents()), 1)
            self.assertFalse(os.path.exists(os.path.join(directory, '_tensor.tsv')))

    def test_skip_analysis_finalizes_parquet(self):
        with tempfile.TemporaryDirectory() as directory:
            narratives_path = os.path.join(directory, 'narratives.csv')
            embeddings_path = os.path.join(directory, 'embeddings.parquet')
            with open(narratives_path, 'w', encoding='utf-8') as file:
                file.write('uuid,narrative\none,First narrative\n')

            storage = ParquetFileManager(embeddings_path)
            analysis = EmbeddingAnalysis(
                vector_model=FakeVectorModel(),
                storage=storage,
                args={
                    'narrative_path': narratives_path,
                    'output': None,
                    'skip_analysis': True,
                    'threshold': 0.75
                }
            )
            analysis.run_embedding_analysis()

            self.assertTrue(os.path.exists(embeddings_path))
            self.assertEqual(len(storage.get_documents()), 1)


class EmbeddingsParserTests(unittest.TestCase):
    def test_local_storage_and_skip_analysis_arguments(self):
        args = create_main_parser().parse_args([
            'embeddings',
            '--model', 'gemini-embedding-001',
            '--narrative-path', 'narratives.csv',
            '--embeddings-output', 'embeddings.sqlite',
            '--skip-analysis',
            '--gemini-task-type', 'clustering'
        ])

        self.assertEqual(args.embeddings_output, 'embeddings.sqlite')
        self.assertTrue(args.skip_analysis)
        self.assertIsNone(args.output)
        self.assertEqual(args.gemini_task_type, 'CLUSTERING')

    def test_storage_backend_is_selected_by_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_storage = _get_embedding_storage({
                'embeddings_output': os.path.join(directory, 'vectors.csv'),
                'mongo_db_name': None,
                'mongo_collection_name': None
            })
            sqlite_storage = _get_embedding_storage({
                'embeddings_output': os.path.join(directory, 'vectors.db'),
                'mongo_db_name': None,
                'mongo_collection_name': None
            })
            parquet_storage = _get_embedding_storage({
                'embeddings_output': os.path.join(directory, 'vectors.parquet'),
                'mongo_db_name': None,
                'mongo_collection_name': None
            })

            self.assertIsInstance(csv_storage, CSVFileManager)
            self.assertIsInstance(sqlite_storage, SQLiteManager)
            self.assertIsInstance(parquet_storage, ParquetFileManager)
            sqlite_storage.close()

    def test_gemini_task_type_is_rejected_for_openai(self):
        with self.assertRaisesRegex(ValueError, 'gemini-embedding-001'):
            handle_embeddings({
                'model': 'text-embedding-3-small',
                'narrative_path': 'unused.csv',
                'output': None,
                'skip_analysis': True,
                'threshold': 0.75,
                'gemini_task_type': 'CLUSTERING',
                'embeddings_output': 'unused.csv',
                'mongo_db_name': None,
                'mongo_collection_name': None
            })


class GeminiTaskTypeTests(unittest.TestCase):
    def test_task_type_is_sent_and_stored(self):
        model = GeminiEmbeddingModel.__new__(GeminiEmbeddingModel)
        VectorModel.__init__(model)
        model.model_name = 'gemini-embedding-001'
        model.task_type = 'FACT_VERIFICATION'
        model.storage = Mock()
        embedding = Mock()
        embedding.values = [0.1, 0.2]
        response = Mock()
        response.embeddings = [embedding]
        model.client = Mock()
        model.client.models.embed_content.return_value = response

        model._safe_embed_request(
            uuids=['one'],
            batch_data=['Claim to verify'],
            request_id=1
        )

        config = model.client.models.embed_content.call_args.kwargs['config']
        self.assertEqual(config.task_type, 'FACT_VERIFICATION')
        stored = model.storage.insert_many.call_args.args[0]
        self.assertEqual(stored[0]['task_type'], 'FACT_VERIFICATION')


if __name__ == '__main__':
    unittest.main()
