# -*- coding: utf-8 -*-

# import modules
import time

# import key arguments
from cli import parser

# import blueprint runner
from runners.blueprint_runner import handle_blueprint

def main():
    # parse arguments
    args = vars(parser.parse_args())

    # start process
    log_text = f'''
    > Starting program at: {time.ctime()}

    '''
    print ('\n\n' + ' '.join(log_text.split()).strip() + '\n\n')

    # process blueprint arguments directly
    handle_blueprint(args)

    # end process
    log_text = f'''
    > Ending program at: {time.ctime()}

    '''
    print ('\n\n' + ' '.join(log_text.split()).strip())

if __name__ == '__main__':
    main()
