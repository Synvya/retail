"""
Database module for handling database connections and models.
"""

from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

engine: Engine
SessionLocal: sessionmaker

class Base(DeclarativeBase): ...
