# -*- coding: utf-8 -*-

# import modules
import os
import json
import tomli
import string
import pandas as pd

# import LLM base class
from models import LanguageModel

# MongoDB connection
from databases import MongoDBManager

# MongoDB errors
from pymongo.errors import ConnectionFailure

# Narrative blueprint class
class NarrativeBlueprint:
    '''
    Narrative blueprint class
    '''
    def __init__(self, llm_engine: LanguageModel, args: dict = None):
        '''
        Initialize the Narrative Blueprint engine.
        
        :param llm_engine: The LLM engine to be used for narrative blueprint
            processing. Must be a subclass of `LanguageModel`.

            Available options:
            - OpenAIGPT: models/openai_client.py
        
        :type llm_engine: LanguageModel

        :raises TypeError: If the provided `llm_engine` is not a subclass
            of `LanguageModel`.

        :param args: Additional arguments to be passed to the Narrative Blueprint framework.
        :type args: dict

        Example:
            >>> from models.openai_client import OpenAIGPT
            >>> llm_engine = OpenAIGPT(model="gpt-4o-mini")
            >>> blueprint = NarrativeBlueprint(llm_engine=llm_engine)
        '''
        # get arguments
        args = args or {}
        self.args = args

        # LLM engine
        if not isinstance(llm_engine, LanguageModel):
            raise TypeError('llm_engine must be an instance of LanguageModel')
        
        self.llm_engine = llm_engine

        # MongoDB manager
        self.mongodb_manager = MongoDBManager()
        self.mongo_db_name = self.args.get('mongo_db_name')
        self.mongo_collection_name = self.args.get('mongo_collection_name')

        # load narratives
        narrative_path = self.args.get('narrative_path')
        if not narrative_path:
            raise ValueError('The `narrative_path` argument is required')
        
        self.narratives = self._load_narratives(narrative_path)

        # check required columns in narratives dataset
        required_columns = ['uuid', 'narrative']
        missing_columns = [
            col for col in required_columns
            if col not in self.narratives.columns
        ]
        if missing_columns:
            raise ValueError(
                f'Narratives dataset missing required columns: {missing_columns}'
            )
        
        # sample size from args
        self.sample_size = self.args.get('sample_size', None)

    def _load_system_prompt(self, template_path: str) -> str:
        '''
        Load the system prompt from a template file.

        :param template_path: The path to the TOML template file.
        :type template_path: str

        :return: The system prompt.
        :rtype: str
        '''
        # load prompts
        with open(template_path, 'rb') as file:
            prompts = tomli.load(file)
        
        # get the system prompt
        return prompts.get('system')['prompt']
    
    def _load_message_prompt(self, template_path: str, narrative: str = None) -> str:
        '''
        Load the message prompt from a template file.

        :param template_path: The path to the TOML template file.
        :type template_path: str

        :param narrative: The narrative to be used in the message prompt.
        :type narrative: str

        :return: The message prompt.
        :rtype: str
        '''
        # load prompts
        with open(template_path, 'rb') as file:
            prompts = tomli.load(file)
        
        # get the message prompt
        message_prompt = prompts.get('message')['prompt']

        # substitute the narrative into the message prompt
        return string.Template(message_prompt).substitute(
            narrative=narrative
        )
    
    def _load_narratives(self, path: str = None) -> pd.DataFrame:
        '''
        Load the narratives from a CSV, XLSX, or JSON file.

        :param path: The path to the file containing the narratives.
            Supported formats: CSV, XLSX, JSON
        :type path: str

        :return: A pandas DataFrame containing the narratives.
        :rtype: pd.DataFrame
        '''
        try:
            # get file extension
            file_extension = os.path.splitext(path)[1].lower()
            
            if file_extension == '.csv':
                return pd.read_csv(path, encoding='utf-8', low_memory=False)
            
            elif file_extension in ['.xlsx', '.xls']:
                return pd.read_excel(path)
            
            elif file_extension == '.json':
                with open(path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                
                # handle different JSON structures
                if isinstance(data, list):
                    # e.g., [{'uuid': '...', 'narrative': '...'}, ...]
                    return pd.DataFrame(data)
                elif isinstance(data, dict):
                    # e.g., {'uuid': '...', 'narrative': '...'}
                    return pd.DataFrame([data])
                else:
                    raise ValueError(f'Unsupported JSON structure in {path}')
            
            else:
                raise ValueError(
                    f'Unsupported file format: {file_extension}. Supported formats: .csv, .xlsx, .xls, .json'
                )
        
        except Exception as e:
            raise ValueError(f'Error loading narratives from {path}: {str(e)}')
    
    def _load_uuids_from_collection(self) -> list:
        '''
        Load the uuids from a MongoDB collection.
        '''
        return self.mongodb_manager.get_collected_uuids(
            self.mongo_db_name,
            self.mongo_collection_name
        )
    
    def _compose_blueprint_messages(self) -> tuple:
        '''
        Prepare the messages for the LLM.

        Each message is a list of role-based dictionaries containing the system
        prompt and the narrative-specific user prompt.

        :return: A tuple of uuids and messages lists ready for LLM input.
        :rtype: tuple
        '''
        template_path = self.args.get('prompt_template')
        system_prompt = self._load_system_prompt(template_path)

        # filter narratives by uuids
        uuids = self._load_uuids_from_collection()
        self.narratives = self.narratives[~ self.narratives['uuid'].isin(uuids)].copy()

        # prepare messages for each narrative
        messages_list = []
        for narrative in self.narratives['narrative']:
            user_prompt = self._load_message_prompt(template_path, narrative=narrative)
            message = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ]
            messages_list.append(message)
        
        return self.narratives['uuid'].tolist(), messages_list
    
    def run_blueprint_analysis(self) -> None:
        '''
        Run the blueprint analysis.

        :raises ConnectionFailure: If connection to MongoDB fails.
        '''
        # Test MongoDB access to database and collection before proceeding
        print('Testing MongoDB acccess to database...')
        mongodb_response = self.mongodb_manager.test_access_to_db_and_collection(
            self.mongo_db_name,
            self.mongo_collection_name
        )
        if not mongodb_response:
            print ('MongoDB access to database or collection failed')
            print ('')

            details = f'<<{self.mongo_db_name}>> and <<{self.mongo_collection_name}>>'
            raise ConnectionFailure(
                f'MongoDB access to database failed for {details}'
            )
        
        print('MongoDB access to database successful')
        print ('')

        # compose messages
        uuids, messages_list = self._compose_blueprint_messages()

        # use sample size if provided
        if self.sample_size:
            uuids = uuids[:self.sample_size]
            messages_list = messages_list[:self.sample_size]

        # run parallel prompt tasks
        print('Running narrative blueprint analysis...')
        self.llm_engine.run_parallel_prompt_tasks(
            uuids=uuids,
            messages=messages_list,
            mongo_db_name=self.mongo_db_name,
            mongo_collection_name=self.mongo_collection_name,
            response_format={'type': 'json_object'}
        )
