"""
Database module for handling database connections and models.
"""

from sqlalchemy.orm import DeclarativeBase, sessionmaker

engine: object
SessionLocal: sessionmaker

class Base(DeclarativeBase): ...
