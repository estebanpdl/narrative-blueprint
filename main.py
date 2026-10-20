# -*- coding: utf-8 -*-

# import modules
import time

# import key arguments
from cli import parser

def main(argv=None):
    # parse arguments
    args = vars(parser.parse_args(argv))

    # start process
    log_text = f'''
    > Starting program at: {time.ctime()}

    '''
    print ('\n\n' + ' '.join(log_text.split()).strip() + '\n\n')

    # command dispatcher
    command = args.pop('command')
    try:
        if command == 'embeddings':
            from runners.embeddings_runner import handle_embeddings
            handle_embeddings(args)
        else:
            from runners.blueprint_runner import handle_blueprint
            handle_blueprint(args)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))

    # end process
    log_text = f'''
    > Ending program at: {time.ctime()}

    '''
    print ('\n\n' + ' '.join(log_text.split()).strip())

if __name__ == '__main__':
    main()
