# -*- coding: utf-8 -*-

# import argparse
from argparse import (
	ArgumentParser, SUPPRESS
)

# import argparse formatter
from utils.argparse_formatter import CustomHelpFormatter
from cli.analysis_options import ANALYSIS_EPILOG, add_analysis_options

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
        epilog=ANALYSIS_EPILOG,
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
        default=None,
        metavar='',
        help=(
            "Embedding model to use. Available options: "
            "OpenAI 'text-embedding-3-small', 'text-embedding-3-large', "
            "'text-embedding-ada-002', and Gemini 'gemini-embedding-001'. "
            "Compute default: text-embedding-3-small"
        )
    )

    embeddings_arguments.add_argument(
        '--narrative-path',
        type=str,
        required=False,
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
        metavar='DIRECTORY',
        help=(
            'Directory where embedding analysis results will be saved. '
            'Required unless --skip-analysis is used; no default. '
            'With --analysis-only, must be a new directory (example: results/diagnostic-01)'
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
        metavar='SCORE',
        help='Cosine similarity threshold; default 0.75. Analysis-only requires a finite score in (0, 1]'
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

    add_analysis_options(embeddings_parser)
    return embeddings_parser
