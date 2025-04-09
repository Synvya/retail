"""Database module."""

import json
import os
from typing import Any, cast

import boto3  # type: ignore
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()


def get_db_credentials(secret_name: str, region_name: str = "us-east-1") -> dict[str, Any]:
    """Get database credentials from AWS Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=region_name)
    secret_value = client.get_secret_value(SecretId=secret_name)
    return cast(dict[str, Any], json.loads(secret_value["SecretString"]))


secret_name = os.getenv("DB_SECRET_NAME")
if secret_name is None:
    raise RuntimeError("DB_SECRET_NAME environment variable is not set.")
region_name = os.getenv("AWS_REGION", "us-east-1")
secret = get_db_credentials(secret_name, region_name)

username = secret["username"]
password = secret["password"]
host = os.getenv("DB_HOST")
db_name = os.getenv("DB_NAME", "synvya_square")

DATABASE_URL = f"postgresql://{username}:{password}@{host}:5432/{db_name}"

engine: Engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# Corrected test database connectivity
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("✅ Database connection successful:", result.scalar())
except Exception as e:
    print("❌ Database connection failed:", e)
