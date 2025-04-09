"""
Database module for handling database connections and models.
"""

from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

engine: Engine
SessionLocal: sessionmaker

def get_db_credentials(secret_name: str, region_name: str = "us-east-1") -> dict[str, Any]: ...

class Base(DeclarativeBase): ...
