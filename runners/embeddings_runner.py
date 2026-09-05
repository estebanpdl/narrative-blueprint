# -*- coding: utf-8 -*-

import os

# embeddings
from embeddings import OpenAIEmbeddingModel, GeminiEmbeddingModel

# storage backends
from databases import (
    CSVFileManager,
    MongoDBManager,
    ParquetFileManager,
    SQLiteManager
)

# import embedding analysis
from analysis import EmbeddingAnalysis


def _get_embedding_storage(args: dict):
    '''Select and initialize the requested embedding storage backend.'''
    embeddings_output = args.get('embeddings_output')
    mongo_db_name = args.get('mongo_db_name')
    mongo_collection_name = args.get('mongo_collection_name')

    if embeddings_output:
        if mongo_db_name or mongo_collection_name:
            raise ValueError(
                '--embeddings-output cannot be combined with MongoDB arguments'
            )

        extension = os.path.splitext(embeddings_output)[1].lower()
        if extension == '.csv':
            return CSVFileManager(output_path=embeddings_output)
        if extension == '.parquet':
            return ParquetFileManager(output_path=embeddings_output)
        if extension in {'.db', '.sqlite', '.sqlite3'}:
            return SQLiteManager(output_path=embeddings_output)
        raise ValueError(
            '--embeddings-output must use .csv, .parquet, .db, .sqlite, '
            'or .sqlite3'
        )

    if not mongo_db_name or not mongo_collection_name:
        raise ValueError(
            '--mongo-db-name and --mongo-collection-name are required when '
            '--embeddings-output is not provided'
        )

    return MongoDBManager(
        db_name=mongo_db_name,
        collection_name=mongo_collection_name
    )

# handle embeddings
def handle_embeddings(args: dict) -> None:
    '''
    Handle the embeddings command.

    :param args: The arguments to be passed to the embeddings command.
    :type args: dict

    :return: None
    :rtype: None
    '''
    embedding_model_map = {
        'gemini-embedding-001': 'Gemini',
        'text-embedding-ada-002': 'OpenAI',
        'text-embedding-3-small': 'OpenAI',
        'text-embedding-3-large': 'OpenAI'
    }

    # dispatch map for embedding models
    embedding_model_classes = {
        'Gemini': GeminiEmbeddingModel,
        'OpenAI': OpenAIEmbeddingModel,
    }

    # get model name
    model = args['model']
    provider = embedding_model_map.get(model)
    if not provider:
        raise ValueError(f'Unsupported embedding model: {model}')

    if not args.get('skip_analysis') and not args.get('output'):
        raise ValueError('--output is required unless --skip-analysis is used')

    gemini_task_type = args.get('gemini_task_type')
    if model != 'gemini-embedding-001' and gemini_task_type:
        raise ValueError(
            '--gemini-task-type can only be used with gemini-embedding-001'
        )

    storage = _get_embedding_storage(args)

    # select and instantiate embedding model
    model_class = embedding_model_classes[provider]
    model_options = {'model_name': model}
    if model == 'gemini-embedding-001':
        model_options['task_type'] = (
            gemini_task_type or 'SEMANTIC_SIMILARITY'
        )
    vector_model = model_class(**model_options)

    # embedding analysis
    embedding_analysis = EmbeddingAnalysis(
        vector_model=vector_model,
        storage=storage,
        args=args
    )

    # run embedding analysis
    print(f'Computing embeddings using {provider} {model}...')
    embedding_analysis.run_embedding_analysis()
