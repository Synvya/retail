"""Initialize the database tables."""

from retail_backend.core.database import Base, engine

print("Creating database tables...")
Base.metadata.create_all(bind=engine)
print("Tables created successfully!")
