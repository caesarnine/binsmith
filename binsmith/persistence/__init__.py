from functools import lru_cache

from binsmith.config import load_storage_config
from binsmith.persistence.sqlite_store import SQLiteSessionStore


@lru_cache(maxsize=1)
def get_default_store() -> SQLiteSessionStore:
    config = load_storage_config()
    return SQLiteSessionStore(config.db_path)


__all__ = ["SQLiteSessionStore", "get_default_store"]
