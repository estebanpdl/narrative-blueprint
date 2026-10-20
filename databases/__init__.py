# -*- coding: utf-8 -*-

from importlib import import_module


_MODULES = {
    'MongoDBManager': '.mongo',
    'JSONFileManager': '.json_file',
    'CSVFileManager': '.csv_file',
    'SQLiteManager': '.sqlite',
    'ParquetFileManager': '.parquet_file',
}
__all__ = list(_MODULES)


def __getattr__(name):
    if name not in _MODULES:
        raise AttributeError(name)
    return getattr(import_module(_MODULES[name], __name__), name)
