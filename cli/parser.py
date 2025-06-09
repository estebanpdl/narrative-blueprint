# -*- coding: utf-8 -*-

# import argparse
from argparse import (
	ArgumentParser, SUPPRESS
)

# import argparse formatter
from utils.argparse_formatter import CustomHelpFormatter

# command parsers
from cli.blueprint_parser import create_blueprint_parser

# create main parser
def create_main_parser():
    '''
    Create a main parser
    '''
    parser = ArgumentParser(
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

    # integrate blueprint parser directly
    create_blueprint_parser(parser)

    return parser

# create and export parser
parser = create_main_parser()
