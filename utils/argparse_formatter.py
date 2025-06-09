# -*- coding: utf-8 -*-

# import modules
import textwrap

# argparse formatter
from argparse import RawDescriptionHelpFormatter
from argparse import _SubParsersAction

class CustomHelpFormatter(RawDescriptionHelpFormatter):
    '''
    Custom formatter for argparse help output.
    
    Extends RawDescriptionHelpFormatter to preserve formatting in help text
    while improving subcommand display.
    '''
    def __init__(self, prog, indent_increment=2, max_help_position=40, width=120):
        super().__init__(prog, indent_increment, max_help_position, width)
    
    def _format_action(self, action):
        if isinstance(action, _SubParsersAction):
            # get the subaction help strings
            subactions = list(action._get_subactions())

            # format the help for each subcommand
            parts = []
            for subaction in subactions:
                # build the complete help string with proper formatting
                cmd = f"  {subaction.metavar or subaction.dest:<20} {subaction.help or ''}"
                parts.append(cmd)
            
            # join all parts with newlines
            return "\n".join(parts)
        return super()._format_action(action)

    def _split_lines(self, text, width):
        '''
        Wrap text while preserving manual newlines.
        '''
        if '\n' in text:
            return text.splitlines()
        
        return textwrap.wrap(text, width)
        
    def _format_usage(self, usage, actions, groups, prefix):
        '''
        Format the usage string to ensure compatibility with argparse expectations.
        This fixes issues with the assertion error in argparse's _format_usage method.
        '''
        if prefix is None:
            prefix = 'usage: '
        
        if usage is None:
            usage = '%(prog)s' % dict(prog=self._prog)
            
        # if usage is just default, calculate usage from actions
        actions_by_positionals = []
        actions_by_optionals = []
        for action in actions:
            if action.option_strings:
                actions_by_optionals.append(action)
            else:
                actions_by_positionals.append(action)
                
        # format positional arguments as positional
        format_string = self._format_actions_usage(actions_by_positionals, groups)
        if format_string:
            usage = ' '.join([usage, format_string])
            
        # format optional arguments as optionals
        format_string = self._format_actions_usage(actions_by_optionals, groups)
        if format_string:
            opt_usage = format_string.replace(',', ' ')
            usage = ' '.join([usage, '[%s]' % opt_usage])
            
        # wrap the usage parts if needed
        return '%s%s\n\n' % (prefix, usage)
