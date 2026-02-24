# -*- coding: utf-8 -*-

# language models
from models import get_llm_engine

# storage backends
from databases import MongoDBManager, JSONFileManager

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

    # select storage backend
    output_path = args.get('output')
    if output_path:
        storage = JSONFileManager(output_path=output_path)
    else:
        mongo_db_name = args.get('mongo_db_name')
        mongo_collection_name = args.get('mongo_collection_name')

        if not mongo_db_name or not mongo_collection_name:
            raise ValueError(
                '--mongo-db-name and --mongo-collection-name are required '
                'when --output is not provided'
            )

        storage = MongoDBManager(
            db_name=mongo_db_name,
            collection_name=mongo_collection_name
        )

    # blueprint
    blueprint = NarrativeBlueprint(
        llm_engine=llm_engine,
        storage=storage,
        args=args
    )

    # run blueprint
    blueprint.run_blueprint_analysis()
