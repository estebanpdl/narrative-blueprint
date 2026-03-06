# -*- coding: utf-8 -*-

# import argparse
from argparse import (
	ArgumentParser, SUPPRESS
)

# import argparse formatter
from utils.argparse_formatter import CustomHelpFormatter

# create blueprint parser
def create_blueprint_parser(subparsers: ArgumentParser) -> ArgumentParser:
    '''
    Create blueprint parser

    :param subparsers: The subparsers to be used for the blueprint parser.
    :type subparsers: ArgumentParser

    :return: The blueprint parser.
    :rtype: ArgumentParser
    '''
    # blueprint parser
    blueprint_parser = subparsers.add_parser(
        'blueprint',
        help='Generate structured narrative blueprints for disinformation analysis',
        formatter_class=CustomHelpFormatter,
        add_help=False
    )

    # help options
    blueprint_help = blueprint_parser.add_argument_group('Options')
    blueprint_help.add_argument(
        '-h',
        '--help',
        action='help',
        default=SUPPRESS,
        help='Show blueprint command help'
    )

    # blueprint arguments
    blueprint_arguments = blueprint_parser.add_argument_group(
        'Blueprint arguments'
    )

    blueprint_arguments.add_argument(
        '--model',
        type=str,
        default='gpt-4o-mini',
        metavar='',
        help='OpenAI/Google model to use for blueprint generation'
    )

    blueprint_arguments.add_argument(
        '--prompt-template',
        type=str,
        required=True,
        metavar='',
        help=(
            "Path to a TOML file containing custom system and message prompts. "
            "The TOML file should contain '[system]' and "
            "'[message]' sections, each with a 'prompt' field. "
        )
    )

    blueprint_arguments.add_argument(
        '--narrative-path',
        type=str,
        required=True,
        metavar='',
        help=(
            "Path to the narrative file. File can be CSV, XLSX, or JSON. "
            "If CSV or XLSX, file must contain the following columns: `uuid`, `narrative`. "
            "If JSON, file must contain the following structure: "
            "`{'uuid': '...', 'narrative': '...'}`"
        )
    )

    blueprint_arguments.add_argument(
        '--sample-size',
        type=int,
        metavar='',
        default=None,
        help='Number of narratives to process for blueprint generation'
    )

    # output arguments
    output_arguments = blueprint_parser.add_argument_group(
        'Output arguments'
    )

    output_arguments.add_argument(
        '--output',
        type=str,
        metavar='',
        default=None,
        help='Path to a JSON file for storing results (alternative to MongoDB)'
    )

    # blueprint MongoDB arguments
    blueprint_mongodb_arguments = blueprint_parser.add_argument_group(
        'Blueprint MongoDB arguments'
    )

    blueprint_mongodb_arguments.add_argument(
        '--mongo-db-name',
        type=str,
        default=None,
        metavar='',
        help='Name of the MongoDB database to store the blueprint'
    )

    blueprint_mongodb_arguments.add_argument(
        '--mongo-collection-name',
        type=str,
        default=None,
        metavar='',
        help='Name of the MongoDB collection to store the blueprint'
    )

    return blueprint_parser
