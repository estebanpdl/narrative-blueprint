# -*- coding: utf-8 -*-

# import argparse
from argparse import (
	ArgumentParser, SUPPRESS
)

# import argparse formatter
from utils.argparse_formatter import CustomHelpFormatter

# create embeddings parser
def create_embeddings_parser(subparsers: ArgumentParser) -> ArgumentParser:
    '''
    Create an embeddings parser

    :param subparsers: The subparsers to be used for the embeddings parser.
    :type subparsers: ArgumentParser

    :return: The embeddings parser.
    :rtype: ArgumentParser
    '''
    # embeddings parser
    embeddings_parser = subparsers.add_parser(
        'embeddings',
        help='Compute embeddings and run similarity analysis on narratives',
        formatter_class=CustomHelpFormatter,
        add_help=False
    )

    # help options
    embeddings_help = embeddings_parser.add_argument_group('Options')
    embeddings_help.add_argument(
        '-h',
        '--help',
        action='help',
        default=SUPPRESS,
        help='Show embeddings command help'
    )

    # embeddings arguments
    embeddings_arguments = embeddings_parser.add_argument_group(
        'Embeddings arguments'
    )

    embeddings_arguments.add_argument(
        '--model',
        type=str,
        choices=[
            'text-embedding-3-small', 'text-embedding-3-large',
            'text-embedding-ada-002', 'gemini-embedding-001'
        ],
        default='text-embedding-3-small',
        metavar='',
        help=(
            "Embedding model to use. Available options: "
            "OpenAI 'text-embedding-3-small', 'text-embedding-3-large', "
            "'text-embedding-ada-002', and Gemini 'gemini-embedding-001'"
        )
    )

    embeddings_arguments.add_argument(
        '--narrative-path',
        type=str,
        required=True,
        metavar='',
        help=(
            "Path to the narrative file. File can be CSV, XLSX, or JSON. "
            "Must contain the following columns/keys: `uuid`, `narrative`."
        )
    )

    embeddings_arguments.add_argument(
        '-o',
        '--output',
        type=str,
        default=None,
        metavar='',
        help=(
            'Directory where embedding analysis results will be saved. '
            'Required unless --skip-analysis is used'
        )
    )

    embeddings_arguments.add_argument(
        '--skip-analysis',
        action='store_true',
        help=(
            'Compute and store embeddings without generating projector or '
            'similarity-analysis files'
        )
    )

    embeddings_arguments.add_argument(
        '--threshold',
        type=float,
        default=0.75,
        metavar='',
        help='Threshold for the similarity analysis'
    )

    embeddings_arguments.add_argument(
        '--gemini-task-type',
        type=str.upper,
        choices=[
            'SEMANTIC_SIMILARITY', 'CLASSIFICATION', 'CLUSTERING',
            'RETRIEVAL_DOCUMENT', 'RETRIEVAL_QUERY',
            'CODE_RETRIEVAL_QUERY', 'QUESTION_ANSWERING',
            'FACT_VERIFICATION'
        ],
        default=None,
        metavar='',
        help=(
            'Task type for gemini-embedding-001 only. Defaults to '
            'SEMANTIC_SIMILARITY'
        )
    )

    # local embedding storage arguments
    embeddings_storage_arguments = embeddings_parser.add_argument_group(
        'Local embedding storage arguments'
    )

    embeddings_storage_arguments.add_argument(
        '--embeddings-output',
        '--embedding-output',
        dest='embeddings_output',
        type=str,
        default=None,
        metavar='',
        help=(
            'Path to store embeddings locally. Supported extensions: '
            '.csv, .parquet, .db, .sqlite, .sqlite3. Alternative to MongoDB'
        )
    )

    # embeddings MongoDB arguments
    embeddings_mongodb_arguments = embeddings_parser.add_argument_group(
        'Embeddings MongoDB arguments'
    )

    embeddings_mongodb_arguments.add_argument(
        '--mongo-db-name',
        type=str,
        default=None,
        metavar='',
        help='Name of the MongoDB database to store the embeddings'
    )

    embeddings_mongodb_arguments.add_argument(
        '--mongo-collection-name',
        type=str,
        default=None,
        metavar='',
        help='Name of the MongoDB collection to store the embeddings'
    )

    return embeddings_parser
