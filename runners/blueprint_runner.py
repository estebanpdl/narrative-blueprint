# -*- coding: utf-8 -*-

# language models
from models import get_llm_engine

# import blueprint
from narrative_blueprint import NarrativeBlueprint

# handle blueprint
def handle_blueprint(args: dict) -> None:
    '''
    Handle the blueprint command.

    :param args: The arguments to be passed to the blueprint command.
    :type args: dict

    :return: None
    :rtype: None
    '''
    model = args['model']

    # llm engine
    llm_engine = get_llm_engine(model_name=model)

    # blueprint
    blueprint = NarrativeBlueprint(
        llm_engine=llm_engine,
        args=args
    )

    # run blueprint
    blueprint.run_blueprint_analysis()
