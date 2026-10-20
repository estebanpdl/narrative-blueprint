# -*- coding: utf-8 -*-

# import argparse
from argparse import SUPPRESS

# import argparse formatter
from utils.argparse_formatter import CustomHelpFormatter

# command parsers
from cli.blueprint_parser import create_blueprint_parser
from cli.embeddings_parser import create_embeddings_parser
from cli.analysis_options import DiagnosticArgumentParser

# create main parser
def create_main_parser():
    '''
    Create a main parser
    '''
    parser = DiagnosticArgumentParser(
        prog='python main.py',
        description='Narrative Blueprint Analysis',
        formatter_class=CustomHelpFormatter,
        add_help=False
    )

    # help arguments
    help_arguments = parser.add_argument_group('Help options')
    help_arguments.add_argument(
        '-h',
        '--help',
        action='help',
        default=SUPPRESS,
        help='Show this help message and exit'
    )

    # subparsers container
    subparsers = parser.add_subparsers(
        title='Available commands',
        metavar='',
        dest='command'
    )

    # required subparsers
    subparsers.required = True

    # integrate parsers
    create_blueprint_parser(subparsers)
    create_embeddings_parser(subparsers)

    return parser

# create and export parser
parser = create_main_parser()
